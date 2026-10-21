"""Component 4, model 1: Sri Lankan market valuation (ikman.lk Toyota ads).

Compares Linear Regression, Random Forest, Gradient Boosting and XGBoost
(proposal section 3.4) on two feature sets:
  market only        model, age, mileage, engine, fuel, transmission, condition, body
  market + attributes  + value attributes stated in the ad (single owner, service
                       records, new tyres, new battery, accident free, original paint,
                       needs repair)
Prices are learned on a log scale. XGBoost and Gradient Boosting (histogram) have
monotonic constraints: price never rises with age or mileage.

Split: 80/20 by seller (no seller's ads in both train and test, so re-posted or
near-identical cars cannot leak); model selection by 5-fold GroupKFold MAE on train.
Attribute premiums: hedonic regression on all ads (log price on the car's features
plus the attributes, standard errors clustered by seller), as an association in
asking prices, not a guaranteed effect.

Run (from component4):  .venv\\Scripts\\python real\\train_valuation_sl.py
"""

from pathlib import Path
import json
import sys
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from xgboost import XGBRegressor

REAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REAL_DIR))

from ikman_data import ATTRIBUTES, CATEGORICAL, NUMERIC, TARGET, TARGET_MODELS, load  # noqa: E402

MODEL_DIR = REAL_DIR / "models"
REPORT_DIR = REAL_DIR / "reports"
SEED = 42
DECREASING = {"age_years", "mileage_km"}   # monotonic: price never rises with these


class MonotoneXGB(BaseEstimator, RegressorMixin):
    """XGBoost with price decreasing in the first two (age, mileage) columns."""

    def __init__(self, n_decreasing=2, **params):
        self.n_decreasing = n_decreasing
        self.params = params

    def fit(self, X, y):
        n = X.shape[1]
        constraints = tuple([-1] * self.n_decreasing + [0] * (n - self.n_decreasing))
        self.model_ = XGBRegressor(monotone_constraints=constraints, **self.params).fit(X, y)
        return self

    def predict(self, X):
        return self.model_.predict(X)

    def get_params(self, deep=True):
        return {"n_decreasing": self.n_decreasing, **self.params}

    def set_params(self, **params):
        for k, v in params.items():
            if k == "n_decreasing":
                self.n_decreasing = v
            else:
                self.params[k] = v
        return self


def preprocessor(numeric, categorical, scale):
    num_steps = [("impute", SimpleImputer(strategy="median"))] + ([("scale", StandardScaler())] if scale else [])
    return ColumnTransformer([
        ("num", Pipeline(num_steps), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), categorical),
    ], sparse_threshold=0)


def candidates(numeric):
    n_dec = sum(c in DECREASING for c in numeric[:2])
    return {
        "LinearRegression": (Ridge(alpha=1.0), True),
        "RandomForest": (RandomForestRegressor(n_estimators=400, min_samples_leaf=2, random_state=SEED, n_jobs=-1), False),
        # monotonic_cst is set in fit_pipeline, once the encoded width is known
        "GradientBoosting": (HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, random_state=SEED), False),
        "XGBoost": (MonotoneXGB(n_decreasing=n_dec, n_estimators=800, learning_rate=0.05, max_depth=6,
                                subsample=0.9, colsample_bytree=0.8, random_state=SEED, n_jobs=-1), False),
    }


def build(name, numeric, categorical):
    regressor, scale = candidates(numeric)[name]
    pre = preprocessor(numeric, categorical, scale)
    model = TransformedTargetRegressor(regressor=clone(regressor), func=np.log, inverse_func=np.exp)
    return Pipeline([("pre", pre), ("model", model)])


def fit_pipeline(name, numeric, categorical, X, y):
    pipe = build(name, numeric, categorical)
    if name == "GradientBoosting":
        n_out = pipe.named_steps["pre"].fit(X).transform(X[:5]).shape[1]
        cst = [(-1 if c in DECREASING else 0) for c in numeric] + [0] * (n_out - len(numeric))
        pipe.named_steps["model"].regressor.set_params(monotonic_cst=cst)
    return pipe.fit(X, y)


def metrics(y, pred):
    return {"MAE": mean_absolute_error(y, pred), "RMSE": float(np.sqrt(mean_squared_error(y, pred))),
            "R2": r2_score(y, pred), "MAPE_%": float(np.mean(np.abs((y - pred) / y)) * 100)}


def cv_mae(name, numeric, categorical, X, y, groups):
    maes = []
    for tr, va in GroupKFold(n_splits=5, shuffle=True, random_state=SEED).split(X, y, groups):
        pipe = fit_pipeline(name, numeric, categorical, X.iloc[tr], y.iloc[tr])
        maes.append(mean_absolute_error(y.iloc[va], pipe.predict(X.iloc[va])))
    return float(np.mean(maes))


def attribute_premiums(df):
    """Hedonic regression: % price difference per attribute, controlling for the car.

    log(price) ~ model + fuel + transmission + condition + body + age + age^2 + log km
                 + log engine + attributes, with standard errors clustered by seller.
    Tree models hardly split on rare binary flags, so they understate these effects.
    """
    d = df[df["engine_cc"].notna()].reset_index(drop=True)
    X = pd.get_dummies(d[CATEGORICAL], drop_first=True).astype(float)
    X["age"], X["age2"] = d["age_years"], d["age_years"] ** 2
    X["log_km"], X["log_cc"] = np.log1p(d["mileage_km"]), np.log(d["engine_cc"])
    for a in ATTRIBUTES:
        X[a] = d[a]
    X.insert(0, "const", 1.0)
    A, y = X.values, np.log(d[TARGET].values)
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    bread = np.linalg.pinv(A.T @ A)
    meat = np.zeros((A.shape[1], A.shape[1]))
    for idx in d.groupby("user").indices.values():
        s = A[idx].T @ resid[idx]
        meat += np.outer(s, s)
    se = np.sqrt(np.diag(bread @ meat @ bread))
    cols = list(X.columns)
    out = {}
    for a in ATTRIBUTES:
        i = cols.index(a)
        lo, hi = beta[i] - 1.96 * se[i], beta[i] + 1.96 * se[i]
        out[a] = {"pct": round((np.exp(beta[i]) - 1) * 100, 2),
                  "ci_low_pct": round((np.exp(lo) - 1) * 100, 2), "ci_high_pct": round((np.exp(hi) - 1) * 100, 2),
                  "significant": bool(lo > 0 or hi < 0), "ads": int(d[a].sum())}
    return out, round(float(1 - resid.var() / y.var()), 3)


