"""
Module      : main.py
Date        : 2026-09-11
Author      : Dhruv
Modification History:
    2026-09-11 - Modernized TradeSage AI API using FastAPI and standard SQLAlchemy 2.0.
                 Features interactive Swagger UI (/docs), strict Pydantic schemas,
                 asynchronous request support, and full frontend compatibility.
Synopsis:
    FastAPI application entry point for TradeSage AI trading intelligence platform.
    Serves REST endpoints for Auth, Portfolio, Signal Engine, Backtesting,
    Watchlists, and Admin settings. Mounts static frontend files at /static.

Globals accessed/modified:
    G-ModelCache: in-memory cache of trained ML models keyed by (assetSymbol, dateStr).
"""

import io
import json
import os
from datetime import date, datetime
from typing import Optional, List, Dict, Any

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

import admin_service
import auth_service
import portfolio_service
import price_service
import sentiment_service
import watchlist_service
from backtesting_service import runBacktest
from feature_pipeline import buildFeatureFrame, labelDirection
from lstm_model import WINDOW_SIZE_DEFAULT, buildSequenceWindows, trainLstm
from models import (
    db,
    engine,
    SessionLocal,
    getDb,
    initDb,
    User,
    Signal,
    BacktestResult,
    TrackedAsset,
    AdminConfig,
    MODEL_BASELINE,
    MODEL_LSTM,
)
from schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    HoldingCreateRequest,
    PortfolioResponse,
    SignalResponse,
    BacktestRequest,
    BacktestResponse,
    WatchlistCreateRequest,
    TrackedAssetCreateRequest,
    AdminConfigRequest,
)
from signal_engine import trainRandomForestBaseline
from signal_service import generateSignal

from contextlib import asynccontextmanager

# Configuration constants
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-production")
SESSION_COOKIE_NAME = "session"
CLASS_NAMES = ["down", "neutral", "up"]
G_ModelCache: Dict[Any, Any] = {}

# Session serializer
G_Serializer = URLSafeTimedSerializer(SECRET_KEY, salt="tradesage-auth-session")


def seedDemoUser():
    """Ensures a default demo user exists for immediate out-of-the-box terminal evaluation."""
    from werkzeug.security import generate_password_hash
    db = SessionLocal()
    try:
        demo = db.query(User).filter_by(email="trader@tradesage.ai").first()
        if not demo:
            demoUser = User(
                email="trader@tradesage.ai",
                passwordHash=generate_password_hash("Password123!")
            )
            db.add(demoUser)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(appInstance: FastAPI):
    """Initializes database tables on startup and seeds default demo credentials."""
    initDb()
    seedDemoUser()
    yield


# FastAPI App instantiation with rich Swagger / OpenAPI metadata
app = FastAPI(
    title="TradeSage AI — Trading Intelligence Terminal API",
    description="""
    **TradeSage AI** algorithmic trading platform and portfolio intelligence engine.
    
    ### Key Features:
    * **Dual-Model ML Signal Engine**: Random Forest baseline vs. Deep LSTM network with SHAP explainability.
    * **FinBERT / VADER NLP Sentiment Analysis**: Market news sentiment evaluation.
    * **Quantitative Backtesting Engine**: Sharpe ratio, maximum drawdown, and simulated equity curve analytics.
    * **Portfolio Tracker & Relational Ledger**: ACID-compliant stock and cryptocurrency portfolio tracker.
    * **CHARUSAT CE363 Compliant**: Built with standard table naming and strict relational architecture.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration supporting credentials from local dev servers
allowedOrigins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
customOrigin = os.environ.get("DASHBOARD_ORIGIN")
if customOrigin and customOrigin not in allowedOrigins:
    allowedOrigins.append(customOrigin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowedOrigins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static frontend directory
frontendDir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontendDir):
    app.mount("/static", StaticFiles(directory=frontendDir), name="static")


@app.get("/", include_in_schema=False)
def rootRedirect():
    """Redirects base URL directly to dashboard."""
    return RedirectResponse(url="/static/dashboard.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Silently handles browser favicon requests."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Authentication Dependency ---

def getCurrentUser(request: Request, dbSession: Session = Depends(getDb)) -> User:
    """Extracts and verifies the authenticated user from the signed session cookie or Bearer token."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    authHeader = request.headers.get("Authorization")
    if not token and authHeader and authHeader.startswith("Bearer "):
        token = authHeader.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )

    try:
        data = G_Serializer.loads(token, max_age=86400 * 7)  # 7-day session validity
        userId = data.get("userId")
        user = dbSession.get(User, int(userId))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    except (BadSignature, SignatureExpired, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalid or expired. Please log in again.",
        )


