"""
Module      : lstm_model.py
Date        : 2026-08-07
Author      : Dhruv
Modification History:
    2026-08-07 - Recreated (rebuild session). Implements the LSTM half of
                 FR-3.3.
    (earlier session) - torch import adds several seconds of cold-start
        latency the first time a Flask worker handles a signal-generation
        request. signal_service.py imports this module at app startup
        (not lazily per-request) specifically to pay that cost once.
Synopsis:
    Shallow LSTM (1 layer, 32 hidden units) over 20-day feature sequence
    windows, predicting direction (up/down/neutral). Deliberately shallow:
    matches the solo-scope/60-hour budget — a deeper model would need more
    data and tuning time than this project has, and would not obviously
    outperform the baseline on noisy financial data anyway (see SPMP risk
    register: "low signal accuracy... framed as expected").

Functions:
    buildSequenceWindows(featureFrame, labelSeries, windowSize) -> (np.ndarray, np.ndarray)
        -> (sequences shaped [nSamples, windowSize, nFeatures], labels [nSamples])
    trainLstm(sequences, labels, classNames, epochs, hiddenSize) -> ShallowLstm
    predictDirection(model, sequence, classNames) -> dict
        -> {"direction": str, "confidence": float, "classIndex": int}

Class:
    ShallowLstm(nn.Module) — 1-layer LSTM + linear head over the final timestep.

Globals accessed/modified: None.
"""

import numpy as np
import torch
import torch.nn as nn

WINDOW_SIZE_DEFAULT = 20   # ALL_CAPS constants per CHARUSAT standard
HIDDEN_SIZE_DEFAULT = 32
EPOCHS_DEFAULT = 15
LEARNING_RATE_DEFAULT = 0.001


class ShallowLstm(nn.Module):
    def __init__(self, inputSize, hiddenSize=HIDDEN_SIZE_DEFAULT, numClasses=3):
        super().__init__()
        self.lstm = nn.LSTM(inputSize, hiddenSize, num_layers=1, batch_first=True)
        self.fc = nn.Linear(hiddenSize, numClasses)

    def forward(self, x):
        lstmOut, _ = self.lstm(x)
        finalTimestep = lstmOut[:, -1, :]
        return self.fc(finalTimestep)


def buildSequenceWindows(featureFrame, labelSeries, windowSize=WINDOW_SIZE_DEFAULT):
    alignedLabels = labelSeries.reindex(featureFrame.index)
    featureValues = featureFrame.values
    sequences, sequenceLabels = [], []

    for endIdx in range(windowSize, len(featureFrame) + 1):
        startIdx = endIdx - windowSize
        rowLabel = alignedLabels.iloc[endIdx - 1]
        if pd_isna(rowLabel):
            continue
        sequences.append(featureValues[startIdx:endIdx])
        sequenceLabels.append(rowLabel)

    return np.asarray(sequences, dtype=np.float32), np.asarray(sequenceLabels)


def pd_isna(value):
    # Tiny local helper so this module doesn't need a full pandas import
    # just for one isna check; keeps the dependency footprint explicit.
    return value != value or value is None  # NaN != NaN is True; catches None too


def trainLstm(sequences, labels, classNames, epochs=EPOCHS_DEFAULT,
              hiddenSize=HIDDEN_SIZE_DEFAULT):
    classToIndex = {name: i for i, name in enumerate(classNames)}
    labelIndices = np.array([classToIndex[label] for label in labels])

    inputSize = sequences.shape[2]
    model = ShallowLstm(inputSize, hiddenSize=hiddenSize, numClasses=len(classNames))
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE_DEFAULT)
    lossFn = nn.CrossEntropyLoss()

    sequenceTensor = torch.tensor(sequences, dtype=torch.float32)
    labelTensor = torch.tensor(labelIndices, dtype=torch.long)

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        outputs = model(sequenceTensor)
        loss = lossFn(outputs, labelTensor)
        loss.backward()
        optimizer.step()

    model.eval()
    return model


def predictDirection(model, sequence, classNames):
    model.eval()
    sequenceTensor = torch.tensor(
        sequence.reshape(1, *sequence.shape), dtype=torch.float32
    )
    with torch.no_grad():
        logits = model(sequenceTensor)
        probabilities = torch.softmax(logits, dim=1)[0].numpy()

    classIndex = int(np.argmax(probabilities))
    return {
        "direction": classNames[classIndex],
        "confidence": float(probabilities[classIndex]),
        "classIndex": classIndex,
    }
