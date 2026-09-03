"""
Module      : backtesting_service.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Initial version. Implements FR-4.1 (historical simulation),
                 FR-4.2 (Sharpe/win-rate/max-drawdown reporting), FR-4.3
                 (per-asset + aggregate views).
Synopsis:
    Walk-forward backtest: replays a series of historical direction signals
    against actual historical prices, builds a daily mark-to-market equity
    curve, and reports risk-adjusted performance metrics.

    Honesty Framework (non-negotiable, per SRS NFR-6 / Synopsis Sec 5):
    raw directional accuracy is NEVER the headline metric. It is computed
    internally only as an optional debug field (_debugDirectionalAccuracy)
    for developer sanity-checking, and is not surfaced in getMetrics()'s
    public return, matching FR-4.2's requirement not to lead with accuracy
    on what is expected to be imbalanced up/down/neutral data.

    Position model (documented assumption, stated because it materially
    affects results): one position open per asset at a time. A new signal
    that arrives while a position from a prior signal is still within its
    holding horizon is skipped rather than stacked. This avoids overlapping
    trades inflating apparent performance and keeps the simulation honest
    about what a single trader could actually have acted on.

Functions:
    runBacktest(priceSeries, signalSeries, horizonDays, riskFreeRate)
        -> dict with sharpeRatio, winRate, maxDrawdown, totalTrades,
           equityCurve, _debugDirectionalAccuracy
        priceSeries   : pandas Series, DatetimeIndex -> close price
        signalSeries  : pandas Series, DatetimeIndex -> 'up'|'down'|'neutral'
                        (must share priceSeries' index or a subset of it)
        horizonDays   : int, holding period per FR-3.3 (default 3)
        riskFreeRate  : float, annualized, for Sharpe (default 0.0)

    computeSharpeRatio(dailyReturns, riskFreeRate) -> float
    computeMaxDrawdown(equityCurve) -> float          # returned as a negative fraction
    computeWinRate(tradeReturns) -> float              # fraction in [0, 1]

Globals accessed/modified: None (stateless service; no G- globals).
"""

import numpy as np
import pandas as pd

HORIZON_DAYS_DEFAULT = 3     # ALL_CAPS constants per CHARUSAT standard
TRADING_DAYS_PER_YEAR = 252
DIRECTION_MULTIPLIER = {"up": 1, "down": -1, "neutral": 0}


def computeSharpeRatio(dailyReturns, riskFreeRate=0.0):
    dailyReturns = np.asarray(dailyReturns, dtype=float)
    if len(dailyReturns) == 0 or np.std(dailyReturns) == 0:
        return 0.0
    dailyRiskFree = riskFreeRate / TRADING_DAYS_PER_YEAR
    excessReturns = dailyReturns - dailyRiskFree
    return float(np.mean(excessReturns) / np.std(excessReturns) * np.sqrt(TRADING_DAYS_PER_YEAR))


def computeMaxDrawdown(equityCurve):
    equityCurve = np.asarray(equityCurve, dtype=float)
    if len(equityCurve) == 0:
        return 0.0
    runningPeak = np.maximum.accumulate(equityCurve)
    drawdownSeries = (equityCurve - runningPeak) / runningPeak
    return float(np.min(drawdownSeries))


def computeWinRate(tradeReturns):
    tradeReturns = np.asarray(tradeReturns, dtype=float)
    if len(tradeReturns) == 0:
        return 0.0
    return float(np.mean(tradeReturns > 0))


def runBacktest(priceSeries, signalSeries, horizonDays=HORIZON_DAYS_DEFAULT, riskFreeRate=0.0):
    priceSeries = priceSeries.sort_index()
    signalSeries = signalSeries.sort_index()
    tradingDates = priceSeries.index

    # Walk-forward: pick non-overlapping trades from non-neutral signals.
    tradeReturns = []
    positionByDate = pd.Series(0, index=tradingDates)  # +1 long, -1 short, 0 flat
    nextAvailableIdx = 0

    for signalDate, direction in signalSeries.items():
        multiplier = DIRECTION_MULTIPLIER.get(direction, 0)
        if multiplier == 0:
            continue
        if signalDate not in tradingDates:
            continue

        entryIdx = tradingDates.get_loc(signalDate)
        if entryIdx < nextAvailableIdx:
            continue  # overlapping with an already-open position, skip per position model

        exitIdx = min(entryIdx + horizonDays, len(tradingDates) - 1)
        if exitIdx <= entryIdx:
            continue

        entryPrice = priceSeries.iloc[entryIdx]
        exitPrice = priceSeries.iloc[exitIdx]
        tradeReturn = multiplier * ((exitPrice / entryPrice) - 1)
        tradeReturns.append(tradeReturn)

        positionByDate.iloc[entryIdx:exitIdx] = multiplier
        nextAvailableIdx = exitIdx

    # Daily mark-to-market equity curve from the position series.
    dailyAssetReturns = priceSeries.pct_change().fillna(0.0)
    dailyPortfolioReturns = (positionByDate.shift(1).fillna(0) * dailyAssetReturns).values
    equityCurve = np.cumprod(1 + dailyPortfolioReturns)

    directionalHits = [1 if r > 0 else 0 for r in tradeReturns]
    debugAccuracy = float(np.mean(directionalHits)) if directionalHits else 0.0

    return {
        "sharpeRatio": computeSharpeRatio(dailyPortfolioReturns, riskFreeRate),
        "winRate": computeWinRate(tradeReturns),
        "maxDrawdown": computeMaxDrawdown(equityCurve),
        "totalTrades": len(tradeReturns),
        "equityCurve": equityCurve.tolist(),
        "_debugDirectionalAccuracy": debugAccuracy,  # NOT surfaced in UI/report — Honesty Framework
    }
