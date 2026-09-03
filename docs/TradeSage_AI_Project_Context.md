# TradeSage AI — Project Context & Continuity File

> **Purpose of this file:** This is the single source of truth for the TradeSage AI
> project. Paste/upload this at the start of any future chat to resume exactly where
> we left off — no re-explaining needed.

---

## ⚠️ STANDING INSTRUCTION — HIGHEST PRIORITY, APPLIES TO ENTIRE PROJECT

**"Let me know all your moves — all means every single move."**

This is a top-priority, permanent instruction for the rest of this project. It means:
- Before/while doing any implementation work — writing code, creating a file, making
  a design decision, choosing a library, structuring a database table, picking a
  default value — **explain the move out loud as it happens**, not just the end
  result.
- Don't silently make judgment calls and present only the finished artifact. Narrate
  the *why* behind each step, not just the *what*.
- This applies to every module, every file, every script, every decision — big or
  small — for the rest of the project, across all future chats.
- If this instruction is ever unclear in a specific moment, default to
  **over-explaining rather than under-explaining.**

---

## 1. Course Context (CE363: Project-III, CHARUSAT)

- Team size: ≤3 students (TBD — not decided yet by user)
- Full SDLC required (Software Engineering principles applied throughout)
- Weekly evaluation by internal guide (lab hours)
- **Mandatory final submission documents:**
  1. Project Synopsis
  2. Software Requirement Specification (SRS)
  3. Software Project Management Plan (SPMP)
  4. Final Project Report
  5. Project Setup file with Source Code
  6. Project Presentation (PPT)
- Total Lab hours: 60
- Course Outcomes to map against (CO1–CO6): teamwork, requirements analysis, design/
  implementation, societal/global impact analysis, technical reporting & viz, end-user
  communication.
- **Coding Standard (CHARUSAT v1.0) — must be followed in all code:**
  - Local variables: `camelCase` (e.g. `localData`)
  - Global variables: `PascalCase` with `G-` prefix (e.g. `G-CityName`)
  - Constants: `ALL_CAPS` (e.g. `CONSDATA`)
  - Functions: `camelCase`, name should clearly describe purpose
  - DB objects: `tbl-`, `vw-`, `tr-` (trigger), `Pr/fn-` prefixes
  - GUI controls: `txt-`, `rdo-`, `chk-`, `cmb-`, `lst-`, `opt-`, `grd-`, `tbl-` prefixes
  - Every module needs a header: module name, date, author, modification history,
    synopsis, functions + I/O params, globals accessed/modified
  - Proper indentation, spacing after commas, braces on new lines, well-commented code
  - Avoid GOTO, avoid overloaded identifiers, keep functions short

---

## 2. Decision History (how we got here — for context, not re-litigation)

1. Started open-ended: user wanted a project from the attached Project List / syllabus,
   AI/ML-Python being their strongest stack.
2. User was "blank" on direction — wanted something that teaches while building.
3. First proposal: **MedAssist AI** (symptom-checker + disease prediction) — rejected
   in favor of a Finance direction per user's explicit request.
4. Pivoted to Finance. Three options presented:
   - **FinWise** — personal finance manager (expense categorization + anomaly
     detection + forecasting) — ranked #1 initially for full-SDLC richness.
   - **CreditSense** — loan default/credit risk prediction — ranked as alternative,
     ML-heavy but thin on user roles.
   - **MarketPulse** — stock trend prediction via sentiment + price (LSTM) — ranked
     #2 initially due to: (a) low achievable accuracy ceiling for direction
     prediction, (b) weak/noisy sentiment-price correlation in practice, (c) thinner
     SRS/design story (one user role), (d) fussier data pipeline (aligning news +
     price data without paid APIs).
5. **Key turning point:** User revealed they actively trade stocks *and* crypto. This
   materially changes the calculus — domain expertise is the biggest lever for a
   project like this (better feature selection, healthier skepticism of results,
   real evaluation criteria like Sharpe ratio/drawdown/win-rate instead of naive
   accuracy, and crypto adds a genuinely interesting stock-vs-crypto comparison
   angle). MarketPulse re-ranked as a strong contender.
6. User liked MarketPulse, then asked about a **merged version**: MarketPulse's
   ML signal engine + FinWise's portfolio-tracking shell — combining full-SDLC
   richness (real user workflows, real feedback loop) with ML depth and the user's
   domain expertise.
7. **Final decision: TradeSage AI** (merged version) — locked in by user as of this
   chat. Full spec below.

---

## 3. LOCKED PROJECT SPECIFICATION

