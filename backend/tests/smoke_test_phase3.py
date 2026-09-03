"""
Module      : smoke_test_phase3.py
Date        : 2026-08-30
Author      : Dhruv
Synopsis:
    Exercises the Phase 3 routes (watchlist, signal-history/feedback loop,
    portfolio comparison, admin panel) through Flask's test client. Reuses
    smoke_test_routes.py's fake-price-history approach since this sandbox
    has no network route to yfinance/Binance.
"""

import numpy as np
import pandas as pd

import price_service
import portfolio_service
from app import create_app
from models import db

np.random.seed(11)
_dates = pd.bdate_range(end=pd.Timestamp.today(), periods=250)
_closes = 100 * np.cumprod(1 + np.random.normal(0.0004, 0.011, len(_dates)))
_volumes = np.random.randint(1_000_000, 5_000_000, len(_dates))
_FAKE_PRICE_DF = pd.DataFrame({"close": _closes, "volume": _volumes}, index=_dates)
price_service.getHistoricalPrices = lambda *a, **k: _FAKE_PRICE_DF.copy()
# /api/portfolio(/comparison) hits portfolio_service's separate live-spot-price
# fetcher (not price_service's history fetcher) — mock that too, same
# no-network-in-tests reasoning. Real gap: no existing smoke test ever
# exercised /api/portfolio through a route, so this was never needed before.
portfolio_service._defaultStockPriceFetcher = lambda assetSymbol: float(_FAKE_PRICE_DF["close"].iloc[-1])
portfolio_service._defaultCryptoPriceFetcher = lambda assetSymbol: float(_FAKE_PRICE_DF["close"].iloc[-1])

app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
with app.app_context():
    db.create_all()
client = app.test_client()

client.post("/api/register", json={"email": "trader@example.com", "password": "hunter2pass"})
client.post("/api/login", json={"email": "trader@example.com", "password": "hunter2pass"})

# --- Watchlist (FR-5) ---
addResp = client.post("/api/watchlist", json={"assetSymbol": "TSLA", "assetType": "stock"})
assert addResp.status_code == 201, addResp.get_json()
watchlistId = addResp.get_json()["watchlistId"]

listResp = client.get("/api/watchlist")
assert listResp.status_code == 200
watchlistData = listResp.get_json()
assert len(watchlistData) == 1 and watchlistData[0]["assetSymbol"] == "TSLA"
assert watchlistData[0]["signalChanged"] is False  # no signals generated yet -> no change to flag
print("watchlist add/list OK ->", watchlistData)

delResp = client.delete(f"/api/watchlist/{watchlistId}")
assert delResp.status_code == 200
assert client.get("/api/watchlist").get_json() == []
print("watchlist delete OK")

# --- Feedback loop (FR-6.2): seed signals dated mid-series (real future outcomes exist) ---
from models import Signal
with app.app_context():
    for i, seedDate in enumerate(_dates[100:104]):
        db.session.add(Signal(
            userId=1, assetSymbol="AAPL", assetType="stock", generatedAt=seedDate.to_pydatetime(),
            horizonDays=3, modelUsed="random_forest", predictedDirection=["up", "down", "neutral", "up"][i],
            confidenceScore=0.6, topContributingFeatures="[]", featureSnapshot="{}",
        ))
    db.session.commit()

# a live /api/signal call for AAPL triggers resolveSignalOutcomes as a side effect
sigResp = client.get("/api/signal?assetSymbol=AAPL&assetType=stock")
assert sigResp.status_code == 200, sigResp.get_json()

historyResp = client.get("/api/signal-history?assetSymbol=AAPL")
assert historyResp.status_code == 200
historyData = historyResp.get_json()
resolvedCount = sum(1 for h in historyData if h["status"] == "resolved")
print(f"signal-history: {len(historyData)} rows, {resolvedCount} resolved ->", historyData[:2])
assert resolvedCount >= 4  # the 4 seeded past signals should all resolve (250-day series has future data for all of them)
assert all("wasCorrect" in h for h in historyData)
assert not any(isinstance(h.get("accuracy"), float) for h in historyData)  # no aggregate accuracy field anywhere (Honesty Framework)

# --- Comparison view (FR-6.3) ---
client.post("/api/holdings", json={"assetSymbol": "AAPL", "assetType": "stock", "quantity": 2, "buyPrice": 100, "buyDate": "2026-01-01"})
compResp = client.get("/api/portfolio/comparison")
assert compResp.status_code == 200
compData = compResp.get_json()
assert "stock" in compData and "crypto" in compData
print("comparison OK ->", compData)

# --- Admin panel (FR-7) ---
trackResp = client.post("/api/admin/tracked-assets", json={"assetSymbol": "BTC", "assetType": "crypto"})
assert trackResp.status_code == 201
trackedId = trackResp.get_json()["trackedAssetId"]
assert len(client.get("/api/admin/tracked-assets").get_json()) == 1

cfgResp = client.post("/api/admin/config", json={"retrainIntervalDays": 7})
assert cfgResp.status_code == 200 and cfgResp.get_json()["retrainIntervalDays"] == 7
assert client.get("/api/admin/config").get_json()["retrainIntervalDays"] == 7
print("admin tracked-assets + config OK")

healthResp = client.get("/api/admin/health")
assert healthResp.status_code == 200
healthData = healthResp.get_json()
assert len(healthData) == 1 and healthData[0]["status"] == "ok"  # mocked fetcher succeeds
print("admin health OK ->", healthData)

assert client.delete(f"/api/admin/tracked-assets/{trackedId}").status_code == 200

print("\nPHASE 3 ROUTE SMOKE TEST PASSED")
