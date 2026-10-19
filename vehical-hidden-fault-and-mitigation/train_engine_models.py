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
from sklearn.model_selection import (
    StratifiedKFold,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from model_utils import LabelEncodedClassifier

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw_data"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

# One entry per dataset. Each dataset has different sensors,
# so each one gets its own model.
DATASETS = [
    {
        "name": "engine_condition",
        "file": "engine_data_with_vehicle_model.csv",
        "target": "Engine Condition",
        "description": "Engine condition from oil, fuel and coolant sensors",
    },
    {
        "name": "engine_vibration",
        "file": "engine_fault_detection_with_vehicle_model.csv",
        "target": "Engine_Condition",
        "description": "Engine condition from vibration, acoustic and exhaust sensors",
    },
]

# Vehicle model is not a sensor reading, so it is not used as a feature.
EXCLUDED_COLUMNS = ["vehicle_model"]


def build_models():
    """Candidate models (Logistic Regression = proposal baseline)."""
    return {
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
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
        ),
    }


def train_dataset(config):
    data_file = RAW_DIR / config["file"]
    target = config["target"]

    print("\n" + "=" * 60)
    print(f"DATASET: {config['name']} ({data_file.name})")
    print("=" * 60)

    if not data_file.exists():
        raise FileNotFoundError(f"Dataset not found: {data_file}")

    df = pd.read_csv(data_file)

    features = [
        col for col in df.columns
        if col != target and col not in EXCLUDED_COLUMNS
    ]

    X = df[features]
    y = df[target]

    print("Total rows:", len(df))
    print("Missing values:", int(df.isna().sum().sum()))
    print("Exact duplicate rows:", int(df.duplicated().sum()))
    print("Features:", features)
    print("\nClass distribution:")
    print(y.value_counts().sort_index().to_string())

    # No duplicate sensor patterns in these datasets, so a plain
    # stratified split cannot leak a pattern into the test set.
    if X.duplicated().any():
        raise ValueError(
            "Duplicate sensor patterns found. Use a grouped split "
            "(see train_model.py) before training."
        )

    # -----------------------------------------------------------
    # 1. Stratified hold-out test set (20%)
    # -----------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    print(f"\nTraining rows: {len(X_train)}")
    print(f"Testing rows: {len(X_test)}")

    # -----------------------------------------------------------
    # 2. Stratified 5-fold cross-validation on the training data
    # -----------------------------------------------------------
    models = build_models()
    scoring = {
        "accuracy": "accuracy",
        "balanced_accuracy": "balanced_accuracy",
        "macro_f1": "f1_macro",
    }
    cv = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    print("\n----- 5-FOLD CROSS-VALIDATION (training data) -----")

    cv_results = {}
    for name, model in models.items():
        result = cross_validate(
            model,
            X_train,
            y_train,
            cv=cv,
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

    best_name = max(
        cv_results,
        key=lambda name: cv_results[name]["macro_f1"]["mean"],
    )
    print(f"\nSelected model (best CV macro F1): {best_name}")

    # -----------------------------------------------------------
    # 3. Final evaluation on the unseen hold-out test set
    # -----------------------------------------------------------
    best_model = models[best_name]
    best_model.fit(X_train, y_train)
    y_pred = best_model.predict(X_test)

    test_metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "macro_f1": float(f1_score(y_test, y_pred, average="macro")),
    }

    print(f"\n----- HOLD-OUT TEST RESULTS ({best_name}) -----")
    for metric, value in test_metrics.items():
        print(f"{metric}: {value:.4f}")

    print("\n----- CLASSIFICATION REPORT -----")
    print(classification_report(y_test, y_pred, zero_division=0))

    labels = [int(label) for label in best_model.classes_]
    print("----- CONFUSION MATRIX -----")
    print("Label order:", labels)
    print(confusion_matrix(y_test, y_pred, labels=labels))

    baseline = models["Logistic Regression"]
    baseline.fit(X_train, y_train)
    baseline_f1 = float(
        f1_score(y_test, baseline.predict(X_test), average="macro")
    )
    print(f"\nLogistic Regression baseline test macro F1: {baseline_f1:.4f}")

    # -----------------------------------------------------------
    # 4. Inference latency (one record)
    # -----------------------------------------------------------
    sample = X_test.iloc[[0]]
    runs = 100

    start = time.perf_counter()
    for _ in range(runs):
        best_model.predict(sample)
        best_model.predict_proba(sample)
    latency_ms = (time.perf_counter() - start) / runs * 1000

    print(f"\nAverage inference latency: {latency_ms:.2f} ms per prediction")

    # -----------------------------------------------------------
    # 5. Retrain on all data and save
    # -----------------------------------------------------------
    # Reported metrics come from the hold-out test above.
    best_model.fit(X, y)

    model_file = MODEL_DIR / f"{config['name']}_model.joblib"
    dump(best_model, model_file)

    metadata = {
        "description": config["description"],
        "features": features,
        "target": target,
        "classes": labels,
        "class_meaning": "Not confirmed yet - check dataset source",
        "dataset": data_file.name,
        "dataset_rows": int(len(df)),
        "model": best_name,
        "selection_metric": "stratified 5-fold CV macro F1",
        "split": "Stratified hold-out (no duplicate sensor patterns)",
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
        MODEL_DIR / f"{config['name']}_metadata.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(metadata, f, indent=2)

    print(f"\nModel saved: {model_file}")

    return best_name, test_metrics


summary = {}
for config in DATASETS:
    summary[config["name"]] = train_dataset(config)

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
for name, (model_name, metrics) in summary.items():
    print(
        f"{name}: {model_name} | "
        f"accuracy {metrics['accuracy']:.4f} | "
        f"macro F1 {metrics['macro_f1']:.4f}"
    )
print("\nTraining complete.")
