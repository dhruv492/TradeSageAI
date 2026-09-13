"""
Module      : schemas.py
Date        : 2026-09-11
Author      : Dhruv
Modification History:
    2026-09-11 - Created for FastAPI modernization. Provides strict Pydantic
                 schemas for request bodies and API response structures with
                 interactive Swagger /docs documentation.
Synopsis:
    Pydantic schemas adhering to CHARUSAT v1.0 coding standard. Validates
    incoming payloads for auth, portfolio, signals, backtesting, and admin.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# --- Auth Schemas ---

class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="User's email address", example="trader@tradesage.ai")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)", example="SecurePass123!")


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="Registered email address", example="trader@tradesage.ai")
    password: str = Field(..., description="Account password", example="SecurePass123!")


class UserResponse(BaseModel):
    userId: int = Field(..., description="Unique user ID")
    email: str = Field(..., description="User's email address")


# --- Portfolio Schemas ---

class HoldingCreateRequest(BaseModel):
    assetSymbol: str = Field(..., description="Ticker symbol (e.g. AAPL, BTC-USD)", example="AAPL")
    assetType: str = Field("stock", description="Asset type: 'stock' or 'crypto'", example="stock")
    quantity: float = Field(..., gt=0, description="Number of units purchased", example=10.0)
    buyPrice: float = Field(..., gt=0, description="Purchase price per unit in USD", example=180.50)
    buyDate: str = Field(..., description="Date of purchase (YYYY-MM-DD)", example="2026-08-01")


class PortfolioHoldingItem(BaseModel):
    assetSymbol: str
    assetType: str
    quantity: float
    livePrice: float
    unrealizedPnl: float
    unrealizedPnlPct: float


class PortfolioResponse(BaseModel):
    totalPnl: float
    holdings: List[PortfolioHoldingItem]


# --- Signal Engine Schemas ---

class SignalItem(BaseModel):
    modelUsed: str = Field(..., description="Model identifier: random_forest or lstm")
    predictedDirection: str = Field(..., description="Predicted direction: up, down, or neutral")
    confidenceScore: float = Field(..., description="Prediction confidence score (0.0 - 1.0)")
    topContributingFeatures: List[Dict[str, Any]] = Field(..., description="SHAP feature importance ranking")
    horizonDays: int = Field(3, description="Prediction horizon in days")


class SignalResponse(BaseModel):
    assetSymbol: str
    assetType: str
    signals: List[SignalItem]


# --- Backtest Schemas ---

class BacktestRequest(BaseModel):
    assetSymbol: str = Field(..., description="Ticker symbol to backtest", example="AAPL")
    modelUsed: str = Field("random_forest", description="ML model used: 'random_forest' or 'lstm'", example="random_forest")
    assetType: str = Field("stock", description="Asset type: 'stock' or 'crypto'", example="stock")
    horizonDays: int = Field(3, ge=1, le=30, description="Prediction horizon days", example=3)


class BacktestResponse(BaseModel):
    sharpeRatio: float = Field(..., description="Annualized Sharpe ratio")
    winRate: float = Field(..., description="Win rate percentage of completed trades")
    maxDrawdown: float = Field(..., description="Maximum peak-to-trough equity drawdown percentage")
    totalTrades: int = Field(..., description="Total simulated trade count")
    equityCurve: List[Dict[str, Any]] = Field(..., description="Simulated equity points over time")


# --- Watchlist Schemas ---

class WatchlistCreateRequest(BaseModel):
    assetSymbol: str = Field(..., description="Ticker symbol to monitor", example="NVDA")
    assetType: str = Field("stock", description="Asset type: 'stock' or 'crypto'", example="stock")


# --- Admin Panel Schemas ---

class TrackedAssetCreateRequest(BaseModel):
    assetSymbol: str = Field(..., description="Master monitored asset symbol", example="SPY")
    assetType: str = Field("stock", description="Asset type: 'stock' or 'crypto'", example="stock")


class AdminConfigRequest(BaseModel):
    retrainIntervalDays: int = Field(..., ge=1, le=30, description="Days between automated model retraining", example=1)
