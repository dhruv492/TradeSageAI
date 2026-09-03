"""
Module      : watchlist_service.py
Date        : 2026-08-30
Author      : Dhruv
Modification History:
    2026-08-30 - Initial version, Phase 3.
Synopsis:
    Two responsibilities, both Phase 3 / stretch scope per SPMP:
    1. Watchlist CRUD + "did this asset's signal just change" check (FR-5).
       "Alert" here means an in-app flag returned alongside the watchlist
       item, not an email/push notification — no notification
       infrastructure exists in this solo-dev scope, and building one was
       not worth the Phase 3 hours budget vs. the rest of the checklist.
    2. Resolving past signals against what actually happened (FR-6.2 feedback
       loop), reusing feature_pipeline.labelDirection's up/down/neutral
       banding so "did the signal turn out right" uses the exact same
       definition of correct that the model was trained against — a
       different threshold here would make the feedback loop misleading
       rather than informative.

Functions:
    addToWatchlist(dbSession, userId, assetSymbol, assetType) -> WatchlistItem
    removeFromWatchlist(dbSession, userId, watchlistId) -> bool
    getWatchlistWithAlerts(dbSession, userId) -> list[dict]
    resolveSignalOutcomes(dbSession, assetSymbol, priceDf) -> int (rows resolved)
    getSignalHistory(dbSession, userId, assetSymbol) -> list[dict]

Globals accessed/modified: None.
"""

from datetime import datetime

from models import db, Signal, SignalOutcome, WatchlistItem
from feature_pipeline import labelDirection, HORIZON_DAYS_DEFAULT


def addToWatchlist(dbSession, userId, assetSymbol, assetType):
    existing = dbSession.query(WatchlistItem).filter_by(
        userId=userId, assetSymbol=assetSymbol,
    ).first()
    if existing:
        return existing
    item = WatchlistItem(userId=userId, assetSymbol=assetSymbol, assetType=assetType)
    dbSession.add(item)
    dbSession.commit()
    return item


def removeFromWatchlist(dbSession, userId, watchlistId):
    item = dbSession.query(WatchlistItem).filter_by(
        watchlistId=watchlistId, userId=userId,
    ).first()
    if item is None:
        return False
    dbSession.delete(item)
    dbSession.commit()
    return True


def getWatchlistWithAlerts(dbSession, userId):
    """FR-5.2: 'notify on signal change' resolved as comparing the two most
    recent persisted Signal rows (same model) for each watchlisted asset.
    changed=True means the last two signals disagree on direction."""
    items = dbSession.query(WatchlistItem).filter_by(userId=userId).all()
    result = []
    for item in items:
        recentSignals = (
            dbSession.query(Signal)
            .filter_by(userId=userId, assetSymbol=item.assetSymbol)
            .order_by(Signal.generatedAt.desc())
            .limit(2)
            .all()
        )
        changed = False
        latestDirection = None
        if recentSignals:
            latestDirection = recentSignals[0].predictedDirection
            if len(recentSignals) == 2:
                changed = recentSignals[0].predictedDirection != recentSignals[1].predictedDirection
        result.append({
            "watchlistId": item.watchlistId,
            "assetSymbol": item.assetSymbol,
            "assetType": item.assetType,
            "latestSignal": latestDirection,
            "signalChanged": changed,
        })
    return result


def resolveSignalOutcomes(dbSession, assetSymbol, priceDf):
    """FR-6.2: for every past Signal on this asset that doesn't yet have a
    SignalOutcome, check whether horizonDays of future price data now
    exists; if so, compute the actual direction and persist whether the
    signal was correct. Returns how many rows were newly resolved."""
    unresolvedSignals = (
        dbSession.query(Signal)
        .filter_by(assetSymbol=assetSymbol)
        .outerjoin(SignalOutcome, Signal.signalId == SignalOutcome.signalId)
        .filter(SignalOutcome.signalOutcomeId.is_(None))
        .all()
    )
    if not unresolvedSignals:
        return 0

    labels = labelDirection(priceDf["close"], horizonDays=HORIZON_DAYS_DEFAULT)
    resolvedCount = 0
    for signalRow in unresolvedSignals:
        signalDate = signalRow.generatedAt.date()
        matchingLabelDates = [d for d in labels.index if d.date() == signalDate]
        if not matchingLabelDates:
            continue  # asset had no trading data on that date (weekend/holiday) — skip, don't guess
        actualDirection = labels.loc[matchingLabelDates[0]]
        if actualDirection != actualDirection:  # NaN check — not enough future data yet
            continue
        dbSession.add(SignalOutcome(
            signalId=signalRow.signalId,
            actualDirection=actualDirection,
            wasCorrect=(actualDirection == signalRow.predictedDirection),
        ))
        resolvedCount += 1
    dbSession.commit()
    return resolvedCount


def getSignalHistory(dbSession, userId, assetSymbol):
    """FR-6.2 read side: past signals for one asset, joined with resolved
    outcome where available. Returned as a per-signal list — deliberately
    NOT reduced to a single accuracy percentage anywhere in this function
    or its caller (Honesty Framework, NFR-6)."""
    rows = (
        dbSession.query(Signal, SignalOutcome)
        .outerjoin(SignalOutcome, Signal.signalId == SignalOutcome.signalId)
        .filter(Signal.userId == userId, Signal.assetSymbol == assetSymbol)
        .order_by(Signal.generatedAt)
        .all()
    )
    return [
        {
            "generatedAt": signalRow.generatedAt.isoformat(),
            "modelUsed": signalRow.modelUsed,
            "predictedDirection": signalRow.predictedDirection,
            "confidenceScore": signalRow.confidenceScore,
            "actualDirection": outcomeRow.actualDirection if outcomeRow else None,
            "wasCorrect": outcomeRow.wasCorrect if outcomeRow else None,
            "status": "resolved" if outcomeRow else "pending",
        }
        for signalRow, outcomeRow in rows
    ]
