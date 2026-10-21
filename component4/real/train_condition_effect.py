"""Component 4, model 2: how much does verified condition move the sale price?

US wholesale auction sales (Kaggle "Vehicle Sales Data", data_real/car_prices.csv):
each sale has an inspector's condition score (10-49, higher is better), the
Manheim Market Report value (MMR, the market value for that make, model, year and
mileage) and the actual selling price.

Target: log(selling price / MMR), the premium or discount against the market
value. MMR already prices the car's model, age and mileage, so what is left is
mostly condition.

Models (all on the same features except the baseline):
  No condition (baseline)   age, log mileage, log MMR, make, body, transmission
  Linear                    + condition
  Gradient Boosting         + condition, monotonic: price never falls as condition improves
  XGBoost                   + condition, same monotonic constraint
Split by VIN (80/20): no car is in both sets.

Repeat-sale validation: cars sold twice in the test set. If condition really moves
price, the model's predicted change between the two sales should follow the actual
change in price-to-market ratio; the no-condition baseline is the reference.

Condition scores 1-5 (a second, coarser scale in the file) are left out.
Run (from component4):  .venv\\Scripts\\python real\\train_condition_effect.py
"""

from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from xgboost import XGBRegressor

REAL_DIR = Path(__file__).resolve().parent
DATA_FILE = REAL_DIR.parent / "data_real" / "car_prices.csv"
MODEL_DIR = REAL_DIR / "models"
REPORT_DIR = REAL_DIR / "reports"
SEED = 42
TOP_MAKES = 30

NUMERIC = ["age_years", "log_odometer", "log_mmr"]
CATEGORICAL = ["make", "body", "transmission"]
TARGET = "log_ratio"


def load_sales(path=DATA_FILE):
    d = pd.read_csv(path, on_bad_lines="skip", low_memory=False)
    for c in ("make", "model", "body", "transmission"):
        d[c] = d[c].astype(str).str.lower().str.strip()
    d["date"] = pd.to_datetime(d["saledate"].astype(str).str[4:15], format="%b %d %Y", errors="coerce")
    for c in ("condition", "odometer", "mmr", "sellingprice", "year"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["condition", "odometer", "mmr", "sellingprice", "year", "date", "vin"])
    d = d[d["condition"].between(10, 49) & d["odometer"].between(1, 400_000)
          & (d["mmr"] > 500) & (d["sellingprice"] > 500)].copy()
    d["ratio"] = d["sellingprice"] / d["mmr"]
    d = d[d["ratio"].between(0.2, 3)]
    d["age_years"] = (d["date"].dt.year + d["date"].dt.dayofyear / 365.25 - d["year"] - 0.5).clip(lower=0)
    d["log_odometer"] = np.log1p(d["odometer"])
    d["log_mmr"] = np.log(d["mmr"])
    d[TARGET] = np.log(d["ratio"])
    top = d["make"].value_counts().index[:TOP_MAKES]
    d["make"] = d["make"].where(d["make"].isin(top), "other")
    return d.reset_index(drop=True)


def model_specs():
    num_with = NUMERIC + ["condition"]
    ordinal = ColumnTransformer([("num", "passthrough", num_with),
                                 ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATEGORICAL)])
    mono = [0] * len(NUMERIC) + [1] + [0] * len(CATEGORICAL)      # +1 on condition only
    cat_mask = [False] * len(num_with) + [True] * len(CATEGORICAL)
    return {
        "No condition (baseline)": (NUMERIC, Pipeline([
            ("pre", ColumnTransformer([("num", "passthrough", NUMERIC),
                                       ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATEGORICAL)])),
            ("model", HistGradientBoostingRegressor(max_iter=400, learning_rate=0.08, random_state=SEED,
                                                    categorical_features=[False] * len(NUMERIC) + [True] * len(CATEGORICAL)))])),
        "Linear": (num_with, Pipeline([
            ("pre", ColumnTransformer([("num", StandardScaler(), num_with),
                                       ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)])),
            ("model", Ridge(alpha=1.0))])),
        "Gradient Boosting": (num_with, Pipeline([
            ("pre", ordinal),
            ("model", HistGradientBoostingRegressor(max_iter=400, learning_rate=0.08, random_state=SEED,
                                                    categorical_features=cat_mask, monotonic_cst=mono))])),
        "XGBoost": (num_with, Pipeline([
            ("pre", clone(ordinal)),
            ("model", XGBRegressor(n_estimators=500, learning_rate=0.08, max_depth=7, subsample=0.9,
                                   colsample_bytree=0.9, monotone_constraints=tuple(mono),
                                   random_state=SEED, n_jobs=-1))])),
    }


def repeat_pairs(d):
    """First and last sale of every VIN sold more than once."""
    s = d.sort_values("date")
    g = s.groupby("vin")
    first, last = g.head(1).set_index("vin"), g.tail(1).set_index("vin")
    keep = g.size()[lambda n: n > 1].index
    return first.loc[keep], last.loc[keep]


