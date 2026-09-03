"""
Module      : portfolio_service.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated (rebuild session). Implements FR-2.1-2.4.
    (earlier session) - numpy float64 values from price-fetch libraries
        aren't JSON-serializable by Flask's default encoder; P&L values are
        cast to plain Python float before being returned from this module.
Synopsis:
    Manual holding entry, CSV bulk import (with per-row error reporting so
    one bad row doesn't abort the whole import), live price lookups
    (yfinance for stocks, Binance public REST for crypto), and P&L
    calculation. P&L is computed fresh per request from live prices
    (FR-2.4) rather than cached/stored, so it's never stale.

    Price fetchers are dependency-injected (stockPriceFetcher /
    cryptoPriceFetcher) for the same reason as sentiment_service.py's
    fetchers: testable without live network access, real client wiring
    lives in app.py.

Functions:
    addHolding(dbSession, userId, assetSymbol, assetType, quantity, buyPrice, buyDate) -> Holding
    importHoldingsFromCsv(dbSession, userId, csvFileObj) -> dict
        -> {"imported": int, "errors": [{"row": int, "reason": str}, ...]}
    getLivePrice(assetSymbol, assetType, stockPriceFetcher=None, cryptoPriceFetcher=None) -> float
    calculatePnl(holding, livePrice) -> dict
        -> {"unrealizedPnl": float, "unrealizedPnlPct": float, "currentValue": float}
    getPortfolioPnl(dbSession, userId, stockPriceFetcher=None, cryptoPriceFetcher=None) -> dict
        -> {"holdings": [...], "totalPnl": float}

Globals accessed/modified: None.
"""

import csv
import io
from datetime import datetime

from models import Holding


def _coerceToDate(buyDate):
    # CSV rows arrive as strings (e.g. "2025-02-01"); manual API calls may
    # already pass a date object. Real bug caught in smoke testing: passing
    # the raw string straight to the ORM column raises at commit time, not
    # at parse time, so it looked like a DB error until traced back here.
    if isinstance(buyDate, str):
        return datetime.strptime(buyDate, "%Y-%m-%d").date()
    return buyDate

REQUIRED_CSV_COLUMNS = ["assetSymbol", "assetType", "quantity", "buyPrice", "buyDate"]


def addHolding(dbSession, userId, assetSymbol, assetType, quantity, buyPrice, buyDate):
    newHolding = Holding(
        userId=userId,
        assetSymbol=assetSymbol.upper(),
        assetType=assetType,
        quantity=float(quantity),
        buyPrice=float(buyPrice),
        buyDate=_coerceToDate(buyDate),
    )
    dbSession.add(newHolding)
    dbSession.commit()
    return newHolding


def importHoldingsFromCsv(dbSession, userId, csvFileObj):
    reader = csv.DictReader(io.TextIOWrapper(csvFileObj, encoding="utf-8"))
    importedCount = 0
    rowErrors = []

    for rowIndex, row in enumerate(reader, start=2):  # row 1 is the header
        missingColumns = [c for c in REQUIRED_CSV_COLUMNS if not row.get(c)]
        if missingColumns:
            rowErrors.append({"row": rowIndex, "reason": f"missing columns: {missingColumns}"})
            continue
        try:
            addHolding(
                dbSession, userId,
                row["assetSymbol"], row["assetType"],
                row["quantity"], row["buyPrice"], row["buyDate"],
            )
            importedCount += 1
        except (ValueError, TypeError, KeyError) as parseError:
            rowErrors.append({"row": rowIndex, "reason": str(parseError)})

    return {"imported": importedCount, "errors": rowErrors}


def getLivePrice(assetSymbol, assetType, stockPriceFetcher=None, cryptoPriceFetcher=None):
    if assetType == "crypto":
        fetcher = cryptoPriceFetcher or _defaultCryptoPriceFetcher
    else:
        fetcher = stockPriceFetcher or _defaultStockPriceFetcher
    rawPrice = fetcher(assetSymbol)
    return float(rawPrice)  # guards against numpy float64 leaking into JSON responses


def calculatePnl(holding, livePrice):
    currentValue = holding.quantity * livePrice
    costBasis = holding.quantity * holding.buyPrice
    unrealizedPnl = currentValue - costBasis
    unrealizedPnlPct = (unrealizedPnl / costBasis * 100) if costBasis else 0.0
    return {
        "unrealizedPnl": float(unrealizedPnl),
        "unrealizedPnlPct": float(unrealizedPnlPct),
        "currentValue": float(currentValue),
    }


def getPortfolioPnl(dbSession, userId, stockPriceFetcher=None, cryptoPriceFetcher=None):
    holdings = dbSession.query(Holding).filter_by(userId=userId).all()
    results = []
    totalPnl = 0.0

    for holding in holdings:
        livePrice = getLivePrice(
            holding.assetSymbol, holding.assetType, stockPriceFetcher, cryptoPriceFetcher
        )
        pnl = calculatePnl(holding, livePrice)
        results.append({"holding": holding, "livePrice": livePrice, **pnl})
        totalPnl += pnl["unrealizedPnl"]

    return {"holdings": results, "totalPnl": float(totalPnl)}


# --- default fetchers (real network clients; not used in unit tests) --

def _defaultStockPriceFetcher(assetSymbol):
    import yfinance as yf
    ticker = yf.Ticker(assetSymbol)
    return ticker.fast_info["lastPrice"]


def _defaultCryptoPriceFetcher(assetSymbol):
    import requests
    response = requests.get(
        "https://api.binance.com/api/v3/ticker/price",
        params={"symbol": f"{assetSymbol.upper()}USDT"},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()["price"]
