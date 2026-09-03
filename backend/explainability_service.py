"""
Module      : explainability_service.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Initial version. Replaces the permutation-importance
                 approximation that was used as a Phase-2 placeholder.
                 Implements FR-3.4 (confidence score + top contributing
                 features via SHAP) for both models compared in FR-3.3.
Synopsis:
    Given a trained model (RandomForest baseline or PyTorch LSTM) and a
    feature instance, returns the top contributing features for that
    specific prediction using SHAP, so the Signal Engine is never a black
    box (NFR-3).

    Design notes (why two explainers, not one):
    - RandomForest -> shap.TreeExplainer. Exact (not sampled/approximate)
      and fast for tree ensembles, so there's no reason to use a slower
      general-purpose explainer here.
    - LSTM (PyTorch) -> shap.GradientExplainer, NOT DeepExplainer. This was
      a real finding during smoke testing: DeepExplainer has no built-in
      rule for nn.LSTM ("unrecognized nn.Module: LSTM") and its additivity
      check failed as a result (max diff 0.0102 > 0.01 tolerance).
      GradientExplainer is architecture-agnostic (gradient-based, no
      per-layer rule table) and passed cleanly on the same shallow
      1-layer/32-unit model, so it's the correct choice here, not a
      workaround.
    - A shared background sample (reference distribution) is required by
      both explainers; callers pass a small representative slice of
      training data (recommended: 50-100 rows) rather than the full set,
      to keep SHAP computation fast enough for on-demand signal generation.

Functions:
    getTopContributingFeatures(modelType, model, backgroundData, instanceData,
                                featureNames, predictedClassIndex, topN)
        -> list[dict] : [{"feature": str, "contribution": float}, ...]
        Dispatches to the correct explainer based on modelType and returns
        the topN features ranked by absolute SHAP contribution to the
        predicted class.

    explainRandomForest(model, backgroundData, instanceRow, featureNames,
                         predictedClassIndex, topN)
        -> list[dict] : as above, for MODEL_BASELINE.

    explainLstm(model, backgroundSequences, instanceSequence, featureNames,
                predictedClassIndex, topN)
        -> list[dict] : as above, for MODEL_LSTM. SHAP values are computed
        per-timestep-per-feature, then aggregated (sum of abs values across
        the 20-day window) into one contribution score per feature, since
        the Signal entity stores one ranked feature list per prediction,
        not a per-day breakdown.

Globals accessed/modified: None (stateless service; no G- globals).
"""

import numpy as np
import shap
import torch

from models import MODEL_BASELINE, MODEL_LSTM

DEFAULT_TOP_N = 5  # ALL_CAPS constant per CHARUSAT standard


def explainRandomForest(model, backgroundData, instanceRow, featureNames,
                         predictedClassIndex, topN=DEFAULT_TOP_N):
    treeExplainer = shap.TreeExplainer(model, backgroundData)
    rawShapValues = treeExplainer.shap_values(instanceRow.reshape(1, -1))

    # SHAP's multiclass output shape varies by version:
    #   - older shap: list of (nSamples, nFeatures) arrays, one per class
    #   - shap>=0.45: single ndarray (nSamples, nFeatures, nClasses)
    # Both are normalized to a single (nFeatures,) row for the predicted class.
    if isinstance(rawShapValues, list):
        classShapRow = rawShapValues[predictedClassIndex][0]
    else:
        arr = np.asarray(rawShapValues)
        if arr.ndim == 3:
            classShapRow = arr[0, :, predictedClassIndex]
        else:
            # binary/regression fallback shape: (nSamples, nFeatures)
            classShapRow = arr[0]

    return _rankTopFeatures(classShapRow, featureNames, topN)


def explainLstm(model, backgroundSequences, instanceSequence, featureNames,
                 predictedClassIndex, topN=DEFAULT_TOP_N):
    model.eval()
    backgroundTensor = torch.tensor(backgroundSequences, dtype=torch.float32)
    instanceTensor = torch.tensor(
        instanceSequence.reshape(1, *instanceSequence.shape), dtype=torch.float32
    )

    gradientExplainer = shap.GradientExplainer(model, backgroundTensor)
    rawShapValues = gradientExplainer.shap_values(instanceTensor)

    # rawShapValues shape: (nClasses, 1, seqLen, nFeatures) or (1, seqLen, nFeatures, nClasses)
    # depending on shap version output convention — normalize both to (seqLen, nFeatures).
    perTimestepValues = _extractClassSlice(rawShapValues, predictedClassIndex)

    # Aggregate across the 20-day window: sum of absolute contribution per feature.
    aggregatedPerFeature = np.abs(perTimestepValues).sum(axis=0)

    return _rankTopFeatures(aggregatedPerFeature, featureNames, topN)


def getTopContributingFeatures(modelType, model, backgroundData, instanceData,
                                featureNames, predictedClassIndex, topN=DEFAULT_TOP_N):
    if modelType == MODEL_BASELINE:
        return explainRandomForest(
            model, backgroundData, instanceData, featureNames,
            predictedClassIndex, topN
        )
    elif modelType == MODEL_LSTM:
        return explainLstm(
            model, backgroundData, instanceData, featureNames,
            predictedClassIndex, topN
        )
    else:
        raise ValueError(f"Unknown modelType for explainability: {modelType}")


# --- internal helpers -------------------------------------------------

def _rankTopFeatures(contributionArray, featureNames, topN):
    contributionArray = np.asarray(contributionArray).flatten()
    rankedIndices = np.argsort(np.abs(contributionArray))[::-1][:topN]
    return [
        {"feature": featureNames[i], "contribution": float(contributionArray[i])}
        for i in rankedIndices
    ]


def _extractClassSlice(rawShapValues, predictedClassIndex):
    if isinstance(rawShapValues, list):
        # list of (1, seqLen, nFeatures) arrays, one per class
        return rawShapValues[predictedClassIndex][0]
    arr = np.asarray(rawShapValues)
    if arr.ndim == 4 and arr.shape[-1] > 1:
        # (1, seqLen, nFeatures, nClasses)
        return arr[0, :, :, predictedClassIndex]
    # (1, seqLen, nFeatures) single-output fallback
    return arr[0]
