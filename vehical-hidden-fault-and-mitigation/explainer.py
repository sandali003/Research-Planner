"""SHAP explanations for the trained models of this component.

- Fault classifier (XGBoost): shap.TreeExplainer, exact and fast.
- Anomaly model (One-Class SVM): shap.KernelExplainer on the anomaly
  score, with a k-means summary of healthy training readings as the
  background.

A positive impact pushes towards the predicted fault (classifier) or
towards "abnormal" (anomaly model). The models are not retrained.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline

BASE_DIR = Path(__file__).resolve().parent
NORMAL_DATA_FILE = BASE_DIR / "raw_data" / "toyota_obd_original_labeled.csv"

FEATURE_LABELS = {
    "engine_rpm": "Engine RPM",
    "battery_voltage_v": "Battery voltage",
    "engine_temp_c": "Engine temperature",
    "engine_load_pct": "Engine load",
    "engine_load": "Engine load",
    "coolant_temp": "Coolant temperature",
    "vibration_x": "Vibration X",
    "vibration_y": "Vibration Y",
    "vibration_z": "Vibration Z",
    "vibration_magnitude": "Vibration level",
}

KERNEL_BACKGROUND_SIZE = 10
KERNEL_SAMPLES = 200


def _factors(features, values, impacts):
    """Per-feature impacts, largest effect first."""
    rows = [
        {
            "feature": f,
            "label": FEATURE_LABELS.get(f, f),
            "value": float(v),
            "impact": round(float(i), 4),
        }
        for f, v, i in zip(features, values, impacts)
    ]
    return sorted(rows, key=lambda r: abs(r["impact"]), reverse=True)


class ClassifierExplainer:
    """TreeExplainer for the saved fault classifier."""

    def __init__(self, model):
        self.model = model
        # The saved model is a LabelEncodedClassifier (XGBoost) or a
        # sklearn Pipeline whose last step is a tree model.
        if isinstance(model, Pipeline):
            self.transform = model[:-1].transform
            estimator = model[-1]
        else:
            self.transform = None
            estimator = getattr(model, "estimator_", model)
        self.explainer = shap.TreeExplainer(estimator)

    def explain(self, row, predicted_class):
        data = self.transform(row) if self.transform else row
        explanation = self.explainer(data)
        values = np.asarray(explanation.values)[0]       # (features, classes)
        base = np.asarray(explanation.base_values)[0]
        idx = list(self.model.classes_).index(predicted_class)
        if values.ndim == 2:
            impacts, base_value = values[:, idx], base[idx]
        else:                                             # binary model
            sign = 1 if idx == 1 else -1
            impacts, base_value = sign * values, sign * float(np.ravel(base)[0])
        return {
            "method": "SHAP TreeExplainer",
            "target": predicted_class,
            "base_value": round(float(base_value), 4),
            "factors": _factors(row.columns, row.iloc[0].values, impacts),
        }


class AnomalyExplainer:
    """KernelExplainer for the anomaly score of the One-Class SVM."""

    def __init__(self, model, features):
        self.features = features
        normal = pd.read_csv(NORMAL_DATA_FILE)
        normal = normal.loc[normal["fault"] == 0, features]
        background = shap.kmeans(normal.values, KERNEL_BACKGROUND_SIZE)

        def score(data):
            frame = pd.DataFrame(data, columns=features)
            return -model.decision_function(frame)        # higher = abnormal

        self.explainer = shap.KernelExplainer(score, background)

    def explain(self, row):
        impacts = self.explainer.shap_values(
            row[self.features].values, nsamples=KERNEL_SAMPLES, silent=True
        )
        return {
            "method": "SHAP KernelExplainer",
            "target": "anomaly score",
            "base_value": round(float(np.ravel(self.explainer.expected_value)[0]), 4),
            "factors": _factors(self.features, row[self.features].iloc[0].values,
                                np.asarray(impacts)[0]),
        }
