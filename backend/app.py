"""
Module      : app.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated (rebuild session). Wires all modules into a
                 Flask app; implements the dashboard-facing endpoints for
                 FR-1 through FR-4.
    (earlier session) - CORS + session cookies don't combine by default:
        supports_credentials must be True AND origins must be an explicit
        list (not "*") for the browser to accept the Set-Cookie on
        cross-origin XHR from the plain HTML/CSS/JS dashboard. Both are
        set below; this was a real bug caught via smoke testing, not a
        guess.
Synopsis:
    Flask application factory + route registration. Minimal HTML/CSS/JS
    dashboard is served from /static per the locked "no React" frontend
    decision (SRS 2.2, project context Section 5).

Globals accessed/modified:
    G-Db (module-level SQLAlchemy instance from models.py, imported not
    redefined — CHARUSAT global naming convention applied at the point of
    use in create_app()).

Functions:
    create_app(configOverrides=None) -> Flask app instance
"""

import io
import json
import os
from datetime import date, datetime

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_login import LoginManager, current_user, login_required

import admin_service
import auth_service
import portfolio_service
import price_service
import sentiment_service
import watchlist_service
from backtesting_service import runBacktest
from feature_pipeline import buildFeatureFrame, labelDirection
from lstm_model import WINDOW_SIZE_DEFAULT, buildSequenceWindows, trainLstm
from models import db, User, Signal, BacktestResult, MODEL_BASELINE, MODEL_LSTM
from signal_engine import trainRandomForestBaseline
from signal_service import generateSignal

ALLOWED_DASHBOARD_ORIGIN_DEFAULT = "http://localhost:5500"  # plain HTML/CSS/JS dev server
CLASS_NAMES = ["down", "neutral", "up"]

# G-ModelCache: process-lifetime cache of trained models keyed by
# (assetSymbol, todaysDateIsoString). Decision: signal generation is an
# explicit user action, not part of the dashboard's 3-second NFR-1 load
# (documented earlier in the project record), so training on first request
# per asset per day is acceptable — this cache just avoids repeating that
# ~17s cold-start cost on every subsequent click for the same asset today.
G_ModelCache = {}


