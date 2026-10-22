
from pathlib import Path
import json
import time

import pandas as pd
from joblib import dump
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedGroupKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from mitigation_rules import get_mitigation_recommendation
from model_utils import LabelEncodedClassifier

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = (
    BASE_DIR
    / "raw_data"
    / "AutoSense_Toyota_Battery_Voltage_Deduplicated.csv"
)

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

df = pd.read_csv(DATA_FILE)

# Sensor inputs only; do not use vehicle IDs or models as features.
features = [
    "engine_rpm",
    "battery_voltage_v",
    "engine_temp_c",
    "engine_load_pct",
]
target = "fault_label"

X = df[features]
y = df[target]

print("===== DATASET =====")
print("Total rows:", len(df))
print("Unique sensor patterns:", X.drop_duplicates().shape[0])
print("Features:", features)
print("\nClass distribution:")
print(y.value_counts().to_string())

# Each sensor pattern must have only one label.
pattern_labels = df.groupby(features)[target].nunique()
if (pattern_labels > 1).any():
    raise ValueError(
        "Some identical sensor patterns have conflicting labels. "
        "Investigate these before training."
    )

# Identical sensor patterns get the same group ID, so a pattern is
# never in both the training and testing data (prevents leakage).
groups = pd.util.hash_pandas_object(X, index=False)

# ---------------------------------------------------------------
# 1. Grouped hold-out test set (about 20%)
# ---------------------------------------------------------------
splitter = StratifiedGroupKFold(
    n_splits=5,
    shuffle=True,
    random_state=RANDOM_STATE,
)
train_idx, test_idx = next(splitter.split(X, y, groups))

X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
groups_train = groups.iloc[train_idx]

shared_patterns = set(groups.iloc[train_idx]) & set(groups.iloc[test_idx])
print("\n===== GROUPED SPLIT =====")
print(f"Training rows: {len(X_train)}")
print(f"Testing rows: {len(X_test)}")
print("Sensor patterns shared by train and test:", len(shared_patterns))

# ---------------------------------------------------------------
# 2. Candidate models (Logistic Regression = proposal baseline)
# ---------------------------------------------------------------
models = {
    "Logistic Regression": Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
        )),
    ]),
    "Random Forest": Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ]),
    "XGBoost": LabelEncodedClassifier(
        XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="mlogloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    ),
}

scoring = {
    "accuracy": "accuracy",
    "balanced_accuracy": "balanced_accuracy",
    "macro_f1": "f1_macro",
}

# ---------------------------------------------------------------
# 3. Grouped 5-fold cross-validation on the training data
# ---------------------------------------------------------------
cv = StratifiedGroupKFold(
    n_splits=5,
    shuffle=True,
    random_state=RANDOM_STATE,
)

print("\n===== GROUPED 5-FOLD CROSS-VALIDATION (training data) =====")

cv_results = {}
for name, model in models.items():
    result = cross_validate(
        model,
        X_train,
        y_train,
        cv=cv,
        groups=groups_train,
        scoring=scoring,
        n_jobs=1,
    )

    cv_results[name] = {
        metric: {
            "mean": float(result[f"test_{metric}"].mean()),
            "std": float(result[f"test_{metric}"].std()),
        }
        for metric in scoring
    }

    print(f"\n--- {name} ---")
    for metric in scoring:
        print(
            f"{metric}: {cv_results[name][metric]['mean']:.4f} "
            f"+/- {cv_results[name][metric]['std']:.4f}"
        )

# Select the model with the best mean macro F1
best_name = max(
    cv_results,
    key=lambda name: cv_results[name]["macro_f1"]["mean"],
)
print(f"\nSelected model (best CV macro F1): {best_name}")

# ---------------------------------------------------------------
# 4. Final evaluation on the unseen hold-out test set
# ---------------------------------------------------------------
best_model = models[best_name]
best_model.fit(X_train, y_train)
y_pred = best_model.predict(X_test)

test_metrics = {
    "accuracy": float(accuracy_score(y_test, y_pred)),
    "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
    "macro_f1": float(f1_score(y_test, y_pred, average="macro")),
}

print(f"\n===== HOLD-OUT TEST RESULTS ({best_name}) =====")
for metric, value in test_metrics.items():
    print(f"{metric}: {value:.4f}")

print("\n===== CLASSIFICATION REPORT =====")
print(classification_report(y_test, y_pred, zero_division=0))

labels = list(best_model.classes_)
print("===== CONFUSION MATRIX =====")
print("Label order:", labels)
print(confusion_matrix(y_test, y_pred, labels=labels))

# Baseline comparison on the same test set
baseline = models["Logistic Regression"]
baseline.fit(X_train, y_train)
baseline_f1 = float(
    f1_score(y_test, baseline.predict(X_test), average="macro")
)
print(f"\nLogistic Regression baseline test macro F1: {baseline_f1:.4f}")

# ---------------------------------------------------------------
# 5. Inference latency (prediction + mitigation, one record)
# ---------------------------------------------------------------
sample = X_test.iloc[[0]]
runs = 100

start = time.perf_counter()
for _ in range(runs):
    prediction = best_model.predict(sample)[0]
    best_model.predict_proba(sample)
    get_mitigation_recommendation(prediction)
latency_ms = (time.perf_counter() - start) / runs * 1000

print(f"\nAverage inference latency: {latency_ms:.2f} ms per assessment")

# ---------------------------------------------------------------
# 6. Retrain on all data and save
# ---------------------------------------------------------------
# Reported metrics come from the hold-out test above.
best_model.fit(X, y)

dump(best_model, MODEL_DIR / "autosense_fault_model.joblib")

metadata = {
    "features": features,
    "target": target,
    "classes": labels,
    "dataset": DATA_FILE.name,
    "model": best_name,
    "selection_metric": "grouped CV macro F1",
    "split": (
        "StratifiedGroupKFold by identical sensor pattern "
        "(no pattern in both train and test)"
    ),
    "test_size": 0.20,
    "random_state": RANDOM_STATE,
    "cv_results": cv_results,
    "test_metrics": test_metrics,
    "baseline_test_macro_f1": baseline_f1,
    "inference_latency_ms": latency_ms,
    "final_model_trained_on": "all rows (after evaluation)",
    "data_type": "Simulated research prototype data",
}

with open(
    MODEL_DIR / "model_metadata.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(metadata, f, indent=2)

print("\nModel saved in:", MODEL_DIR)
print("Training complete.")
