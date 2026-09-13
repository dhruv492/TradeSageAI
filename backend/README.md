# TradeSage AI — CE363 Project-III (CHARUSAT)

Personal trading intelligence platform combining portfolio tracking with an
ML-driven signal engine (RandomForest baseline + LSTM, compared side by
side) for stocks and cryptocurrency. Decision-support only — not financial
advice.

## Contents

- `../docs/` — Synopsis, SRS, SPMP (Phase 0 deliverables)
- `watchlist_service.py` — Watchlist CRUD + signal-change flagging (FR-5), feedback-loop outcome resolution (FR-6.2)
- `admin_service.py` — tracked-asset management, retrain schedule config, data source health check (FR-7)
- `price_service.py` — historical OHLCV fetchers (yfinance/Binance), used by the Signal Engine and Backtesting Module
- `app.py` — Flask app factory + routes (auth, portfolio, **signal, backtest**, dashboard)
- `models.py` — SQLAlchemy ORM (User, Holding, Signal, BacktestResult, WatchlistItem, SentimentCache)
- `auth_service.py` — FR-1: registration/login/logout
- `portfolio_service.py` — FR-2: manual entry, CSV import, live price, P&L
- `feature_pipeline.py` — FR-3.1: RSI/MACD/SMA/volume-change + direction labeling
- `sentiment_service.py` — FR-3.2: VADER + finance lexicon, cached
- `signal_engine.py` — FR-3.3 (baseline): RandomForest
- `lstm_model.py` — FR-3.3 (deep): shallow 1-layer/32-unit LSTM
- `signal_service.py` — FR-3.3–3.5 orchestrator, persists both models' signals
- `explainability_service.py` — FR-3.4: SHAP (TreeExplainer / GradientExplainer)
- `backtesting_service.py` — FR-4: Sharpe ratio, win-rate, max drawdown (Honesty Framework)
- `../frontend/dashboard.html` — FR-6.1 dashboard: account (register/login/logout), portfolio (manual add + CSV import + P&L), Signal Engine display (both models side by side, confidence + SHAP features), Backtest display (Sharpe/win-rate/max-drawdown + equity curve)
- `tests/smoke_test.py`, `tests/smoke_test_full.py` — execution-based verification (not unit-test stubs; these run the real pipeline end to end)
- `tests/smoke_test_routes.py` — drives the actual Flask routes via the test client (auth cookies, `/api/signal`, `/api/backtest`), catching wiring bugs the two tests above can't see since they call service modules directly
- `tests/smoke_test_phase3.py` — route-level test for Watchlist, Admin panel, feedback loop, and comparison view (FR-5, FR-6.2, FR-6.3, FR-7)
- `tests/conftest.py` — puts `backend/` on `sys.path` so the smoke tests' bare `import app` / `import price_service` still resolve now that tests live in a subfolder

## Setup

```bash
pip install -r requirements.txt
python app.py   # run from inside backend/
```

Serves the API on `http://localhost:5000`. Open `../frontend/dashboard.html`
directly in a browser (or via a simple dev server on port 5500 — see
`ALLOWED_DASHBOARD_ORIGIN_DEFAULT` in `app.py` if you change the port).
Register an account first, then log in — the dashboard has no data to show
until you do, and the Signal/Backtest sections need an active session.

Note: `/api/signal` trains both models on first request for an asset
(~15-20s cold start, documented cost — this is an explicit user action, not
part of the dashboard's 3-second load NFR). Sentiment is neutral (0.0) until
real NewsAPI/PRAW keys are wired into the default fetchers in
`sentiment_service.py` — that's an open TODO, not a bug.

## Verifying the build

Run from inside `backend/`. These are script-style smoke tests, not pytest
test functions, so run each one directly with `backend/` on `PYTHONPATH`
(the `tests/conftest.py` handles this automatically if you invoke them via
`pytest` instead):

```bash
PYTHONPATH=. python tests/smoke_test.py         # SHAP explainability + backtesting in isolation
PYTHONPATH=. python tests/smoke_test_full.py    # full pipeline: auth -> portfolio -> features -> sentiment -> both models -> SHAP -> persisted signals
PYTHONPATH=. python tests/smoke_test_routes.py  # /api/signal + /api/backtest through real Flask routes (mocked price data)
PYTHONPATH=. python tests/smoke_test_phase3.py  # watchlist, feedback loop, comparison, admin panel through real Flask routes
```

Both scripts use synthetic data and mocked price/news fetchers by design —
no live API keys are required to verify correctness. Real yfinance/Binance/
NewsAPI/PRAW clients are wired in `portfolio_service.py` and
`sentiment_service.py`'s default fetchers for actual deployment.

## Status

Phase 0 (docs) — complete.
Phase 1 (MVP core) — complete.
Phase 2 (ML depth: sentiment, LSTM, SHAP, backtesting) — complete, and fully wired end to end: dashboard -> Flask routes -> services -> DB, verified via `smoke_test_routes.py`.
Phase 3 (Watchlist/Alerts, dashboard feedback loop, Admin panel) — complete, backend + frontend, verified via `smoke_test_phase3.py`. "Alerts" is an in-app flag (signal direction changed since the last check), not email/push — no notification infra was in scope. "Retrain schedule" is config storage only (FR-7.2); there is no cron/Celery executor reading it yet.

## Known deviations (documented, not oversights)

- DB table prefixes use `tbl_` (underscore) instead of CHARUSAT v1.0's
  `tbl-` (hyphen), because SQL engines reject hyphens in unquoted
  identifiers. Documented in `models.py`'s header.
- SHAP's LSTM explainer is `GradientExplainer`, not `DeepExplainer` —
  `DeepExplainer` has no built-in rule for `nn.LSTM` and failed its own
  additivity check during smoke testing. Documented in
  `explainability_service.py`'s header.
- `User` model requires Flask-Login's `UserMixin` (adds `is_active` etc.) —
  missing before 2026-08-29, caught by `smoke_test_routes.py` because it's
  the first test to call Flask-Login's real `login_user()` through an
  actual request instead of calling `auth_service` functions directly.
- `requirements.txt`'s `numpy` pin was bumped from `1.26.4` to `2.4.4` —
  the old pin conflicts with `torch==2.13.0`/`shap==0.52.0`'s numpy 2.x
  requirement and made `pip install -r requirements.txt` fail outright
  with `ResolutionImpossible` on a clean install.
