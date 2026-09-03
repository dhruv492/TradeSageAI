# TradeSage AI — CE363 Project-III (CHARUSAT)

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
cp ../.env.example ../.env      # fill in SECRET_KEY at minimum
pip install -r requirements.txt
python app.py
```

Then open `frontend/dashboard.html` in a browser. Full setup detail,
known deviations from the CHARUSAT coding standard, and test instructions
live in `backend/README.md`.

## Status

Phases 0–3 complete (docs, MVP core, ML depth, stretch features). See
`docs/TradeSage_AI_Project_Context.md` for full decision history, and
`backend/README.md` for what's actually wired vs. still a TODO (e.g. live
NewsAPI/PRAW credentials aren't plugged into the sentiment fetchers yet —
sentiment defaults to neutral until real keys are added via `.env`).
