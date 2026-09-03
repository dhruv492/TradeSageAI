"""
Module      : feature_pipeline.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated (rebuild session). Implements FR-3.1.
Synopsis:
    Computes technical indicators (RSI, MACD, SMA, volume-change) from a
    price/volume history and builds the per-day feature matrix consumed by
    both the RandomForest baseline and the LSTM. Also labels historical
    direction (up/down/neutral) for supervised training, using a neutral
    band so tiny moves aren't forced into up/down (avoids training the
    model to chase noise).

Functions:
    computeRsi(closePrices, windowSize) -> pandas.Series
    computeMacd(closePrices, fastSpan, slowSpan, signalSpan) -> pandas.DataFrame (macd, signalLine)
    computeSma(closePrices, windowSize) -> pandas.Series
    computeVolumeChange(volumeSeries) -> pandas.Series (pct change)
    buildFeatureFrame(priceDf) -> pandas.DataFrame
        priceDf: DataFrame with columns ['close', 'volume'], DatetimeIndex
        returns feature columns: rsi, macd, sma, volumeChange
    labelDirection(closePrices, horizonDays, neutralBandPct) -> pandas.Series
        values in {'up','down','neutral'}; neutralBandPct default 0.5%
        forward return magnitude below this band is labeled 'neutral'.

Globals accessed/modified: None.
"""

import numpy as np
import pandas as pd

RSI_WINDOW_DEFAULT = 14        # ALL_CAPS constants per CHARUSAT standard
MACD_FAST_SPAN_DEFAULT = 12
MACD_SLOW_SPAN_DEFAULT = 26
MACD_SIGNAL_SPAN_DEFAULT = 9
SMA_WINDOW_DEFAULT = 20
HORIZON_DAYS_DEFAULT = 3
NEUTRAL_BAND_PCT_DEFAULT = 0.005  # 0.5%


def computeRsi(closePrices, windowSize=RSI_WINDOW_DEFAULT):
    priceDelta = closePrices.diff()
    gains = priceDelta.clip(lower=0)
    losses = -priceDelta.clip(upper=0)
    avgGain = gains.rolling(windowSize).mean()
    avgLoss = losses.rolling(windowSize).mean()
    relativeStrength = avgGain / avgLoss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relativeStrength))
    return rsi.fillna(50)  # neutral RSI where undefined (start of series / zero loss)


def computeMacd(closePrices, fastSpan=MACD_FAST_SPAN_DEFAULT,
                 slowSpan=MACD_SLOW_SPAN_DEFAULT, signalSpan=MACD_SIGNAL_SPAN_DEFAULT):
    fastEma = closePrices.ewm(span=fastSpan, adjust=False).mean()
    slowEma = closePrices.ewm(span=slowSpan, adjust=False).mean()
    macdLine = fastEma - slowEma
    signalLine = macdLine.ewm(span=signalSpan, adjust=False).mean()
    return pd.DataFrame({"macd": macdLine, "macdSignal": signalLine})


def computeSma(closePrices, windowSize=SMA_WINDOW_DEFAULT):
    return closePrices.rolling(windowSize).mean()


def computeVolumeChange(volumeSeries):
    return volumeSeries.pct_change().replace([np.inf, -np.inf], 0).fillna(0)


def buildFeatureFrame(priceDf):
    rsi = computeRsi(priceDf["close"])
    macdDf = computeMacd(priceDf["close"])
    sma = computeSma(priceDf["close"])
    volumeChange = computeVolumeChange(priceDf["volume"])

    featureFrame = pd.DataFrame({
        "rsi": rsi,
        "macd": macdDf["macd"],
        "sma": sma,
        "volumeChange": volumeChange,
    }, index=priceDf.index)

    return featureFrame.dropna()


def labelDirection(closePrices, horizonDays=HORIZON_DAYS_DEFAULT,
                    neutralBandPct=NEUTRAL_BAND_PCT_DEFAULT):
    forwardReturn = closePrices.shift(-horizonDays) / closePrices - 1

    labels = pd.Series("neutral", index=closePrices.index)
    labels[forwardReturn > neutralBandPct] = "up"
    labels[forwardReturn < -neutralBandPct] = "down"
    labels[forwardReturn.isna()] = np.nan  # can't label the last horizonDays rows
    return labels
