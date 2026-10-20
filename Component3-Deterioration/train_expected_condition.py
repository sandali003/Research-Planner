"""Component 3, step 2: probabilistic expected-condition baseline (UK MOT data).

For a vehicle's age, mileage, platform, fuel and engine size the model gives
the full distribution of condition grades of comparable vehicles (mot_condition.py),
not a single expected value. A vehicle's observed grade is then placed in that
distribution: "worse than 88% of comparable cars".

Model: cumulative ordinal model, one gradient-boosted binary classifier per
cut-off P(grade <= k). Age and mileage have monotonic constraints, so the
expected condition can never improve as a car gets older or covers more km.

Evaluation on vehicles not seen in training (80/20 split by vehicle_id),
against three simpler baselines:
  marginal       grade frequencies of all cars
  platform only  grade frequencies per platform (Yaris / Corolla)
  age only       ordinal model on age alone
Metrics: log loss, ranked probability score (RPS, for ordered grades) and
percentile calibration (randomised PIT; Kolmogorov-Smirnov distance from uniform).

Run:  python train_expected_condition.py   (needs external_data/mot_toyota_2023.csv)
"""

from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from scipy.stats import kstest
from sklearn.model_selection import GroupShuffleSplit

from mot_condition import COMPONENTS, COMPONENT_GRADES, OVERALL_GRADES, add_grades
from ordinal_model import CATEGORICAL, NUMERIC, SEED, FrequencyBaseline, OrdinalBaseline

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "external_data" / "mot_toyota_2023.csv"
MODEL_FILE = BASE_DIR / "models" / "expected_condition_model.joblib"
REPORT_FILE = BASE_DIR / "reports" / "expected_condition_results.md"


def clean(df):
    df = df[df["platform"].notna()
            & df["age_years"].between(0.5, 40)
            & df["odometer_km"].between(500, 600_000)
            & (df["km_per_year"] <= 100_000)].copy()
    df["engine_cc"] = pd.to_numeric(df["engine_cc"], errors="coerce")
    df["fuel_type"] = df["fuel_type"].fillna("UNKNOWN")
    return df


def percentile_better_than(probs, levels, observed):
    """Share of comparable cars in a worse condition than the observed grade (0-1, mid-rank)."""
    idx = np.searchsorted(levels, observed)
    worse = np.array([p[:i].sum() for p, i in zip(probs, idx)])
    same = probs[np.arange(len(probs)), idx]
    return worse + 0.5 * same


def evaluate(probs, y, levels, rng):
    probs = np.clip(probs, 1e-9, 1)
    probs = probs / probs.sum(axis=1, keepdims=True)
    idx = np.searchsorted(levels, y)
    log_loss = float(-np.log(probs[np.arange(len(y)), idx]).mean())
    cum = np.cumsum(probs, axis=1)
    observed_cum = (np.arange(len(levels))[None, :] >= idx[:, None]).astype(float)
    rps = float(((cum - observed_cum) ** 2).sum(axis=1).mean() / (len(levels) - 1))
    # Randomised PIT: uniform if the predicted distributions are calibrated
    below = np.where(idx > 0, cum[np.arange(len(y)), idx - 1], 0.0)
    pit = below + rng.random(len(y)) * probs[np.arange(len(y)), idx]
    return {"log_loss": round(log_loss, 4), "rps": round(rps, 4),
            "pit_ks": round(float(kstest(pit, "uniform").statistic), 4)}


def models_for(levels):
    return {
        "Marginal": FrequencyBaseline(levels),
        "Platform only": FrequencyBaseline(levels, by="platform"),
        "Age only": OrdinalBaseline(levels, categorical=[], numeric=["age_years"]),
        "Proposed (age + km + platform + fuel + engine)": OrdinalBaseline(levels),
    }