```
Build TradeSage AI — a personal trading intelligence platform combining
portfolio tracking with an ML-driven sentiment + price signal engine for
stocks and crypto, for CE363 Project-III.

PROJECT SPECIFICATION (REQUIRED):
- Domain: FinTech / AI-ML (Trading & Investment)
- Team Size: [1–3, TBD — user to confirm]
- Tech Stack: Python (Flask/Django) backend, scikit-learn + a lightweight
  LSTM/GRU (PyTorch or TensorFlow) for the signal engine, React or
  HTML/CSS/JS frontend with a charting library (e.g. Chart.js / Plotly),
  PostgreSQL/MySQL for portfolio + trade data, Celery/cron-style scheduled
  job for daily data refresh
- Data Sources:
  - Price data: yfinance (stocks), CCXT or a free crypto exchange API
    (Binance public API) for crypto — no paid API needed
  - Sentiment data: NewsAPI free tier or scraped headlines for stocks;
    Reddit (via PRAW, free) or Twitter/X free-tier alternative for crypto
    sentiment
- Coding Standards: CHARUSAT Coding Standard v1.0 (see Section 1 above)

MODULE STRUCTURE:
1. Auth Module — registration/login, single or multi-user support
2. Portfolio Tracker — add/track holdings (stocks + crypto), CSV import,
   live price updates, P&L calculation
3. Signal Engine (core ML):
   - Feature pipeline: technical indicators (RSI, MACD, volume, moving
     averages) + sentiment score (NLP on news/Reddit headlines)
   - Model: baseline (Logistic Regression / Random Forest) vs. LSTM,
     compared side by side — direction prediction (up/down/neutral) over
     a defined horizon (e.g. next 3 days). NEVER predict exact price.
   - Confidence score + top contributing factors per signal (SHAP or
     feature importance — explainability required, no black box)
4. Backtesting Module — Sharpe ratio, win-rate, max drawdown (NOT raw
   accuracy). This module is what makes the ML claims defensible.
5. Watchlist & Alerts — track unheld assets, notify on signal changes
6. Dashboard — portfolio overview, per-asset signal history vs. actual
   outcome (feedback loop), stock vs. crypto comparison view
7. Admin/Config Panel — manage tracked assets, retrain schedule, data
   source health monitoring

EVALUATION & HONESTY FRAMEWORK (non-negotiable, protects report credibility):
- Report backtested metrics (Sharpe ratio, win-rate, max drawdown) — never
  lead with raw "accuracy" (misleading for imbalanced up/down classes)
- Dedicated Limitations section: market noise, non-stationarity,
  survivorship bias in backtesting, no guarantee of future performance
- Explicit framing as decision-support tool, NOT financial advice — stated
  in SRS and on the UI itself

DELIVERABLES (mandatory per CE363 syllabus):
- Project Synopsis
- Software Requirement Specification (SRS)
- Software Project Management Plan (SPMP)
- Final Project Report
- Project Setup file with Source Code
- Project Presentation (PPT)

CO MAPPING FOR FINAL REPORT:
- CO2 → SRS: user stories drawn from the user's own real trading workflow
- CO3 → Design: signal engine + backtesting architecture
- CO4 → Societal impact: retail investor decision-support, financial
  literacy angle, explicit disclaimer framing
- CO5 → Visualization: dashboard, backtest charts
- CO6 → User testing: 2–3 other traders test it and give real feedback
  (not hypothetical)
```

---

## 4. Project Outline / Roadmap (phased — for when we resume)

**Status as of this file: NOT STARTED. No code, no docs written yet. Team size not
yet finalized by user. This is purely a planning/context artifact.**

### Phase 0 — Setup & Documentation (do this first when we resume)
- [ ] Confirm team size (solo / 2 / 3)
- [ ] Draft Project Synopsis
- [ ] Draft SRS (actors: Trader/User, Admin; functional + non-functional requirements)
- [ ] Draft SPMP (timeline, milestones, risk register — flag ML accuracy/market-noise
      risk explicitly here)
- [ ] Set up repo structure, environment, coding-standard boilerplate (module header
      template, naming-convention cheat sheet for the team)

### Phase 1 — MVP Core (get something end-to-end working early)
- [ ] Auth module (basic)
- [ ] Portfolio Tracker (manual entry + basic CSV import, P&L calc)
- [ ] Price data pipeline (yfinance + Binance/CCXT integration)
- [ ] Signal Engine v1 — baseline model only (Logistic Regression or Random
      Forest), technical indicators only (no sentiment yet), direction prediction
- [ ] Minimal dashboard showing portfolio + basic signal

### Phase 2 — ML Depth & Credibility Layer
- [ ] Add sentiment pipeline (NewsAPI for stocks, Reddit/PRAW for crypto)
- [ ] Add LSTM/GRU model, compare against baseline
- [ ] Explainability layer (SHAP / feature importance) on signals
- [ ] Backtesting module — Sharpe ratio, win-rate, max drawdown reporting
- [ ] Limitations section drafted in parallel (don't leave this to the end)

### Phase 3 — Polish & Stretch Goals (only if time allows)
- [ ] Watchlist & Alerts
- [ ] Stock vs. crypto comparison view
- [ ] Admin/Config panel (retrain schedule, data source health)
- [ ] Feedback loop UI: signal history vs. actual outcome
- [ ] User testing round (2–3 traders — CO6 requirement)

### Always-on (every phase)
- Weekly progress log entries for the internal guide
- Explain-every-move standing instruction (see top of this file) applies
  throughout — this is not phase-specific, it's permanent.

---

## 5. Open Items / Not Yet Decided

- Final team size (user said "will let you know later")
- Which specific crypto exchange API to lock in (Binance public API assumed for now)
- Whether frontend will be React or plain HTML/CSS/JS (likely depends on final
  team size / comfort level — revisit in Phase 0)
- Exact prediction horizon for the signal engine (3 days assumed as a starting
  point, open to adjustment)

---

*End of context file. Resume by uploading this file and saying "continue TradeSage AI
from where we left off" — everything needed to pick up seamlessly is above.*
