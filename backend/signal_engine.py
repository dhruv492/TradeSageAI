"""
Module      : signal_engine.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated (rebuild session). Implements the baseline half
                 of FR-3.3.
Synopsis:
    RandomForest baseline classifier over the technical + sentiment feature
    set, predicting direction (up/down/neutral). Exists alongside the LSTM
    (lstm_model.py) as the side-by-side comparison FR-3.3 requires — a
    baseline model ships first (Phase 1) precisely so there's always a
    working fallback if LSTM integration slips (see SPMP risk register).

Functions:
    trainRandomForestBaseline(featureFrame, labelSeries, numEstimators, randomState)
        -> sklearn.ensemble.RandomForestClassifier
        featureFrame/labelSeries must share an index; rows with NaN labels
        (tail of the series, see feature_pipeline.labelDirection) are dropped.
    predictDirection(model, featureRow) -> dict
        -> {"direction": str, "confidence": float, "classIndex": int}
        confidence = predicted class's probability from predict_proba.

Globals accessed/modified: None.
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier

NUM_ESTIMATORS_DEFAULT = 100  # ALL_CAPS constant per CHARUSAT standard
RANDOM_STATE_DEFAULT = 42


def trainRandomForestBaseline(featureFrame, labelSeries,
                               numEstimators=NUM_ESTIMATORS_DEFAULT,
                               randomState=RANDOM_STATE_DEFAULT):
    alignedLabels = labelSeries.reindex(featureFrame.index).dropna()
    alignedFeatures = featureFrame.loc[alignedLabels.index]

    model = RandomForestClassifier(n_estimators=numEstimators, random_state=randomState)
    model.fit(alignedFeatures.values, alignedLabels.values)
    return model


def predictDirection(model, featureRow):
    featureArray = np.asarray(featureRow).reshape(1, -1)
    probabilities = model.predict_proba(featureArray)[0]
    classIndex = int(np.argmax(probabilities))
    return {
        "direction": model.classes_[classIndex],
        "confidence": float(probabilities[classIndex]),
        "classIndex": classIndex,
    }