def markdown(df):
    lines = ["| " + " | ".join(df.columns) + " |", "|---" * len(df.columns) + "|"]
    for r in df.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:,.0f}" if isinstance(v, float) and abs(v) > 100 else
                                       (f"{v:.3f}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(lines)


def main():
    started = time.perf_counter()
    df = load()
    print(f"Toyota ads after cleaning: {len(df):,} | sellers: {df['user'].nunique():,}")
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    tr_idx, te_idx = next(split.split(df, groups=df["user"]))
    train, test = df.iloc[tr_idx], df.iloc[te_idx]

    feature_sets = {
        "Market only": (NUMERIC, CATEGORICAL),
        "Market + attributes": (NUMERIC + list(ATTRIBUTES), CATEGORICAL),
    }
    rows, best = [], {}
    for fs_name, (numeric, categorical) in feature_sets.items():
        cols = numeric + categorical
        for name in candidates(numeric):
            cv = cv_mae(name, numeric, categorical, train[cols], train[TARGET], train["user"])
            pipe = fit_pipeline(name, numeric, categorical, train[cols], train[TARGET])
            m = metrics(test[TARGET].values, pipe.predict(test[cols]))
            rows.append({"Feature set": fs_name, "Model": name, "CV MAE": cv, **m})
            print(f"  {fs_name:20s} {name:17s} CV MAE {cv:12,.0f}  test MAE {m['MAE']:12,.0f}  "
                  f"R2 {m['R2']:.3f}  MAPE {m['MAPE_%']:.1f}%", flush=True)
            if fs_name not in best or cv < best[fs_name][1]:
                best[fs_name] = (name, cv, pipe, m)

    results = pd.DataFrame(rows)
    REPORT_DIR.mkdir(exist_ok=True)
    MODEL_DIR.mkdir(exist_ok=True)
    results.to_csv(REPORT_DIR / "sl_valuation_results.csv", index=False)

    name, _, pipe, m = best["Market + attributes"]
    numeric, categorical = feature_sets["Market + attributes"]
    cols = numeric + categorical
    premiums, hedonic_r2 = attribute_premiums(df)

    per_model = []
    for model_name in TARGET_MODELS:
        part = test[test["model"] == model_name]
        if len(part) >= 10:
            mm = metrics(part[TARGET].values, pipe.predict(part[cols]))
            per_model.append({"Model": model_name, "Test ads": len(part), "MAE": mm["MAE"], "MAPE_%": mm["MAPE_%"]})

    # Final model on all ads
    final = fit_pipeline(name, numeric, categorical, df[cols], df[TARGET])
    joblib.dump({"model": final, "model_name": name, "numeric": numeric, "categorical": categorical,
                 "attributes": list(ATTRIBUTES), "test_metrics": m, "premiums": premiums,
                 "data": "ikman.lk Toyota car ads, Sep 2022 - Apr 2023 (asking prices, LKR)",
                 "n_ads": len(df)}, MODEL_DIR / "sl_valuation.joblib", compress=3)

    base_name, _, _, base_m = best["Market only"]
    report = [
        "# Sri Lankan market valuation (Component 4, model 1)", "",
        f"ikman.lk Toyota car ads (Sep 2022 - Apr 2023, asking prices). {len(df):,} ads after cleaning, "
        f"{df['user'].nunique():,} sellers. Test set: 20% of sellers ({len(test):,} ads), never seen in training.",
        "", "## All models", "", markdown(results), "",
        "## Best model per feature set (chosen by cross-validated MAE)", "",
        f"- Market only: **{base_name}**, test MAE LKR {base_m['MAE']:,.0f}, R2 {base_m['R2']:.3f}, MAPE {base_m['MAPE_%']:.1f}%",
        f"- Market + attributes: **{name}**, test MAE LKR {m['MAE']:,.0f}, R2 {m['R2']:.3f}, MAPE {m['MAPE_%']:.1f}%",
        f"- MAE change from the attributes: {(m['MAE'] - base_m['MAE']) / base_m['MAE'] * 100:+.1f}%", "",
        f"## Attribute premiums (hedonic regression, R2 {hedonic_r2}, 95% CI clustered by seller)", "",
        "| Attribute | Price difference | 95% CI | Significant | Ads |", "|---|---|---|---|---|",
        *[f"| {k} | {v['pct']:+.1f}% | {v['ci_low_pct']:+.1f}% to {v['ci_high_pct']:+.1f}% | "
          f"{'yes' if v['significant'] else 'no'} | {v['ads']:,} |" for k, v in premiums.items()], "",
        "Claims made by sellers in the ad text; associations in asking prices, not guaranteed effects.", "",
        "## Error for the AutoSense target models", "", markdown(pd.DataFrame(per_model)), "",
    ]
    (REPORT_DIR / "sl_valuation_results.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Done in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
