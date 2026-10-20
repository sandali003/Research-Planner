"""Tuning the fusion: classifier confidence gate + anomaly threshold.

Both values are chosen with fault labels we never test on:
  - Anomaly threshold: a percentile of *out-of-fold* scores (GroupKFold by
    vehicle), so it matches how the model scores vehicles it has not seen.
    A percentile of training scores is too low for new vehicles.
  - Grid search over (confidence gate, percentile): best macro F1 on faults
    injected into the same out-of-fold readings, with the false alarm rate
    on the clean readings at most MAX_FALSE_ALARM_RATE.

The grid search simulates the expert system's fusion rules
(F1 classifier, F1b gate, F2 hidden anomaly) on top of rules-only output,
so the costly inference only runs once per reading.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from expert_system import run_expert_system
from fault_injection import FAULT_TYPES, build_test_set
from obd_assessment import WARM_ENGINE_TEMP_C

ANOMALY_FEATURES = [
    "engine_rpm", "engine_load_pct", "coolant_temp_c",
    "vibration_x_g", "vibration_y_g", "vibration_z_g", "vibration_magnitude_g",
]
CLASSES = ["Normal"] + FAULT_TYPES

# System output -> injected fault category
CATEGORY = {
    "Charging_System_Warning": "Charging",
    "Cooling_System_Warning": "Cooling",
    "Engine_Abnormality_Suspected": "Cooling",  # high engine temp at low rpm
    "Running_Hot": "Cooling",
    "Abnormal_Vibration": "Vibration",
    "Hidden_Anomaly": "Unknown",                # detected, cause not named
    "Engine_Lugging": "Other",
    "Rough_Idle": "Other",
    "High_Idle": "Other",
}
CATEGORY_PRIORITY = FAULT_TYPES + ["Unknown", "Other"]

CONFIDENCE_GATES = [0.0, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
THRESHOLD_PERCENTILES = [95, 96, 97, 98, 99, 99.5]
INNER_FOLDS = 5

# Most cars inspected are healthy, so false alarms are limited first:
# at most 1 in 20 healthy readings may be reported as a fault.
MAX_FALSE_ALARM_RATE = 0.05


def anomaly_model():
    """Same detector as the saved model (train_anomaly_model.py)."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("detector", OneClassSVM(kernel="rbf", gamma="scale", nu=0.05)),
    ])


def anomaly_score(model, df):
    """Higher = more abnormal."""
    return -model.decision_function(df[ANOMALY_FEATURES])


def with_magnitude(df):
    df = df.copy()
    df["vibration_magnitude_g"] = np.sqrt(
        df["vibration_x_g"] ** 2 + df["vibration_y_g"] ** 2 + df["vibration_z_g"] ** 2
    )
    return df


def predicted_label(categories, true_fault):
    """One label per reading: the true category if the system named it, else its top category."""
    if not categories:
        return "Normal"
    if true_fault in categories:
        return true_fault
    return next(c for c in CATEGORY_PRIORITY if c in categories)


def rule_categories(row, use_vib=True, use_volt=True, prediction=None, anomaly=None):
    """Run the expert system on one reading; return the fault categories it reports."""
    es = run_expert_system(
        sensors={
            "rpm": row.engine_rpm,
            "load": row.engine_load_pct,
            "coolant": row.coolant_temp_c,
            "engine_temp": row.engine_temp_c,
            "voltage": row.battery_voltage_v if use_volt else None,
            "vibration": row.vibration_magnitude_g if use_vib else None,
            "vehicle_model": row.vehicle_model,
            "dtc_codes": (),
        },
        prediction=prediction,
        anomaly=anomaly,
    )
    return {CATEGORY.get(f["name"], "Other") for f in es["faults"]}


def build_tuning_set(normal, classifier, classifier_features, rng, seed):
    """Out-of-fold anomaly scores for the normal readings, and a scored injected-fault set."""
    normal = with_magnitude(normal).reset_index(drop=True)
    oof_scores = np.zeros(len(normal))
    parts = []
    inner = GroupKFold(n_splits=INNER_FOLDS, shuffle=True, random_state=seed)
    for fit_idx, val_idx in inner.split(normal, groups=normal["vehicle_id"]):
        detector = anomaly_model().fit(normal.iloc[fit_idx][ANOMALY_FEATURES])
        oof_scores[val_idx] = anomaly_score(detector, normal.iloc[val_idx])
        part = build_test_set(normal.iloc[val_idx], rng)
        part["anomaly_score"] = anomaly_score(detector, part)
        parts.append(part)

    tuning = pd.concat(parts, ignore_index=True)
    tuning["xgb_pred"] = classifier.predict(tuning[classifier_features]).astype(str)
    tuning["xgb_conf"] = classifier.predict_proba(tuning[classifier_features]).max(axis=1)
    tuning["rule_cats"] = [frozenset(rule_categories(r)) for r in tuning.itertuples(index=False)]
    return oof_scores, tuning


def simulate_fusion(tuning, gate, threshold):
    """Predicted labels of the full hybrid for one (gate, threshold), mirroring rules F1/F1b/F2."""
    labels = []
    for row in tuning.itertuples(index=False):
        cats = set(row.rule_cats)
        classifier_fault = row.xgb_pred != "Normal" and row.xgb_conf >= gate
        if classifier_fault:
            cats.add(CATEGORY[row.xgb_pred])
        flagged = row.anomaly_score >= threshold
        if flagged and not cats and row.coolant_temp_c >= WARM_ENGINE_TEMP_C:
            cats.add("Unknown")
        labels.append(predicted_label(cats, row.true_fault))
    return np.array(labels)


def grid_search(oof_scores, tuning):
    """Return the best (gate, percentile, threshold) by macro F1, and the full grid."""
    rows = []
    is_normal = tuning["true_fault"] == "Normal"
    for percentile in THRESHOLD_PERCENTILES:
        threshold = float(np.percentile(oof_scores, percentile))
        for gate in CONFIDENCE_GATES:
            labels = simulate_fusion(tuning, gate, threshold)
            rows.append({
                "confidence_gate": gate,
                "threshold_percentile": percentile,
                "anomaly_threshold": threshold,
                "macro_f1": f1_score(tuning["true_fault"], labels, labels=CLASSES,
                                     average="macro", zero_division=0),
                "false_alarm_rate": float((labels[is_normal] != "Normal").mean()),
            })
    grid = pd.DataFrame(rows)
    # Best macro F1 among settings within the false alarm limit; ties go to fewer false alarms.
    # If none is within the limit, take the fewest false alarms.
    allowed = grid[grid["false_alarm_rate"] <= MAX_FALSE_ALARM_RATE]
    if allowed.empty:
        best = grid.sort_values(["false_alarm_rate", "macro_f1"], ascending=[True, False]).iloc[0]
    else:
        best = allowed.sort_values(["macro_f1", "false_alarm_rate"], ascending=[False, True]).iloc[0]
    return best, grid