def create_app(configOverrides=None):
    # Repo reorg (lean-build session): dashboard.html now lives in ../frontend
    # instead of a static/ folder next to app.py. static_folder is pointed
    # there explicitly so Flask's default static route keeps serving it at
    # the same /static/dashboard.html URL the smoke tests and browser already
    # expect - no other route or test needed to change.
    app = Flask(__name__, static_folder="../frontend", static_url_path="/static")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///tradesage.db"
    )
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-only-change-in-production"
    )
    if configOverrides:
        app.config.update(configOverrides)

    db.init_app(app)

    # Real bug from earlier smoke testing: credentials + CORS need an
    # explicit origin (not "*") or the browser silently drops the cookie.
    CORS(app, supports_credentials=True,
         origins=[app.config.get("DASHBOARD_ORIGIN", ALLOWED_DASHBOARD_ORIGIN_DEFAULT)])

    loginManager = LoginManager()
    loginManager.init_app(app)

    @loginManager.user_loader
    def loadUser(userId):
        return db.session.get(User, int(userId))

    @app.route("/api/register", methods=["POST"])
    def register():
        body = request.get_json()
        try:
            newUser = auth_service.registerUser(db.session, body["email"], body["password"])
        except ValueError as registrationError:
            return jsonify({"error": str(registrationError)}), 409
        return jsonify({"userId": newUser.userId, "email": newUser.email}), 201

    @app.route("/api/login", methods=["POST"])
    def login():
        body = request.get_json()
        user = auth_service.verifyLogin(db.session, body["email"], body["password"])
        if user is None:
            return jsonify({"error": "invalid credentials"}), 401
        auth_service.loginUser(user)
        return jsonify({"userId": user.userId, "email": user.email})

    @app.route("/api/logout", methods=["POST"])
    @login_required
    def logout():
        auth_service.logoutUser()
        return jsonify({"status": "logged out"})

    @app.route("/api/holdings", methods=["POST"])
    @login_required
    def addHolding():
        body = request.get_json()
        holding = portfolio_service.addHolding(
            db.session, current_user.userId,
            body["assetSymbol"], body["assetType"],
            body["quantity"], body["buyPrice"], body["buyDate"],
        )
        return jsonify({"holdingId": holding.holdingId}), 201

    @app.route("/api/holdings/import", methods=["POST"])
    @login_required
    def importHoldings():
        uploadedFile = request.files["file"]
        result = portfolio_service.importHoldingsFromCsv(
            db.session, current_user.userId, io.BytesIO(uploadedFile.read())
        )
        return jsonify(result)

    @app.route("/api/portfolio", methods=["GET"])
    @login_required
    def getPortfolio():
        result = portfolio_service.getPortfolioPnl(db.session, current_user.userId)
        return jsonify({
            "totalPnl": result["totalPnl"],
            "holdings": [
                {
                    "assetSymbol": h["holding"].assetSymbol,
                    "assetType": h["holding"].assetType,
                    "quantity": h["holding"].quantity,
                    "livePrice": h["livePrice"],
                    "unrealizedPnl": h["unrealizedPnl"],
                    "unrealizedPnlPct": h["unrealizedPnlPct"],
                }
                for h in result["holdings"]
            ],
        })

    @app.route("/api/signal", methods=["GET"])
    @login_required
    def getSignal():
        assetSymbol = request.args.get("assetSymbol")
        assetType = request.args.get("assetType", "stock")
        if not assetSymbol:
            return jsonify({"error": "assetSymbol query param required"}), 400

        priceDf = price_service.getHistoricalPrices(assetSymbol, assetType)
        # No headlineFetcher/postFetcher injected here yet: real NewsAPI/PRAW
        # client wiring (with API keys) is a separate, still-open TODO per
        # sentiment_service.py's own docstring. Until then this safely
        # returns 0.0 (neutral) rather than crashing or faking a score.
        sentimentScore = sentiment_service.getSentimentForAsset(
            assetSymbol, assetType, date.today(), db.session,
        )

        rfModel, rfBackground, lstmModel, lstmBackground, featureNames = \
            _getOrTrainModels(assetSymbol, priceDf, sentimentScore)

        signalRows = generateSignal(
            db.session, current_user.userId, assetSymbol, assetType, priceDf,
            sentimentScore=sentimentScore,
            rfModel=rfModel, rfBackground=rfBackground,
            lstmModel=lstmModel, lstmBackground=lstmBackground,
            featureNames=featureNames,
        )
        # FR-6.2 feedback loop: opportunistically resolve any of this
        # asset's older signals now that we already have fresh price data
        # in hand — avoids a second fetch just to run this check.
        watchlist_service.resolveSignalOutcomes(db.session, assetSymbol, priceDf)

        return jsonify({
            "assetSymbol": assetSymbol,
            "assetType": assetType,
            "signals": [
                {
                    "modelUsed": row.modelUsed,
                    "predictedDirection": row.predictedDirection,
                    "confidenceScore": row.confidenceScore,
                    "topContributingFeatures": json.loads(row.topContributingFeatures),
                    "horizonDays": row.horizonDays,
                }
                for row in signalRows
            ],
        })

    @app.route("/api/backtest", methods=["POST"])
    @login_required
    def backtest():
        body = request.get_json()
        assetSymbol = body["assetSymbol"]
        modelUsed = body.get("modelUsed", MODEL_BASELINE)
        assetType = body.get("assetType", "stock")
        horizonDays = body.get("horizonDays", 3)

        # Pull this user's persisted signal history for the asset+model —
        # FR-4.1's "historical data" is the Signal table itself, populated
        # by prior /api/signal calls, not a separately re-simulated series.
        signalRowsQuery = (
            db.session.query(Signal)
            .filter_by(userId=current_user.userId, assetSymbol=assetSymbol, modelUsed=modelUsed)
            .order_by(Signal.generatedAt)
            .all()
        )
        if len(signalRowsQuery) < 2:
            return jsonify({"error": "not enough signal history yet to backtest (need 2+ past signals)"}), 400

        signalSeries = pd.Series(
            [row.predictedDirection for row in signalRowsQuery],
            index=pd.DatetimeIndex([row.generatedAt.date() for row in signalRowsQuery]),
        )
        rangeStart = signalRowsQuery[0].generatedAt.date()
        rangeEnd = date.today()
        priceDf = price_service.getHistoricalPrices(assetSymbol, assetType)
        priceSeries = priceDf["close"]

        metrics = runBacktest(priceSeries, signalSeries, horizonDays=horizonDays)

        resultRow = BacktestResult(
            userId=current_user.userId,
            assetSymbol=assetSymbol,
            modelUsed=modelUsed,
            rangeStart=rangeStart,
            rangeEnd=rangeEnd,
            sharpeRatio=metrics["sharpeRatio"],
            winRate=metrics["winRate"],
            maxDrawdown=metrics["maxDrawdown"],
            totalTrades=metrics["totalTrades"],
            equityCurve=json.dumps(metrics["equityCurve"]),
        )
        db.session.add(resultRow)
        db.session.commit()

        # _debugDirectionalAccuracy deliberately dropped here, not just in
        # backtesting_service — Honesty Framework applies at every layer
        # the metric could otherwise leak through (NFR-6).
        return jsonify({
            "sharpeRatio": metrics["sharpeRatio"],
            "winRate": metrics["winRate"],
            "maxDrawdown": metrics["maxDrawdown"],
            "totalTrades": metrics["totalTrades"],
            "equityCurve": metrics["equityCurve"],
        })

    # --- Phase 3: Watchlist & Alerts (FR-5) ---

    @app.route("/api/watchlist", methods=["GET"])
    @login_required
    def getWatchlist():
        return jsonify(watchlist_service.getWatchlistWithAlerts(db.session, current_user.userId))

    @app.route("/api/watchlist", methods=["POST"])
    @login_required
    def addWatchlistItem():
        body = request.get_json()
        item = watchlist_service.addToWatchlist(
            db.session, current_user.userId, body["assetSymbol"], body.get("assetType", "stock"),
        )
        return jsonify({"watchlistId": item.watchlistId}), 201

    @app.route("/api/watchlist/<int:watchlistId>", methods=["DELETE"])
    @login_required
    def deleteWatchlistItem(watchlistId):
        removed = watchlist_service.removeFromWatchlist(db.session, current_user.userId, watchlistId)
        if not removed:
            return jsonify({"error": "not found"}), 404
        return jsonify({"status": "removed"})

    # --- Phase 3: Feedback loop (FR-6.2) ---

    @app.route("/api/signal-history", methods=["GET"])
    @login_required
    def getSignalHistory():
        assetSymbol = request.args.get("assetSymbol")
        if not assetSymbol:
            return jsonify({"error": "assetSymbol query param required"}), 400
        return jsonify(watchlist_service.getSignalHistory(db.session, current_user.userId, assetSymbol))

    # --- Phase 3: Stock vs crypto comparison (FR-6.3) ---

    @app.route("/api/portfolio/comparison", methods=["GET"])
    @login_required
    def getPortfolioComparison():
        result = portfolio_service.getPortfolioPnl(db.session, current_user.userId)
        byType = {"stock": {"totalPnl": 0.0, "holdingCount": 0}, "crypto": {"totalPnl": 0.0, "holdingCount": 0}}
        for h in result["holdings"]:
            bucket = byType.setdefault(h["holding"].assetType, {"totalPnl": 0.0, "holdingCount": 0})
            bucket["totalPnl"] += h["unrealizedPnl"]
            bucket["holdingCount"] += 1
        return jsonify(byType)

    # --- Phase 3: Admin/Config panel (FR-7) ---
    # NOTE: SRS 2.1 treats Admin as "the same physical person as Trader/
    # User, but a distinct role" (solo project) — enforced here only by
    # @login_required, not a separate role check, matching that spec.

    @app.route("/api/admin/tracked-assets", methods=["GET"])
    @login_required
    def listTrackedAssets():
        assets = admin_service.listTrackedAssets(db.session)
        return jsonify([{"trackedAssetId": a.trackedAssetId, "assetSymbol": a.assetSymbol, "assetType": a.assetType} for a in assets])

    @app.route("/api/admin/tracked-assets", methods=["POST"])
    @login_required
    def addTrackedAsset():
        body = request.get_json()
        asset = admin_service.addTrackedAsset(db.session, body["assetSymbol"], body.get("assetType", "stock"))
        return jsonify({"trackedAssetId": asset.trackedAssetId}), 201

    @app.route("/api/admin/tracked-assets/<int:trackedAssetId>", methods=["DELETE"])
    @login_required
    def deleteTrackedAsset(trackedAssetId):
        removed = admin_service.removeTrackedAsset(db.session, trackedAssetId)
        if not removed:
            return jsonify({"error": "not found"}), 404
        return jsonify({"status": "removed"})

    @app.route("/api/admin/config", methods=["GET"])
    @login_required
    def getAdminConfig():
        config = admin_service.getRetrainConfig(db.session)
        return jsonify({"retrainIntervalDays": config.retrainIntervalDays})

    @app.route("/api/admin/config", methods=["POST"])
    @login_required
    def setAdminConfig():
        body = request.get_json()
        config = admin_service.setRetrainInterval(db.session, body["retrainIntervalDays"])
        return jsonify({"retrainIntervalDays": config.retrainIntervalDays})

    @app.route("/api/admin/health", methods=["GET"])
    @login_required
    def getDataSourceHealth():
        return jsonify(admin_service.checkDataSourceHealth(db.session))

    return app


