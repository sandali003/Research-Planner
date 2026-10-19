
"""Component 3 - Age- and Mileage-Adjusted Vehicle Deterioration Assessment.

1. Expected-condition model: age + mileage + model -> expected inspection score
2. Observed-condition model: current inspection evidence -> observed score
3. Deviation = observed - expected (negative = worse than expected)
4. Accelerated deterioration when deviation <= threshold (threshold tuned on training data)

Compared against (proposal section 3.3):
  A. age-and-mileage-only classifier
  B. current-condition-only classifier (no expected-vs-observed step)
Target used for comparison: poor_condition = inspection score below 60 (Poor/Critical).
"""
import os
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score,
                             precision_score, recall_score, f1_score, roc_auc_score)

from data_prep import build_deterioration_table

BASELINE_FEATURES = ["age_years", "odometer_km", "vehicle_model"]
EVIDENCE_FEATURES = ["component", "component_state", "vehicle_model"]
CATEGORICAL = ["vehicle_model", "component", "component_state"]
SCORE = "inspection_score"
LABEL = "poor_condition"


def _preprocessor(features):
    cats = [f for f in features if f in CATEGORICAL]
    return ColumnTransformer(
        [("categorical", OneHotEncoder(handle_unknown="ignore"), cats)],
        remainder="passthrough",
    )


def make_regressor(features):
    return Pipeline([
        ("preprocessor", _preprocessor(features)),
        ("model", RandomForestRegressor(n_estimators=300, min_samples_leaf=20, random_state=42, n_jobs=-1)),
    ])


def make_classifier(features):
    return Pipeline([
        ("preprocessor", _preprocessor(features)),
        ("model", RandomForestClassifier(n_estimators=300, min_samples_leaf=10,
                                         class_weight="balanced", random_state=42, n_jobs=-1)),
    ])


def choose_threshold(deviation, label):
    """Deviation cut-off that best separates poor-condition records (max F1)."""
    candidates = np.arange(-30, 0.5, 0.5)
    scores = [f1_score(label, deviation <= t, zero_division=0) for t in candidates]
    return float(candidates[int(np.argmax(scores))])


def fit_deterioration(train):
    """Fit expected + observed models and tune the threshold on out-of-fold deviations."""
    groups = train["vehicle_id"]
    cv = GroupKFold(n_splits=5)
    expected_oof = cross_val_predict(make_regressor(BASELINE_FEATURES), train[BASELINE_FEATURES],
                                     train[SCORE], groups=groups, cv=cv)
    observed_oof = cross_val_predict(make_regressor(EVIDENCE_FEATURES), train[EVIDENCE_FEATURES],
                                     train[SCORE], groups=groups, cv=cv)
    threshold = choose_threshold(observed_oof - expected_oof, train[LABEL])

    expected_model = make_regressor(BASELINE_FEATURES).fit(train[BASELINE_FEATURES], train[SCORE])
    observed_model = make_regressor(EVIDENCE_FEATURES).fit(train[EVIDENCE_FEATURES], train[SCORE])
    return expected_model, observed_model, threshold


def deterioration_status(deviation, threshold):
    return np.select(
        [deviation <= threshold, deviation <= threshold / 2],
        ["High", "Slightly high"],
        default="Normal",
    )


def classification_metrics(y, flag, score):
    return {
        "precision": round(precision_score(y, flag, zero_division=0), 3),
        "recall": round(recall_score(y, flag, zero_division=0), 3),
        "f1": round(f1_score(y, flag, zero_division=0), 3),
        "roc_auc": round(roc_auc_score(y, score), 3),
    }


def regression_metrics(y, pred):
    return {
        "mae": round(mean_absolute_error(y, pred), 2),
        "rmse": round(mean_squared_error(y, pred) ** 0.5, 2),
        "r2": round(r2_score(y, pred), 3),
    }