# =====================================================================
# 1. AUTHENTICATION MODULE (FR-1)
# =====================================================================

@app.post("/api/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def register(body: UserRegisterRequest, response: Response, dbSession: Session = Depends(getDb)):
    """Registers a new user account with secure password hashing."""
    try:
        newUser = auth_service.registerUser(dbSession, body.email, body.password)
    except ValueError as registrationError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(registrationError))

    token = G_Serializer.dumps({"userId": newUser.userId, "email": newUser.email})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return {"userId": newUser.userId, "email": newUser.email}


@app.post("/api/login", response_model=UserResponse, tags=["Authentication"])
def login(body: UserLoginRequest, response: Response, dbSession: Session = Depends(getDb)):
    """Authenticates user credentials and creates a secure session cookie."""
    user = auth_service.verifyLogin(dbSession, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = G_Serializer.dumps({"userId": user.userId, "email": user.email})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return {"userId": user.userId, "email": user.email}


@app.post("/api/logout", tags=["Authentication"])
def logout(response: Response, currentUser: User = Depends(getCurrentUser)):
    """Clears user session and logs out."""
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"status": "logged out"}


# =====================================================================
# 2. PORTFOLIO MODULE (FR-2)
# =====================================================================

@app.post("/api/holdings", status_code=status.HTTP_201_CREATED, tags=["Portfolio Management"])
def addHolding(
    body: HoldingCreateRequest,
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Records a new asset holding position in the user's portfolio."""
    holding = portfolio_service.addHolding(
        dbSession,
        currentUser.userId,
        body.assetSymbol,
        body.assetType,
        body.quantity,
        body.buyPrice,
        body.buyDate,
    )
    return {"holdingId": holding.holdingId}


@app.post("/api/holdings/import", tags=["Portfolio Management"])
async def importHoldings(
    file: UploadFile = File(...),
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Imports asset holdings in bulk from an uploaded CSV file."""
    content = await file.read()
    result = portfolio_service.importHoldingsFromCsv(
        dbSession, currentUser.userId, io.BytesIO(content)
    )
    return result


@app.get("/api/portfolio", response_model=PortfolioResponse, tags=["Portfolio Management"])
def getPortfolio(
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Calculates live portfolio valuation, total PnL, and unrealized gains across all holdings."""
    result = portfolio_service.getPortfolioPnl(dbSession, currentUser.userId)
    return {
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
    }


@app.get("/api/portfolio/comparison", tags=["Portfolio Management"])
def getPortfolioComparison(
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """FR-6.3: Compares aggregate portfolio performance between Stocks and Cryptocurrencies."""
    result = portfolio_service.getPortfolioPnl(dbSession, currentUser.userId)
    byType = {"stock": {"totalPnl": 0.0, "holdingCount": 0}, "crypto": {"totalPnl": 0.0, "holdingCount": 0}}
    for h in result["holdings"]:
        bucket = byType.setdefault(h["holding"].assetType, {"totalPnl": 0.0, "holdingCount": 0})
        bucket["totalPnl"] += h["unrealizedPnl"]
        bucket["holdingCount"] += 1
    return byType


# =====================================================================
# 3. SIGNAL ENGINE MODULE (FR-3)
# =====================================================================

@app.get("/api/signal", response_model=SignalResponse, tags=["Signal Engine (ML)"])
def getSignal(
    assetSymbol: str = Query(..., description="Ticker symbol (e.g. AAPL, BTC-USD)"),
    assetType: str = Query("stock", description="Asset class ('stock' or 'crypto')"),
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """
    Executes live ML inference using Random Forest baseline and Deep LSTM networks.
    Computes directional confidence (UP, DOWN, NEUTRAL) and SHAP feature importance.
    """
    priceDf = price_service.getHistoricalPrices(assetSymbol, assetType)
    sentimentScore = sentiment_service.getSentimentForAsset(
        assetSymbol, assetType, date.today(), dbSession
    )

    rfModel, rfBackground, lstmModel, lstmBackground, featureNames = _getOrTrainModels(
        assetSymbol, priceDf, sentimentScore
    )

    signalRows = generateSignal(
        dbSession,
        currentUser.userId,
        assetSymbol,
        assetType,
        priceDf,
        sentimentScore=sentimentScore,
        rfModel=rfModel,
        rfBackground=rfBackground,
        lstmModel=lstmModel,
        lstmBackground=lstmBackground,
        featureNames=featureNames,
    )

    # Resolve past signal outcomes with freshly ingested price data (FR-6.2)
    watchlist_service.resolveSignalOutcomes(dbSession, assetSymbol, priceDf)

    return {
        "assetSymbol": assetSymbol,
        "assetType": assetType,
        "signals": [
            {
                "modelUsed": row.modelUsed,
                "predictedDirection": row.predictedDirection,
                "confidenceScore": row.confidenceScore,
                "topContributingFeatures": json.loads(row.topContributingFeatures) if row.topContributingFeatures else [],
                "horizonDays": row.horizonDays,
            }
            for row in signalRows
        ],
    }


@app.get("/api/signal-history", tags=["Signal Engine (ML)"])
def getSignalHistory(
    assetSymbol: str = Query(..., description="Ticker symbol to query"),
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """FR-6.2 Feedback loop: Fetches historical signals and their actual resolved market outcomes."""
    return watchlist_service.getSignalHistory(dbSession, currentUser.userId, assetSymbol)


# =====================================================================
# 4. QUANTITATIVE BACKTESTING MODULE (FR-4)
# =====================================================================

@app.post("/api/backtest", response_model=BacktestResponse, tags=["Backtesting Engine"])
def backtest(
    body: BacktestRequest,
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """
    Simulates trading strategy performance against historical signals.
    Returns defensive Honesty-Framework metrics: Sharpe ratio, win rate, max drawdown, and equity curves.
    """
    signalRowsQuery = (
        dbSession.query(Signal)
        .filter_by(userId=currentUser.userId, assetSymbol=body.assetSymbol, modelUsed=body.modelUsed)
        .order_by(Signal.generatedAt)
        .all()
    )
    if len(signalRowsQuery) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough signal history yet to backtest (need 2+ past signals for this asset and model).",
        )

    signalSeries = pd.Series(
        [row.predictedDirection for row in signalRowsQuery],
        index=pd.DatetimeIndex([row.generatedAt.date() for row in signalRowsQuery]),
    )
    rangeStart = signalRowsQuery[0].generatedAt.date()
    rangeEnd = date.today()
    priceDf = price_service.getHistoricalPrices(body.assetSymbol, body.assetType)
    priceSeries = priceDf["close"]

    metrics = runBacktest(priceSeries, signalSeries, horizonDays=body.horizonDays)

    resultRow = BacktestResult(
        userId=currentUser.userId,
        assetSymbol=body.assetSymbol,
        modelUsed=body.modelUsed,
        rangeStart=rangeStart,
        rangeEnd=rangeEnd,
        sharpeRatio=metrics["sharpeRatio"],
        winRate=metrics["winRate"],
        maxDrawdown=metrics["maxDrawdown"],
        totalTrades=metrics["totalTrades"],
        equityCurve=json.dumps(metrics["equityCurve"]),
    )
    dbSession.add(resultRow)
    dbSession.commit()

    return {
        "sharpeRatio": metrics["sharpeRatio"],
        "winRate": metrics["winRate"],
        "maxDrawdown": metrics["maxDrawdown"],
        "totalTrades": metrics["totalTrades"],
        "equityCurve": metrics["equityCurve"],
    }


# =====================================================================
# 5. WATCHLIST & ALERTS MODULE (FR-5)
# =====================================================================

@app.get("/api/watchlist", tags=["Watchlist & Alerts"])
def getWatchlist(
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Retrieves all monitored watchlist items with real-time signal alerts."""
    return watchlist_service.getWatchlistWithAlerts(dbSession, currentUser.userId)


@app.post("/api/watchlist", status_code=status.HTTP_201_CREATED, tags=["Watchlist & Alerts"])
def addWatchlistItem(
    body: WatchlistCreateRequest,
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Adds an asset to the user's active watchlist."""
    item = watchlist_service.addToWatchlist(
        dbSession, currentUser.userId, body.assetSymbol, body.assetType
    )
    return {"watchlistId": item.watchlistId}


@app.delete("/api/watchlist/{watchlistId}", tags=["Watchlist & Alerts"])
def deleteWatchlistItem(
    watchlistId: int,
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Removes an asset from the user's watchlist."""
    removed = watchlist_service.removeFromWatchlist(dbSession, currentUser.userId, watchlistId)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist item not found")
    return {"status": "removed"}


# =====================================================================
# 6. ADMIN & CONFIG MODULE (FR-7)
# =====================================================================

@app.get("/api/admin/tracked-assets", tags=["Admin Panel"])
def listTrackedAssets(
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Lists master tracked assets monitored across the platform."""
    assets = admin_service.listTrackedAssets(dbSession)
    return [{"trackedAssetId": a.trackedAssetId, "assetSymbol": a.assetSymbol, "assetType": a.assetType} for a in assets]


@app.post("/api/admin/tracked-assets", status_code=status.HTTP_201_CREATED, tags=["Admin Panel"])
def addTrackedAsset(
    body: TrackedAssetCreateRequest,
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Adds a new asset to the master tracking list."""
    asset = admin_service.addTrackedAsset(dbSession, body.assetSymbol, body.assetType)
    return {"trackedAssetId": asset.trackedAssetId}


@app.delete("/api/admin/tracked-assets/{trackedAssetId}", tags=["Admin Panel"])
def deleteTrackedAsset(
    trackedAssetId: int,
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Deletes an asset from the master tracking list."""
    removed = admin_service.removeTrackedAsset(dbSession, trackedAssetId)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked asset not found")
    return {"status": "removed"}


@app.get("/api/admin/config", tags=["Admin Panel"])
def getAdminConfig(
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Retrieves current model retraining configuration."""
    config = admin_service.getRetrainConfig(dbSession)
    return {"retrainIntervalDays": config.retrainIntervalDays}


@app.post("/api/admin/config", tags=["Admin Panel"])
def setAdminConfig(
    body: AdminConfigRequest,
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Updates model retraining interval days."""
    config = admin_service.setRetrainInterval(dbSession, body.retrainIntervalDays)
    return {"retrainIntervalDays": config.retrainIntervalDays}


@app.get("/api/admin/health", tags=["Admin Panel"])
def getDataSourceHealth(
    currentUser: User = Depends(getCurrentUser),
    dbSession: Session = Depends(getDb),
):
    """Checks latency and connectivity status of external financial data feeds."""
    return admin_service.checkDataSourceHealth(dbSession)


# =====================================================================
# INTERNAL MODEL CACHE HELPER
# =====================================================================

def _getOrTrainModels(assetSymbol: str, priceDf: pd.DataFrame, sentimentScore: float):
    """
    Retrieves trained models from process-lifetime cache or trains baseline RF and LSTM.
    Avoids repetitive ~17s training on multiple requests for the same asset today.
    """
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
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)