def validate_repeat_sales(pipes, specs, first, last):
    actual = last[TARGET].values - first[TARGET].values
    dc = last["condition"].values - first["condition"].values
    changed = np.abs(dc) >= 5
    rows = []
    for name, pipe in pipes.items():
        cols = specs[name][0] + CATEGORICAL
        predicted = pipe.predict(last[cols]) - pipe.predict(first[cols])
        rows.append({
            "Model": name,
            "Pairs": len(actual),
            "Corr(predicted, actual change)": round(float(np.corrcoef(predicted, actual)[0, 1]), 3),
            "MAE of change": round(float(np.mean(np.abs(predicted - actual))), 4),
            "Right direction (|condition change| >= 5)": round(float(np.mean(np.sign(predicted[changed]) == np.sign(actual[changed]))), 3),
        })
    return pd.DataFrame(rows)


def condition_curve(pipe, cols, toyota):
    """Price multiplier by condition for a typical Toyota, relative to condition 35."""
    typical = {c: toyota[c].median() for c in NUMERIC}
    typical.update({c: toyota[c].mode().iloc[0] for c in CATEGORICAL})
    grid = np.arange(10, 50)
    rows = pd.DataFrame([{**typical, "condition": c} for c in grid])
    pred = pipe.predict(rows[cols])
    ref = pred[list(grid).index(35)]
    return pd.DataFrame({"condition": grid, "price_vs_condition_35_pct": ((np.exp(pred - ref) - 1) * 100).round(2)})


def condition_quantiles(toyota):
    """Condition distribution of Toyotas by age band (to map Component 3 percentiles to this scale)."""
    bands = pd.cut(toyota["age_years"], [0, 2, 4, 6, 8, 10, 14, 30], include_lowest=True)
    q = toyota.groupby(bands, observed=True)["condition"].quantile([0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]).unstack()
    q.index = [str(i) for i in q.index]
    return q


def markdown(df):
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |", "|---" * len(df.columns) + "|"]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    started = time.perf_counter()
    d = load_sales()
    toyota = d[d["make"] == "toyota"]
    print(f"Sales: {len(d):,} | Toyota: {len(toyota):,} | VINs: {d['vin'].nunique():,}")
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(d, groups=d["vin"]))
    train, test = d.iloc[tr], d.iloc[te]

    specs = model_specs()
    pipes, rows = {}, []
    for name, (num, pipe) in specs.items():
        cols = num + CATEGORICAL
        pipe.fit(train[cols], train[TARGET])
        pipes[name] = pipe
        pred = pipe.predict(test[cols])
        price_pred = test["mmr"].values * np.exp(pred)
        tt = (test["make"] == "toyota").values
        rows.append({
            "Model": name,
            "MAE log ratio": round(mean_absolute_error(test[TARGET], pred), 4),
            "R2 log ratio": round(r2_score(test[TARGET], pred), 3),
            "Price MAE $": round(mean_absolute_error(test["sellingprice"], price_pred)),
            "Toyota price MAE $": round(mean_absolute_error(test["sellingprice"][tt], price_pred[tt])),
        })
        print(f"  {name:26s} {rows[-1]}", flush=True)
    results = pd.DataFrame(rows)

    first, last = repeat_pairs(test)
    repeat = validate_repeat_sales(pipes, specs, first, last)
    print(repeat.to_string(index=False))

    best = results[results["Model"] != "No condition (baseline)"].sort_values("MAE log ratio").iloc[0]["Model"]
    best_cols = specs[best][0] + CATEGORICAL
    curve = condition_curve(pipes[best], best_cols, toyota)
    quantiles = condition_quantiles(toyota)

    final = specs[best][1].fit(d[best_cols], d[TARGET])
    MODEL_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": final, "model_name": best, "features": best_cols, "numeric": specs[best][0],
                 "categorical": CATEGORICAL, "toyota_curve": curve, "toyota_condition_quantiles": quantiles,
                 "toyota_typical": {c: float(toyota[c].median()) for c in NUMERIC},
                 "test_metrics": results.to_dict(orient="records"), "repeat_sales": repeat.to_dict(orient="records"),
                 "data": "US wholesale auction sales 2014-2015 (Kaggle Vehicle Sales Data), condition 10-49"},
                MODEL_DIR / "condition_effect.joblib", compress=3)
    results.to_csv(REPORT_DIR / "condition_effect_results.csv", index=False)

    picks = curve[curve["condition"].isin([15, 20, 25, 30, 35, 40, 45, 49])]
    report = [
        "# Condition effect on sale price (Component 4, model 2)", "",
        f"US wholesale auction sales 2014-2015: {len(d):,} sales ({len(toyota):,} Toyota), condition 10-49 "
        "(higher is better). Target: log(selling price / market value MMR). Test set: 20% of VINs.", "",
        "## Test set", "", markdown(results), "",
        f"## Repeat-sale validation ({len(first):,} cars sold twice in the test set)", "",
        "Predicted change between the two sales vs the actual change in price-to-market ratio.", "",
        markdown(repeat), "",
        f"## Price by condition for a typical Toyota (best model: {best}; relative to condition 35)", "",
        markdown(picks), "",
        "## Toyota condition distribution by age (for mapping Component 3 percentiles)", "",
        markdown(quantiles.reset_index().rename(columns={"index": "age band"})), "",
    ]
    (REPORT_DIR / "condition_effect_results.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Done in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