def expected_curve(model, levels, platform, fuel, cc, km_per_year):
    """Expected grade and P(major or worse) by age, at a typical km per year."""
    ages = np.arange(1, 21)
    X = pd.DataFrame({"platform": platform, "fuel_type": fuel, "engine_cc": cc,
                      "age_years": ages, "odometer_km": ages * km_per_year})
    probs = model.predict_proba(X)
    expected = probs @ np.array(levels)
    major = probs[:, [i for i, k in enumerate(levels) if k <= 2]].sum(axis=1)
    return pd.DataFrame({"age_years": ages, "odometer_km": ages * km_per_year,
                         "expected_grade": expected.round(2), "p_major_or_worse": major.round(3)})


def markdown(df):
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |", "|---" * len(df.columns) + "|"]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    started = time.perf_counter()
    df = clean(add_grades(pd.read_csv(DATA_FILE)))
    print(f"Tests: {len(df):,} | vehicles: {df['vehicle_id'].nunique():,}")
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    train_idx, test_idx = next(split.split(df, groups=df["vehicle_id"]))
    train, test = df.iloc[train_idx], df.iloc[test_idx]
    rng = np.random.default_rng(SEED)

    targets = {"Overall": ("grade", sorted(OVERALL_GRADES))}
    targets.update({c.replace("_", " ").title(): (f"grade_{c}", sorted(COMPONENT_GRADES)) for c in COMPONENTS})

    rows, final = [], {}
    for name, (col, levels) in targets.items():
        for model_name, model in models_for(levels).items():
            model.fit(train, train[col])
            metrics = evaluate(model.predict_proba(test), test[col].values, levels, rng)
            rows.append({"Target": name, "Model": model_name, **metrics})
            print(f"  {name:16s} {model_name:48s} {metrics}", flush=True)
        final[col] = OrdinalBaseline(levels).fit(df, df[col])  # final model on every vehicle

    results = pd.DataFrame(rows)
    results.to_csv(BASE_DIR / "reports" / "expected_condition_results.csv", index=False)

    # Typical petrol cars at the median km per year of each platform
    curves = []
    for platform in ("Yaris", "Corolla"):
        p = df[df["platform"] == platform]
        cc = float(p["engine_cc"].median())
        kpy = float(p["km_per_year"].median())
        curve = expected_curve(final["grade"], sorted(OVERALL_GRADES), platform, "PE", cc, kpy)
        curve.insert(0, "platform", platform)
        curves.append(curve[curve["age_years"].isin([2, 4, 6, 8, 10, 12, 14, 16, 18, 20])])

    joblib.dump({
        "models": final,
        "features": CATEGORICAL + NUMERIC,
        "overall_grades": OVERALL_GRADES,
        "component_grades": COMPONENT_GRADES,
        "components": COMPONENTS,
        "data": "UK MOT anonymised test data 2023 (DVSA), Toyota Yaris/Vitz/Corolla",
        "metrics": results.to_dict(orient="records"),
    }, MODEL_FILE, compress=3)

    best = results.loc[results.groupby("Target")["log_loss"].idxmin(), ["Target", "Model"]]
    report = [
        "# Expected-condition baseline (Component 3, step 2)", "",
        f"Data: UK MOT 2023, Toyota Yaris / Vitz / Corolla, {len(df):,} tests of "
        f"{df['vehicle_id'].nunique():,} vehicles. Test set: 20% of vehicles, never seen in training.",
        "Grades follow the DVSA defect categories (mot_condition.py). Lower log loss / RPS is better; "
        "PIT KS is the distance of the percentiles from uniform (0 = perfectly calibrated).", "",
        markdown(results), "",
        "Best model per target (log loss):", "", markdown(best), "",
        "## Expected overall condition by age (petrol, median engine size and km per year)", "",
        "Expected grade: 5 Good ... 1 Dangerous.", "",
        markdown(pd.concat(curves)), "",
    ]
    REPORT_FILE.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Saved {MODEL_FILE.name}. Done in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
