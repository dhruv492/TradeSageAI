"""
Module      : smoke_test_routes.py
Date        : 2026-08-29
Author      : Dhruv
Synopsis:
    Exercises /api/signal and /api/backtest through Flask's test client
    (real HTTP-shaped requests, real session cookies) rather than calling
    signal_service/backtesting_service directly. smoke_test_full.py already
    proved the underlying services work; this proves app.py's wiring of
    them (routes, auth, JSON shapes) works too, since that wiring didn't
    exist before this session and had no test coverage.

    Price history is mocked via monkeypatching price_service's default
    fetcher (this sandbox has no network route to yfinance/Binance) —
    same "no live network in tests" principle as the existing smoke tests.
"""

import numpy as np
import pandas as pd
from datetime import date

import price_service
from app import create_app
from models import db

# --- monkeypatch: deterministic synthetic price history, no network ---
np.random.seed(7)
_dates = pd.bdate_range(end=pd.Timestamp.today(), periods=250)
_closes = 100 * np.cumprod(1 + np.random.normal(0.0004, 0.011, len(_dates)))
_volumes = np.random.randint(1_000_000, 5_000_000, len(_dates))
_FAKE_PRICE_DF = pd.DataFrame({"close": _closes, "volume": _volumes}, index=_dates)

price_service.getHistoricalPrices = lambda *a, **k: _FAKE_PRICE_DF.copy()

app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
with app.app_context():
    db.create_all()

client = app.test_client()

registerResp = client.post("/api/register", json={"email": "trader@example.com", "password": "hunter2pass"})
assert registerResp.status_code == 201, registerResp.get_json()

loginResp = client.post("/api/login", json={"email": "trader@example.com", "password": "hunter2pass"})
assert loginResp.status_code == 200, loginResp.get_json()
print("auth via routes OK")

# --- /api/signal: first call trains + persists two Signal rows ---
signalResp = client.get("/api/signal?assetSymbol=AAPL&assetType=stock")
assert signalResp.status_code == 200, signalResp.get_json()
signalData = signalResp.get_json()
modelsReturned = {s["modelUsed"] for s in signalData["signals"]}
print("GET /api/signal ->", [(s["modelUsed"], s["predictedDirection"], round(s["confidenceScore"], 3)) for s in signalData["signals"]])
assert modelsReturned == {"random_forest", "lstm"}
assert all(len(s["topContributingFeatures"]) > 0 for s in signalData["signals"])

# second call should hit G_ModelCache (no retraining) and still succeed
signalResp2 = client.get("/api/signal?assetSymbol=AAPL&assetType=stock")
assert signalResp2.status_code == 200
print("GET /api/signal (cached) OK")

# --- /api/backtest ---
# The two /api/signal calls above both landed "today" (the last row in our
# fake price series), so they have no future price data yet to be judged
# against — runBacktest correctly returns 0 trades for those, which is
# honest, not a bug. To actually exercise the metrics math through the
# route, seed a few older signals (dated mid-series) directly, matching
# what real signal history looks like after the app has run for a while.
from models import Signal
with app.app_context():
    seedDates = _dates[100:110:2]  # 5 dates, spaced out, with future price data available
    for i, seedDate in enumerate(seedDates):
        direction = ["up", "down", "up", "neutral", "up"][i]
        db.session.add(Signal(
            userId=1, assetSymbol="AAPL", assetType="stock", generatedAt=seedDate.to_pydatetime(),
            horizonDays=3, modelUsed="random_forest", predictedDirection=direction,
            confidenceScore=0.6, topContributingFeatures="[]", featureSnapshot="{}",
        ))
    db.session.commit()

backtestResp = client.post("/api/backtest", json={"assetSymbol": "AAPL", "assetType": "stock", "modelUsed": "random_forest"})
assert backtestResp.status_code == 200, backtestResp.get_json()
backtestData = backtestResp.get_json()
print("POST /api/backtest ->", {k: v for k, v in backtestData.items() if k != "equityCurve"})
assert "sharpeRatio" in backtestData and "winRate" in backtestData and "maxDrawdown" in backtestData
assert backtestData["totalTrades"] >= 3  # the 5 seeded dated signals should now actually resolve into trades
assert "_debugDirectionalAccuracy" not in backtestData  # Honesty Framework must hold through the API layer too

print("\nROUTE-LEVEL SMOKE TEST PASSED")