def _getOrTrainModels(assetSymbol, priceDf, sentimentScore):
    """Train RF+LSTM on demand and cache per (asset, day) — see G_ModelCache
    comment above for why per-day retraining (not per-request) is the right
    tradeoff here rather than a more elaborate persisted model store."""
    cacheKey = (assetSymbol, date.today().isoformat())
    if cacheKey in G_ModelCache:
        return G_ModelCache[cacheKey]

    featureFrame = buildFeatureFrame(priceDf)
    labels = labelDirection(priceDf["close"])
    featureFrameWithSentiment = featureFrame.copy()
    featureFrameWithSentiment["sentiment"] = sentimentScore
    featureNames = list(featureFrameWithSentiment.columns)

    rfModel = trainRandomForestBaseline(featureFrameWithSentiment, labels)
    rfBackground = featureFrameWithSentiment.tail(80).values[:60]

    sequences, seqLabels = buildSequenceWindows(featureFrameWithSentiment, labels, WINDOW_SIZE_DEFAULT)
    lstmModel = None
    lstmBackground = None
    if len(sequences) > 0:
        lstmModel = trainLstm(sequences, seqLabels, classNames=CLASS_NAMES)
        lstmBackground = sequences[-30:]

    result = (rfModel, rfBackground, lstmModel, lstmBackground, featureNames)
    G_ModelCache[cacheKey] = result
    return result


if __name__ == "__main__":
    application = create_app()
    with application.app_context():
        db.create_all()
    application.run(debug=True)
