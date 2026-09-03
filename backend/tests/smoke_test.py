import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import torch
import torch.nn as nn

from models import MODEL_BASELINE, MODEL_LSTM
from explainability_service import getTopContributingFeatures
from backtesting_service import runBacktest

np.random.seed(42)
FEATURE_NAMES = ["rsi", "macd", "sma", "volumeChange"]

# ---- 1. RandomForest + SHAP TreeExplainer ----
X = np.random.randn(200, len(FEATURE_NAMES))
y = np.random.choice(["up", "down", "neutral"], size=200)
rf = RandomForestClassifier(n_estimators=50, random_state=42).fit(X, y)
predictedClassIdx = list(rf.classes_).index(rf.predict(X[:1])[0])
rfExplanation = getTopContributingFeatures(
    MODEL_BASELINE, rf, X[:60], X[0], FEATURE_NAMES, predictedClassIdx, topN=3
)
print("RF SHAP top features:", rfExplanation)
assert len(rfExplanation) == 3 and all("feature" in f and "contribution" in f for f in rfExplanation)

# ---- 2. Shallow LSTM (1-layer/32-unit) + SHAP DeepExplainer ----
class ShallowLstm(nn.Module):
    def __init__(self, inputSize, hiddenSize=32, numClasses=3):
        super().__init__()
        self.lstm = nn.LSTM(inputSize, hiddenSize, batch_first=True)
        self.fc = nn.Linear(hiddenSize, numClasses)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

seqLen = 20
lstm = ShallowLstm(len(FEATURE_NAMES))
lstm.eval()
backgroundSeqs = np.random.randn(30, seqLen, len(FEATURE_NAMES)).astype(np.float32)
instanceSeq = np.random.randn(seqLen, len(FEATURE_NAMES)).astype(np.float32)
with torch.no_grad():
    pred = lstm(torch.tensor(instanceSeq).unsqueeze(0))
predictedClassIdxLstm = int(torch.argmax(pred, dim=1).item())

lstmExplanation = getTopContributingFeatures(
    MODEL_LSTM, lstm, backgroundSeqs, instanceSeq, FEATURE_NAMES, predictedClassIdxLstm, topN=3
)
print("LSTM SHAP top features:", lstmExplanation)
assert len(lstmExplanation) == 3

# ---- 3. Backtesting ----
dates = pd.bdate_range("2025-01-01", periods=120)
prices = pd.Series(100 * np.cumprod(1 + np.random.normal(0.0005, 0.01, len(dates))), index=dates)
signalDates = dates[::5]
signals = pd.Series(np.random.choice(["up", "down", "neutral"], size=len(signalDates)), index=signalDates)

result = runBacktest(prices, signals, horizonDays=3)
print("Backtest result:", {k: (v if k != "equityCurve" else f"[{len(v)} points]") for k, v in result.items()})
assert "sharpeRatio" in result and "winRate" in result and "maxDrawdown" in result
assert result["maxDrawdown"] <= 0
assert 0 <= result["winRate"] <= 1
assert "_debugDirectionalAccuracy" in result  # present internally, but caller must not surface it in UI

print("\nALL SMOKE TESTS PASSED")
