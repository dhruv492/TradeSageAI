"""
Module      : sentiment_service.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated (rebuild session). Implements FR-3.2.
    (earlier session) - VADER's stock lexicon under-scores finance-specific
        language (e.g. "bearish", "bullish", "downgrade" scored ~neutral).
        Extended with a ~25-term finance lexicon on top of VADER rather than
        switching to FinBERT, to keep sentiment as a lightweight contributing
        feature (not the primary signal driver) — see project decision log.
Synopsis:
    Computes a sentiment score per asset from news headlines (stocks) or
    Reddit posts (crypto), using VADER extended with finance vocabulary,
    and persists results to SentimentCache so repeated signal-generation
    calls don't re-hit rate-limited free-tier APIs (NewsAPI, Reddit/PRAW).

    Fetchers are dependency-injected (headlineFetcher / postFetcher
    parameters) rather than hardcoded to the live NewsAPI/PRAW clients.
    This is deliberate: it keeps this module unit-testable without live
    API keys or network access, and the actual NewsAPI/PRAW client wiring
    lives in app.py's config, not here.

Functions:
    getFinanceLexicon() -> dict[str, float]
        ~25 finance terms with VADER-style valence scores, additive to VADER.
    scoreText(text, vaderAnalyzer) -> float
        Returns compound sentiment score in [-1, 1].
    getSentimentForAsset(assetSymbol, assetType, sourceDate, dbSession,
                          headlineFetcher=None, postFetcher=None)
        -> float
        Checks SentimentCache first; on miss, fetches (NewsAPI for stocks,
        Reddit for crypto), scores, caches, and returns the score.

Globals accessed/modified: None (dbSession passed explicitly, not global).
"""

import os
from datetime import date

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf

from models import SentimentCache

MIN_SAMPLE_SIZE_DEFAULT = 1  # ALL_CAPS constant per standard naming convention


def getFinanceLexicon():
    # Extends VADER's general-purpose lexicon with finance-specific terms
    # VADER under-scores or misses entirely (caught during smoke testing
    # against real headlines in the earlier session).
    return {
        "bullish": 2.5, "bearish": -2.5, "rally": 2.0, "selloff": -2.5,
        "sell-off": -2.5, "downgrade": -2.0, "upgrade": 2.0, "outperform": 2.0,
        "underperform": -2.0, "beat": 1.8, "miss": -1.8, "surge": 2.2,
        "plunge": -2.5, "tumble": -2.0, "soar": 2.3, "crash": -3.0,
        "recession": -2.0, "correction": -1.5, "breakout": 1.8,
        "overbought": -1.0, "oversold": 1.0, "short squeeze": 2.0,
        "hack": -2.5, "exploit": -2.5, "rug pull": -3.0, "liquidation": -2.0,
    }


def _buildAnalyzer():
    analyzer = SentimentIntensityAnalyzer()
    analyzer.lexicon.update(getFinanceLexicon())
    return analyzer


def scoreText(text, vaderAnalyzer):
    return vaderAnalyzer.polarity_scores(text)["compound"]


def _extractTitle(item):
    if isinstance(item, dict):
        content = item.get("content")
        if isinstance(content, dict) and content.get("title"):
            return content["title"]
        return item.get("title", "")
    return str(item)


def _defaultHeadlineFetcher(assetSymbol, sourceDate):
    """Fetches real headlines via NewsAPI if configured, or falls back to
    yfinance news stream for the symbol. Returns empty list on network failure."""
    newsApiKey = os.environ.get("NEWSAPI_KEY")
    if newsApiKey:
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={"q": assetSymbol, "pageSize": 10, "sortBy": "relevance", "apiKey": newsApiKey},
                timeout=4,
            )
            if resp.status_code == 200:
                data = resp.json()
                headlines = [a["title"] for a in data.get("articles", []) if a.get("title")]
                if headlines:
                    return headlines
        except Exception:
            pass

    # Zero-config live news fallback via yfinance
    try:
        ticker = yf.Ticker(assetSymbol)
        newsItems = ticker.news if hasattr(ticker, "news") and ticker.news else []
        headlines = [_extractTitle(item) for item in newsItems[:10]]
        headlines = [h.strip() for h in headlines if h and h.strip()]
        if headlines:
            return headlines
    except Exception:
        pass

    return []


def _defaultPostFetcher(assetSymbol, sourceDate):
    """Fetches crypto posts via Reddit/PRAW if configured, or falls back to
    crypto news via yfinance or Reddit public JSON. Returns empty list on failure."""
    clientId = os.environ.get("REDDIT_CLIENT_ID")
    clientSecret = os.environ.get("REDDIT_CLIENT_SECRET")
    if clientId and clientSecret:
        try:
            import praw
            reddit = praw.Reddit(
                client_id=clientId,
                client_secret=clientSecret,
                user_agent=os.environ.get("REDDIT_USER_AGENT", "tradesage-ai/1.0"),
            )
            subreddit = reddit.subreddit("CryptoCurrency")
            posts = [s.title for s in subreddit.search(assetSymbol, limit=10, time_filter="week")]
            if posts:
                return posts
        except Exception:
            pass

    # Fallback to yfinance ticker news (e.g. BTC-USD)
    try:
        yfSymbol = assetSymbol if assetSymbol.endswith("-USD") else f"{assetSymbol}-USD"
        ticker = yf.Ticker(yfSymbol)
        newsItems = ticker.news if hasattr(ticker, "news") and ticker.news else []
        headlines = [_extractTitle(item) for item in newsItems[:10]]
        headlines = [h.strip() for h in headlines if h and h.strip()]
        if headlines:
            return headlines
    except Exception:
        pass

    return []


def getSentimentForAsset(assetSymbol, assetType, sourceDate, dbSession,
                          headlineFetcher=None, postFetcher=None):
    cachedRow = (
        dbSession.query(SentimentCache)
        .filter_by(assetSymbol=assetSymbol, sourceDate=sourceDate)
        .first()
    )
    if cachedRow is not None:
        return cachedRow.sentimentScore

    headlineFetcher = headlineFetcher or _defaultHeadlineFetcher
    postFetcher = postFetcher or _defaultPostFetcher

    if assetType == "crypto":
        texts = postFetcher(assetSymbol, sourceDate)
    else:
        texts = headlineFetcher(assetSymbol, sourceDate)

    if not texts:
        sentimentScore = 0.0
        sampleSize = 0
    else:
        analyzer = _buildAnalyzer()
        scores = [scoreText(t, analyzer) for t in texts]
        sentimentScore = sum(scores) / len(scores)
        sampleSize = len(scores)

    newCacheRow = SentimentCache(
        assetSymbol=assetSymbol,
        sourceDate=sourceDate,
        sentimentScore=sentimentScore,
        sampleSize=sampleSize,
    )
    dbSession.add(newCacheRow)
    dbSession.commit()
    return sentimentScore