if __name__ == "__main__":
    # 1. Load inspections joined with age and mileage
    df = build_deterioration_table()
    print("Inspection records:", len(df), "| vehicles:", df["vehicle_id"].nunique())
    print("Poor/Critical share:", round(df[LABEL].mean(), 3))

    # 2. Vehicle-level outer cross-validation
    results = df.copy()
    for col in ["expected_score", "observed_score", "deviation", "threshold",
                "prob_age_mileage", "prob_current_condition"]:
        results[col] = np.nan

    outer = GroupKFold(n_splits=5)
    for fold, (train_idx, test_idx) in enumerate(outer.split(df, groups=df["vehicle_id"]), 1):
        train, test = df.iloc[train_idx], df.iloc[test_idx]

        expected_model, observed_model, threshold = fit_deterioration(train)
        expected = expected_model.predict(test[BASELINE_FEATURES])
        observed = observed_model.predict(test[EVIDENCE_FEATURES])

        model_a = make_classifier(BASELINE_FEATURES).fit(train[BASELINE_FEATURES], train[LABEL])
        model_b = make_classifier(EVIDENCE_FEATURES).fit(train[EVIDENCE_FEATURES], train[LABEL])

        results.loc[results.index[test_idx], "expected_score"] = expected
        results.loc[results.index[test_idx], "observed_score"] = observed
        results.loc[results.index[test_idx], "deviation"] = observed - expected
        results.loc[results.index[test_idx], "threshold"] = threshold
        results.loc[results.index[test_idx], "prob_age_mileage"] = model_a.predict_proba(test[BASELINE_FEATURES])[:, 1]
        results.loc[results.index[test_idx], "prob_current_condition"] = model_b.predict_proba(test[EVIDENCE_FEATURES])[:, 1]
        print(f"  fold {fold}: threshold = {threshold}")

    results["status"] = deterioration_status(results["deviation"], results["threshold"])
    y = results[LABEL]

    # 3. Regression results
    print("\nScore prediction on unseen vehicles:")
    mean_only = np.full(len(results), df[SCORE].mean())
    regression = {
        "mean_only": regression_metrics(results[SCORE], mean_only),
        "expected_model_age_mileage": regression_metrics(results[SCORE], results["expected_score"]),
        "observed_model_current_evidence": regression_metrics(results[SCORE], results["observed_score"]),
    }
    for name, m in regression.items():
        print(f"  {name:34s} {m}")

    # 4. Classification comparison (proposal section 3.3)
    print("\nPoor-condition detection on unseen vehicles:")
    classification = {
        "A_age_mileage_only": classification_metrics(y, results["prob_age_mileage"] >= 0.5, results["prob_age_mileage"]),
        "B_current_condition_only": classification_metrics(y, results["prob_current_condition"] >= 0.5, results["prob_current_condition"]),
        "C_proposed_deviation": classification_metrics(y, results["deviation"] <= results["threshold"], -results["deviation"]),
    }
    for name, m in classification.items():
        print(f"  {name:26s} {m}")

    print("\nDeterioration status counts:", results["status"].value_counts().to_dict())

    # 5. Save per-inspection results for the report
    os.makedirs("reports", exist_ok=True)
    results[["vehicle_id", "vehicle_model", "inspection_date", "age_years", "odometer_km",
             "component_condition", SCORE, "expected_score", "observed_score",
             "deviation", "status"]].round(2).to_csv("reports/deterioration_results.csv", index=False)

    # 6. Train final models on all data and save
    expected_model, observed_model, threshold = fit_deterioration(df)
    joblib.dump({
        "expected_model": expected_model,
        "observed_model": observed_model,
        "threshold": threshold,
        "baseline_features": BASELINE_FEATURES,
        "evidence_features": EVIDENCE_FEATURES,
        "typical_km_per_year": float((df["odometer_km"] / df["age_years"].clip(lower=1)).median()),
        "metrics": {"regression": regression, "classification": classification},
    }, "deterioration_model.joblib", compress=3)

    print("\nFinal threshold:", threshold)
    print("Model saved: deterioration_model.joblib")
    print("Per-inspection results: reports/deterioration_results.csv")
