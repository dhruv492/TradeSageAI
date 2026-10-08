# TradeSage AI

Personal trading intelligence platform combining portfolio tracking with an
ML-driven signal engine (RandomForest baseline + LSTM, compared side by
side) for stocks and cryptocurrency. Decision-support only — not financial
advice.

## Repository layout

```
TradeSageAI/
├── backend/        Flask app, ML pipeline, services, tests (see backend/README.md)
│   ├── tests/      Smoke test suites
│   └── requirements.txt
├── frontend/       Vanilla HTML/CSS/JS dashboard (dashboard.html)
├── docs/           Synopsis, SRS, SPMP, project context file
├── .env.example    Copy to .env and fill in before running
└── .gitignore
```

## Quick start

```bash
cd backend
cp ../.env.example ../.env      # fill in SECRET_KEY at minimum; set FLASK_DEBUG and SEED_DEMO_USER as needed
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000/` in a browser. The landing page
(`index.html`) is served by Flask itself — the app is same-origin so the
Flask-Login session cookie alone handles authentication. The dashboard is
at `http://127.0.0.1:5000/dashboard` (requires login).

- **FLASK_DEBUG**: Set to `"1"` to enable Flask debug mode. Defaults to unset
  (production mode). Without `SECRET_KEY` and with `FLASK_DEBUG` unset, the
  app will refuse to start.
- **SEED_DEMO_USER**: Set to `"1"` to automatically seed a demo user
  (`trader@tradesage.ai` / `Password123!`) at startup. This controls the
  1-click demo button visibility. Leave unset to hide the demo button.
- **Auth model**: The app uses Flask-Login session cookies as the primary
  authentication mechanism. All API endpoints under `/api/*` require a valid
  login session (no unsigned `X-User-Id` or `Bearer ts_<id>` tokens are
  accepted).

## Status

Phases 0–3 complete (docs, MVP core, ML depth, stretch features). See
`docs/TradeSage_AI_Project_Context.md` for full decision history, and
`backend/README.md` for what's actually wired vs. still a TODO (e.g. live
NewsAPI/PRAW credentials aren't plugged into the sentiment fetchers yet —
sentiment defaults to neutral until real keys are added via `.env`).

## Status

Phases 0–3 complete (docs, MVP core, ML depth, stretch features). See
`docs/TradeSage_AI_Project_Context.md` for full decision history, and
`backend/README.md` for what's actually wired vs. still a TODO (e.g. live
NewsAPI/PRAW credentials aren't plugged into the sentiment fetchers yet —
sentiment defaults to neutral until real keys are added via `.env`).
