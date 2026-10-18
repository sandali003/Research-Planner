from pathlib import Path
import json
import time

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "raw_data" / "toyota_obd_original_labeled.csv"

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

# Normal readings above this score percentile are flagged.
# 95 means about 5% of normal readings are expected false alarms.
THRESHOLD_PERCENTILE = 95

# Sensor inputs only. Label columns (fault_label, condition,
# label_reason, fault) are never used as features.
features = [
    "engine_rpm",
    "engine_load",
    "coolant_temp",
    "vibration_x",
    "vibration_y",
    "vibration_z",
    "vibration_magnitude",
]

df = pd.read_csv(DATA_FILE)

X = df[features]
is_fault = df["fault"] == 1
groups = df["vehicle_id"]

print("===== DATASET =====")
print("Total rows:", len(df))
print("Normal rows (fault = 0):", int((~is_fault).sum()))
print("Fault rows (fault = 1):", int(is_fault.sum()))
print("Features:", features)
print("\nFault labels:")
print(df.loc[is_fault, "fault_label"].value_counts().to_string())

# ---------------------------------------------------------------
# 1. Split normal rows by vehicle (20% of vehicles held out)
# ---------------------------------------------------------------
# The model only learns from normal readings. Readings from one
# vehicle are never in both training and testing.
normal_df = df[~is_fault]

splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.20,
    random_state=RANDOM_STATE,
)
train_idx, test_idx = next(
    splitter.split(normal_df, groups=normal_df["vehicle_id"])
)

train_df = normal_df.iloc[train_idx]
test_normal_df = normal_df.iloc[test_idx]

# Test set = unseen normal vehicles + every fault row
test_df = pd.concat([test_normal_df, df[is_fault]])

X_train = train_df[features]
X_test = test_df[features]
y_test = (test_df["fault"] == 1).astype(int)

print("\n===== SPLIT =====")
print(f"Training rows (normal only): {len(X_train)}")
print(f"Testing rows: {len(X_test)} "
      f"({len(test_normal_df)} normal + {int(is_fault.sum())} fault)")
print("Vehicles in train:", train_df["vehicle_id"].nunique())
print("Vehicles in test (normal):", test_normal_df["vehicle_id"].nunique())

# ---------------------------------------------------------------
# 2. Candidate anomaly detectors
# ---------------------------------------------------------------
models = {
    "Isolation Forest": Pipeline([
        ("scaler", StandardScaler()),
        ("detector", IsolationForest(
            n_estimators=300,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ]),
    "One-Class SVM": Pipeline([
        ("scaler", StandardScaler()),
        ("detector", OneClassSVM(kernel="rbf", gamma="scale", nu=0.05)),
    ]),
    "Local Outlier Factor": Pipeline([
        ("scaler", StandardScaler()),
        ("detector", LocalOutlierFactor(n_neighbors=20, novelty=True)),
    ]),
}


def anomaly_score(model, data):
    """Higher score = more abnormal."""
    return -model.decision_function(data)


# ---------------------------------------------------------------
# 3. Train on normal data, evaluate on held-out test set
# ---------------------------------------------------------------
results = {}
for name, model in models.items():
    model.fit(X_train)

    # Threshold comes from training normals only (no test labels)
    threshold = float(
        np.percentile(anomaly_score(model, X_train), THRESHOLD_PERCENTILE)
    )

    scores = anomaly_score(model, X_test)
    y_pred = (scores >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()

    results[name] = {
        "roc_auc": float(roc_auc_score(y_test, scores)),
        "pr_auc": float(average_precision_score(y_test, scores)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "false_alarm_rate": float(fp / (fp + tn)),
        "threshold": threshold,
        "confusion_matrix": {
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        },
    }

    print(f"\n--- {name} ---")
    for metric in ["roc_auc", "pr_auc", "recall", "precision",
                   "false_alarm_rate"]:
        print(f"{metric}: {results[name][metric]:.4f}")
    print(f"Faults caught: {tp}/{tp + fn} | "
          f"False alarms: {fp}/{fp + tn}")

# Select the model with the best PR-AUC (faults are rare)
best_name = max(results, key=lambda name: results[name]["pr_auc"])
best_model = models[best_name]
print(f"\nSelected model (best PR-AUC): {best_name}")

# ---------------------------------------------------------------
# 4. Which fault types are caught?
# ---------------------------------------------------------------
best_threshold = results[best_name]["threshold"]
fault_rows = df[is_fault].copy()
fault_rows["flagged"] = (
    anomaly_score(best_model, fault_rows[features]) >= best_threshold
)

caught_by_type = (
    fault_rows.groupby("fault_label")["flagged"]
    .agg(caught="sum", total="count")
    .astype(int)
)
print(f"\n===== FAULTS CAUGHT BY TYPE ({best_name}) =====")
print(caught_by_type.to_string())

# ---------------------------------------------------------------
# 5. Inference latency (one record)
# ---------------------------------------------------------------
sample = X_test.iloc[[0]]
runs = 100

start = time.perf_counter()
for _ in range(runs):
    anomaly_score(best_model, sample)
latency_ms = (time.perf_counter() - start) / runs * 1000

print(f"\nAverage inference latency: {latency_ms:.2f} ms per reading")

# ---------------------------------------------------------------
# 6. Retrain on all normal rows and save
# ---------------------------------------------------------------
# Reported metrics come from the held-out test above.
best_model.fit(normal_df[features])
final_threshold = float(
    np.percentile(
        anomaly_score(best_model, normal_df[features]),
        THRESHOLD_PERCENTILE,
    )
)

dump(best_model, MODEL_DIR / "obd_anomaly_model.joblib")

metadata = {
    "task": "Unsupervised anomaly detection (trained on normal data only)",
    "features": features,
    "score": "higher = more abnormal (negative decision_function)",
    "threshold": final_threshold,
    "threshold_rule": (
        f"{THRESHOLD_PERCENTILE}th percentile of normal training scores"
    ),
    "dataset": DATA_FILE.name,
    "model": best_name,
    "selection_metric": "PR-AUC on held-out test set",
    "split": (
        "GroupShuffleSplit by vehicle_id on normal rows (20% of vehicles); "
        "all fault rows used for testing only"
    ),
    "random_state": RANDOM_STATE,
    "results": results,
    "faults_caught_by_type": caught_by_type.to_dict(orient="index"),
    "inference_latency_ms": latency_ms,
    "final_model_trained_on": "all normal rows (after evaluation)",
    "label_note": (
        "Fault labels were assigned by threshold rules (see label_reason) "
        "and are used only for evaluation."
    ),
    "data_type": "Real OBD-II readings with rule-based labels",
}

with open(
    MODEL_DIR / "obd_anomaly_metadata.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(metadata, f, indent=2)

print("\nModel saved in:", MODEL_DIR)
print("Training complete.")
