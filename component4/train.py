"""Train and evaluate Component 4 models.

1. Valuation: market-only baseline vs condition-aware model (plus C1/C2/C3 ablations),
   comparing Linear Regression, Random Forest, Gradient Boosting and XGBoost.
2. Health Score dependency check (do faults affect the Component 1 score in this data?).
3. Repair-cost lookup validation against historical repair records.

Run:  .venv\\Scripts\\python.exe train.py
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

import data

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
SEED = 42


def candidate_models():
    return {
        "LinearRegression": LinearRegression(),
        "RandomForest": RandomForestRegressor(n_estimators=400, min_samples_leaf=2, random_state=SEED, n_jobs=-1),
        "GradientBoosting": GradientBoostingRegressor(n_estimators=400, learning_rate=0.05, max_depth=3, random_state=SEED),
        "XGBoost": XGBRegressor(n_estimators=600, learning_rate=0.05, max_depth=4, subsample=0.9,
                                colsample_bytree=0.9, random_state=SEED, n_jobs=-1),
    }


def build_pipeline(numeric, categorical, regressor):
    pre = ColumnTransformer([
        ("num", StandardScaler(), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
    ])
    # Prices are right-skewed, so models learn log(price) and predictions are mapped back.
    model = TransformedTargetRegressor(regressor=regressor, func=np.log1p, inverse_func=np.expm1)
    return Pipeline([("pre", pre), ("model", model)])


def metrics(y_true, y_pred):
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)),
        "MAPE_%": float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100),
    }


def train_valuation(master):
    X, y = master, master[data.TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=SEED)
    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)

    rows, best = [], {}
    for set_name, (num, cat) in data.feature_sets().items():
        for model_name, reg in candidate_models().items():
            pipe = build_pipeline(num, cat, reg)
            cvres = cross_validate(pipe, X_train, y_train, cv=cv,
                                   scoring=("neg_mean_absolute_error", "r2"), n_jobs=1)
            pipe.fit(X_train, y_train)
            test = metrics(y_test.values, pipe.predict(X_test))
            row = {"feature_set": set_name, "model": model_name,
                   "cv_MAE": -cvres["test_neg_mean_absolute_error"].mean(),
                   "cv_R2": cvres["test_r2"].mean(),
                   **{f"test_{k}": v for k, v in test.items()}}
            rows.append(row)
            print(f"  {set_name:28s} {model_name:17s} cv_MAE={row['cv_MAE']:>11,.0f}  "
                  f"test_MAE={test['MAE']:>11,.0f}  test_R2={test['R2']:.4f}")
            # Model selection uses CV MAE only; the test set is reported, never used to pick.
            if set_name not in best or row["cv_MAE"] < best[set_name]["row"]["cv_MAE"]:
                best[set_name] = {"row": row, "pipe": pipe}

    results = pd.DataFrame(rows)
    return results, best, (X_test, y_test)


def condition_feature_importance(pipe, X_test, y_test):
    """Permutation importance on the raw input columns of the selected condition-aware model."""
    from sklearn.inspection import permutation_importance

    num, cat = data.feature_sets()["condition_aware_C1_C2_C3"]
    cols = num + cat
    imp = permutation_importance(pipe, X_test[cols], y_test, n_repeats=10, random_state=SEED,
                                 scoring="neg_mean_absolute_error")
    return (pd.DataFrame({"feature": cols, "MAE_increase_lkr": imp.importances_mean})
            .sort_values("MAE_increase_lkr", ascending=False))


def health_score_dependency(master):
    """How well age, mileage and deterioration explain the Health Score, and whether faults add anything.

    In the current dataset faults do not move the Health Score, so repair scenarios only change
    the Component 2 features; this check is recorded so that assumption stays visible.
    """
    def fit_r2(cols):
        lr = LinearRegression().fit(master[cols], master["health_score"])
        return float(r2_score(master["health_score"], lr.predict(master[cols])))

    without_faults = ["vehicle_age", "mileage_km", "deterioration_deviation"]
    return {
        "R2_age_mileage_deterioration": fit_r2(without_faults),
        "R2_plus_fault_features": fit_r2(without_faults + ["fault_count", "severity_level"]),
    }


def validate_cost_lookup(lookup, records):
    merged = records.merge(lookup, on=["vehicle_model", "repair_type"], how="left")
    missing = int(merged["typical_total_cost_lkr"].isna().sum())
    merged = merged.dropna(subset=["typical_total_cost_lkr"])
    in_range = ((merged.total_repair_cost_lkr >= merged.min_total_cost_lkr)
                & (merged.total_repair_cost_lkr <= merged.max_total_cost_lkr)).mean()
    return {
        "records": int(len(records)),
        "records_without_lookup": missing,
        **metrics(merged.total_repair_cost_lkr.values, merged.typical_total_cost_lkr.values),
        "share_within_min_max_%": float(in_range * 100),
    }


def main():
    MODEL_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    master = data.load_master()
    print(f"Loaded {len(master)} vehicles from {data.DATA_DIR}")

    print("\n[1] Valuation models (5-fold CV on 80% train, reported on 20% held-out test)")
    results, best, (X_test, y_test) = train_valuation(master)
    results.to_csv(REPORT_DIR / "valuation_results.csv", index=False)

    summary = pd.DataFrame([{"feature_set": k, **v["row"]} for k, v in best.items()])
    summary = summary.drop(columns="feature_set").rename(columns={"model": "best_model"})
    summary.insert(0, "feature_set", list(best.keys()))
    summary.to_csv(REPORT_DIR / "valuation_best_per_feature_set.csv", index=False)

    base = best["baseline_market_only"]
    full = best["condition_aware_C1_C2_C3"]
    joblib.dump(base["pipe"], MODEL_DIR / "valuation_baseline.joblib")
    joblib.dump(full["pipe"], MODEL_DIR / "valuation_condition_aware.joblib")

    importance = condition_feature_importance(full["pipe"], X_test, y_test)
    importance.to_csv(REPORT_DIR / "condition_aware_feature_importance.csv", index=False)

    print("\n[2] Health Score dependency check")
    hs_dep = health_score_dependency(master)
    print(f"  {hs_dep}")

    print("\n[3] Repair-cost lookup validation")
    cost_val = validate_cost_lookup(data.load_cost_lookup(), data.load_cost_records())
    print(f"  {cost_val}")

    improvement = {
        "MAE_reduction_lkr": base["row"]["test_MAE"] - full["row"]["test_MAE"],
        "MAE_reduction_%": (1 - full["row"]["test_MAE"] / base["row"]["test_MAE"]) * 100,
        "R2_gain": full["row"]["test_R2"] - base["row"]["test_R2"],
    }
    meta = {
        "data_dir": str(data.DATA_DIR),
        "n_vehicles": int(len(master)),
        "split": "80/20 train/test, random_state=42; model selection by 5-fold CV MAE on train",
        "baseline": {"model": base["row"]["model"], "features": data.feature_sets()["baseline_market_only"],
                     **{k: base["row"][k] for k in ("test_MAE", "test_RMSE", "test_R2", "test_MAPE_%")}},
        "condition_aware": {"model": full["row"]["model"], "features": data.feature_sets()["condition_aware_C1_C2_C3"],
                            **{k: full["row"][k] for k in ("test_MAE", "test_RMSE", "test_R2", "test_MAPE_%")}},
        "improvement_over_baseline": improvement,
        "health_score_dependency": hs_dep,
        "repair_cost_lookup_validation": cost_val,
    }
    (MODEL_DIR / "model_meta.json").write_text(json.dumps(meta, indent=2))

    print("\n=== Summary (held-out test set) ===")
    print(summary[["feature_set", "best_model", "test_MAE", "test_RMSE", "test_R2", "test_MAPE_%"]]
          .to_string(index=False, float_format=lambda v: f"{v:,.4f}" if abs(v) < 100 else f"{v:,.0f}"))
    print(f"\nCondition-aware vs baseline: MAE -{improvement['MAE_reduction_lkr']:,.0f} LKR "
          f"({improvement['MAE_reduction_%']:.1f}%), R2 +{improvement['R2_gain']:.4f}")
    print("\nTop condition-aware features (permutation importance):")
    print(importance.head(8).to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
    print(f"\nSaved models to {MODEL_DIR} and reports to {REPORT_DIR}")


if __name__ == "__main__":
    main()
