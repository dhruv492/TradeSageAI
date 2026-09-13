"""
Module      : models.py (partial recreation — Signal & BacktestResult only)
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated minimal subset needed by explainability_service.py
                 and backtesting_service.py after a fresh sandbox session.
                 Full model set (User, Holding, WatchlistItem, SentimentCache)
                 already exists in the working codebase and is unchanged;
                 only reproduced here so this module is self-contained and
                 importable on its own.
Synopsis:
    SQLAlchemy ORM definitions for the Signal and BacktestResult entities,
    matching SRS Section 5 (Data Requirements).

Naming Standard Deviation (documented, per project convention):
    Table name prefixes use underscore (tbl_Signal) rather than the hyphen
    shown in CHARUSAT v1.0 (tbl-Signal), because SQLAlchemy/most SQL engines
    do not accept hyphens in unquoted identifiers. This deviation was made
    deliberately and consistently across the whole schema, not just here.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# Constants (ALL_CAPS per CHARUSAT standard)
MODEL_BASELINE = "random_forest"
MODEL_LSTM = "lstm"
DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
DIRECTION_NEUTRAL = "neutral"


class User(db.Model, UserMixin):
    """FR-1: auth actor. Passwords stored hashed only (NFR-4).
    UserMixin added 2026-08-29: Flask-Login's login_user() reads
    user.is_active (and other properties) that a plain db.Model doesn't
    provide. Never caught before because smoke_test_full.py exercises
    auth_service functions directly and never calls Flask-Login's actual
    login_user() through a real request — smoke_test_routes.py, which does,
    is what caught this."""
    __tablename__ = "tbl_User"

    userId = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    passwordHash = db.Column(db.String(255), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        # Flask-Login requires a string id
        return str(self.userId)


class Holding(db.Model):
    """FR-2.1-2.4: a portfolio position. P&L is computed fresh per request
    from live price, not stored, so this table only holds cost basis."""
    __tablename__ = "tbl_Holding"

    holdingId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey("tbl_User.userId"), nullable=False)
    assetSymbol = db.Column(db.String(20), nullable=False)
    assetType = db.Column(db.String(10), nullable=False)  # 'stock' | 'crypto'
    quantity = db.Column(db.Float, nullable=False)
    buyPrice = db.Column(db.Float, nullable=False)
    buyDate = db.Column(db.Date, nullable=False)


class WatchlistItem(db.Model):
    """FR-5.1-5.2: stretch goal, unheld assets tracked for signal alerts."""
    __tablename__ = "tbl_WatchlistItem"

    watchlistId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey("tbl_User.userId"), nullable=False)
    assetSymbol = db.Column(db.String(20), nullable=False)
    assetType = db.Column(db.String(10), nullable=False)
    dateAdded = db.Column(db.DateTime, default=datetime.utcnow)


class SentimentCache(db.Model):
    """FR-3.2 support: caches computed sentiment scores per asset/day so
    repeated signal generation calls don't re-hit NewsAPI/Reddit rate limits."""
    __tablename__ = "tbl_SentimentCache"

    cacheId = db.Column(db.Integer, primary_key=True)
    assetSymbol = db.Column(db.String(20), nullable=False)
    sourceDate = db.Column(db.Date, nullable=False)
    sentimentScore = db.Column(db.Float, nullable=False)  # VADER compound, -1..1
    sampleSize = db.Column(db.Integer, default=0)  # number of headlines/posts scored
    computedAt = db.Column(db.DateTime, default=datetime.utcnow)


class Signal(db.Model):
    """FR-3.3, FR-3.4: one row per (asset, model, generation call)."""
    __tablename__ = "tbl_Signal"

    signalId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey("tbl_User.userId"), nullable=False)
    assetSymbol = db.Column(db.String(20), nullable=False)
    assetType = db.Column(db.String(10), nullable=False)  # 'stock' | 'crypto'
    generatedAt = db.Column(db.DateTime, default=datetime.utcnow)
    horizonDays = db.Column(db.Integer, default=3)
    modelUsed = db.Column(db.String(20), nullable=False)  # MODEL_BASELINE | MODEL_LSTM
    predictedDirection = db.Column(db.String(10), nullable=False)
    confidenceScore = db.Column(db.Float, nullable=False)
    # JSON-serialized list of {feature, contribution} — populated by
    # explainability_service.py via SHAP, previously permutation-importance.
    topContributingFeatures = db.Column(db.Text, nullable=True)
    featureSnapshot = db.Column(db.Text, nullable=True)  # JSON of raw feature row, needed for SHAP replay


class TrackedAsset(db.Model):
    """FR-7.1: assets the Admin actively monitors/refreshes — distinct from
    a user's Holdings (owned) or Watchlist (personal interest, FR-5). This
    is the admin-curated master list a solo operator would use to decide
    what the system spends its free-tier API budget on."""
    __tablename__ = "tbl_TrackedAsset"

    trackedAssetId = db.Column(db.Integer, primary_key=True)
    assetSymbol = db.Column(db.String(20), nullable=False, unique=True)
    assetType = db.Column(db.String(10), nullable=False)
    addedAt = db.Column(db.DateTime, default=datetime.utcnow)


class AdminConfig(db.Model):
    """FR-7.2: retrain schedule config. Deliberately configuration-only for
    this scope — there is no cron/Celery executor reading this value yet
    (SPMP explicitly cuts infra like that from Phase 3's 8-hour budget).
    Single-row table (solo/single-admin deployment per SRS 2.2)."""
    __tablename__ = "tbl_AdminConfig"

    configId = db.Column(db.Integer, primary_key=True)
    retrainIntervalDays = db.Column(db.Integer, default=1)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow)


class SignalOutcome(db.Model):
    """FR-6.2 feedback loop support: caches the resolved actual direction
    for a past Signal once horizonDays of future price data exists, so the
    dashboard doesn't recompute this from scratch on every page load.
    Deliberately per-signal, not aggregated — an aggregate hit-rate number
    is exactly the raw-accuracy headline the Honesty Framework forbids
    (SRS NFR-6); this stays a per-signal review list, resolved status only.
    """
    __tablename__ = "tbl_SignalOutcome"

    signalOutcomeId = db.Column(db.Integer, primary_key=True)
    signalId = db.Column(db.Integer, db.ForeignKey("tbl_Signal.signalId"), nullable=False, unique=True)
    actualDirection = db.Column(db.String(10), nullable=False)
    wasCorrect = db.Column(db.Boolean, nullable=False)
    resolvedAt = db.Column(db.DateTime, default=datetime.utcnow)


class BacktestResult(db.Model):
    """FR-4.1-4.3: honesty-framework metrics only — no raw accuracy field by design."""
    __tablename__ = "tbl_BacktestResult"

    backtestId = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey("tbl_User.userId"), nullable=False)
    assetSymbol = db.Column(db.String(20), nullable=False)
    modelUsed = db.Column(db.String(20), nullable=False)
    rangeStart = db.Column(db.Date, nullable=False)
    rangeEnd = db.Column(db.Date, nullable=False)
    sharpeRatio = db.Column(db.Float, nullable=False)
    winRate = db.Column(db.Float, nullable=False)
    maxDrawdown = db.Column(db.Float, nullable=False)
    totalTrades = db.Column(db.Integer, nullable=False)
    equityCurve = db.Column(db.Text, nullable=True)  # JSON list, for dashboard charting (FR-6.2)
    runAt = db.Column(db.DateTime, default=datetime.utcnow)
