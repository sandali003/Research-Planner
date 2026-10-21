"""Counterfactual and XAI reliability evaluation on the fault injection benchmark.

Counterfactuals (counterfactual.py) - for injected faults the model reported:
  validity       a move of the repairable sensors clears the fault
  right sensor   the counterfactual changes the injected sensor (only)
  plausible      the target value lies in the healthy range (5th-95th pct)
  restoration    how much of the injected change has to be undone
                 (|target - faulty| / |original - faulty|; 1 = full undo)
Because we know the reading before injection, the repair target can be
checked against the truth - most counterfactual studies cannot do that.

XAI reliability flag (expert_system.EXPECTED_CAUSES, rule X2) - for every
classifier fault: are flagged predictions wrong more often? (Fisher exact test)

Same seeds, folds and test readings as run_xai_eval.py / run_ablation.py.
Run (from the component folder):  python benchmark/run_xai_extras.py
"""

from pathlib import Path
import json
import sys
import time

import joblib
import numpy as np
import pandas as pd
import shap
from joblib import Parallel, delayed
from scipy.stats import fisher_exact
from sklearn.model_selection import GroupKFold

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parent))
sys.path.insert(0, str(BENCH_DIR))

from counterfactual import find_counterfactual  # noqa: E402
from expert_system import EXPECTED_CAUSES  # noqa: E402
from fault_injection import BATTERY_FILE, build_test_set, load_normal_readings  # noqa: E402
from fusion_tuning import ANOMALY_FEATURES, CATEGORY, anomaly_model, anomaly_score, with_magnitude  # noqa: E402

MODEL_DIR = BENCH_DIR.parent / "models"
RESULTS_DIR = BENCH_DIR / "results"

SEEDS = [0, 1, 2]
N_FOLDS = 5
THRESHOLD_PERCENTILE = 95
READINGS_PER_BLOCK = 4  # build_test_set: clean, Charging, Cooling, Vibration per base reading

GROUP = {
    "engine_rpm": "rpm", "engine_load_pct": "load", "battery_voltage_v": "voltage",
    "engine_temp_c": "temperature", "coolant_temp_c": "temperature",
    "vibration_x_g": "vibration", "vibration_y_g": "vibration", "vibration_z_g": "vibration",
    "vibration_magnitude_g": "vibration",
}
TRUE_GROUP = {"Charging": "voltage", "Cooling": "temperature", "Vibration": "vibration"}
# Feature used to measure restoration, per model and sensor group
SHOWN = {"voltage": "battery_voltage_v", "vibration": "vibration_magnitude_g"}


def restoration(cf, original, faulty, feature):
    change = next((c for c in cf["changes"] if c["feature"] == feature), None)
    injected = abs(original[feature] - faulty[feature])
    if change is None or injected < 1e-9:
        return np.nan
    return abs(change["to"] - faulty[feature]) / injected


def evaluate_counterfactuals(model, readings, test, features, is_normal, normal, healthy):
    rows = []
    for idx, faulty in readings.iterrows():
        original = test.loc[(idx // READINGS_PER_BLOCK) * READINGS_PER_BLOCK]
        true = TRUE_GROUP[faulty["true_fault"]]
        cf = find_counterfactual(faulty.to_frame().T[features].astype(float), features, is_normal, normal,
                                 group_of=GROUP.get)
        row = {"model": model, "fault": faulty["true_fault"], "severity": int(faulty["severity"]),
               "valid": cf is not None}
        if cf:
            feature = SHOWN.get(true, "engine_temp_c" if "engine_temp_c" in features else "coolant_temp_c")
            right = cf["sensor_groups"] == [true]
            target = next((c["to"] for c in cf["changes"] if c["feature"] == feature), np.nan)
            lo, hi = healthy[feature]
            row.update({
                "right_sensor": right,
                "single_sensor": len(cf["sensor_groups"]) == 1,
                "plausible": bool(lo <= target <= hi) if right else np.nan,
                "restoration": restoration(cf, original, faulty, feature) if right else np.nan,
            })
        rows.append(row)
    return rows


def run_seed(seed):
    classifier = joblib.load(MODEL_DIR / "autosense_fault_model.joblib")
    with open(MODEL_DIR / "model_metadata.json", encoding="utf-8") as f:
        clf_features = json.load(f)["features"]
    tree = shap.TreeExplainer(classifier.estimator_)
    classes = list(classifier.classes_)

    battery = pd.read_csv(BATTERY_FILE)
    clf_healthy_rows = battery.loc[battery["fault_label"] == "Normal", clf_features]
    clf_normal = clf_healthy_rows.median()
    clf_healthy = {f: tuple(clf_healthy_rows[f].quantile([0.05, 0.95])) for f in clf_features}

    def clf_is_normal(df):
        return classifier.predict(df[clf_features]) == "Normal"

    base = load_normal_readings()
    rng = np.random.default_rng(seed)
    folds = GroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)

    cf_rows, rel_rows = [], []
    for train_idx, test_idx in folds.split(base, groups=base["vehicle_id"]):
        train = with_magnitude(base.iloc[train_idx])
        detector = anomaly_model().fit(train[ANOMALY_FEATURES])
        threshold = np.percentile(anomaly_score(detector, train), THRESHOLD_PERCENTILE)
        an_normal = train[ANOMALY_FEATURES].median()
        an_healthy = {f: tuple(train[f].quantile([0.05, 0.95])) for f in ANOMALY_FEATURES}

        def an_is_normal(df):
            return anomaly_score(detector, df[ANOMALY_FEATURES]) < threshold

        test = build_test_set(base.iloc[test_idx], rng)
        pred = classifier.predict(test[clf_features]).astype(str)
        scores = anomaly_score(detector, test)

        # --- Counterfactuals
        clf_rows = test[(pred != "Normal") & test["true_fault"].isin(["Charging", "Cooling"])]
        cf_rows += evaluate_counterfactuals("XGBoost classifier", clf_rows, test, clf_features,
                                            clf_is_normal, clf_normal, clf_healthy)
        an_rows = test[(scores >= threshold) & test["true_fault"].isin(["Cooling", "Vibration"])]
        cf_rows += evaluate_counterfactuals("One-Class SVM anomaly", an_rows, test, ANOMALY_FEATURES,
                                            an_is_normal, an_normal, an_healthy)

        # --- Reliability flag on every classifier fault (clean readings included)
        reported = test[pred != "Normal"]
        reported_pred = pred[pred != "Normal"]
        values = np.asarray(tree(reported[clf_features]).values)
        for i in range(len(reported)):
            impacts = values[i][:, classes.index(reported_pred[i])]
            sums = pd.Series(impacts, index=[GROUP[f] for f in clf_features]).groupby(level=0).sum()
            positive = sums[sums > 0]
            top = positive.idxmax() if len(positive) else None
            rel_rows.append({
                "predicted": reported_pred[i],
                "true": reported["true_fault"].iloc[i],
                "top_group": top,
                "low_reliability": top is not None and top not in EXPECTED_CAUSES[reported_pred[i]],
                "correct": CATEGORY[reported_pred[i]] == reported["true_fault"].iloc[i],
            })

    cf, rel = pd.DataFrame(cf_rows), pd.DataFrame(rel_rows)
    cf["seed"], rel["seed"] = seed, seed
    return cf, rel


def pct(s):
    return f"{s.mean() * 100:.1f} ± {s.std() * 100:.1f}"


def markdown(df):
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |", "|---" * len(df.columns) + "|"]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def counterfactual_table(cf):
    rows = []
    for (model, fault), g in cf.groupby(["model", "fault"]):
        per_seed = g.groupby("seed").agg(
            valid=("valid", "mean"), right=("right_sensor", "mean"), single=("single_sensor", "mean"),
            plausible=("plausible", "mean"), restoration=("restoration", "median"))
        rows.append({
            "Model": model, "Fault": fault, "n": len(g) // g["seed"].nunique(),
            "Valid": pct(per_seed["valid"]), "Right sensor": pct(per_seed["right"]),
            "Single sensor": pct(per_seed["single"]), "Plausible target": pct(per_seed["plausible"]),
            "Restoration needed (median)": f"{per_seed['restoration'].mean() * 100:.0f}%",
        })
    return pd.DataFrame(rows)


def reliability_table(rel):
    rows = []
    for name, g in [("All classifier faults", rel), ("On clean readings (false alarms)", rel[rel["true"] == "Normal"])]:
        low, ok = g[g["low_reliability"]], g[~g["low_reliability"]]
        rows.append({
            "Readings": name, "n": len(g),
            "Flagged low reliability": f"{len(low) / max(len(g), 1) * 100:.1f}%",
            "Accuracy if reliable": f"{ok['correct'].mean() * 100:.1f}%" if len(ok) else "–",
            "Accuracy if flagged": f"{low['correct'].mean() * 100:.1f}%" if len(low) else "–",
        })
    table = [[int((~rel["low_reliability"] & rel["correct"]).sum()), int((~rel["low_reliability"] & ~rel["correct"]).sum())],
             [int((rel["low_reliability"] & rel["correct"]).sum()), int((rel["low_reliability"] & ~rel["correct"]).sum())]]
    odds, p = fisher_exact(table)
    wrong = rel[~rel["correct"]]
    return pd.DataFrame(rows), p, odds, wrong["low_reliability"].mean()


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    started = time.perf_counter()
    if "--report-only" in sys.argv:
        cf = pd.read_csv(RESULTS_DIR / "counterfactual_per_reading.csv")
        rel = pd.read_csv(RESULTS_DIR / "reliability_per_reading.csv")
    else:
        runs = Parallel(n_jobs=len(SEEDS))(delayed(run_seed)(s) for s in SEEDS)
        cf = pd.concat([c for c, _ in runs], ignore_index=True)
        rel = pd.concat([r for _, r in runs], ignore_index=True)
        cf.to_csv(RESULTS_DIR / "counterfactual_per_reading.csv", index=False)
        rel.to_csv(RESULTS_DIR / "reliability_per_reading.csv", index=False)

    rel_table, p, odds, errors_caught = reliability_table(rel)
    report = [
        "# Counterfactuals and XAI reliability (fault injection benchmark)",
        "",
        f"{len(SEEDS)} seeds x {N_FOLDS}-fold GroupKFold by vehicle; same test readings as the other benchmarks.",
        "",
        "## Counterfactual repair targets",
        "",
        "Readings = injected faults the model reported. Values in %, mean ± std over seeds; n per seed. "
        "Right sensor = only the injected sensor is changed. Plausible = the minimal target is already inside "
        "the healthy 5th-95th percentile range; the minimal change stops at the model's decision boundary, so "
        "this is often outside it, which is why the system shows the healthy range as the repair goal. "
        "Restoration = share of the injected change that has to be undone to clear the alarm (median).",
        "",
        markdown(counterfactual_table(cf)),
        "",
        "## XAI reliability flag (classifier)",
        "",
        "Flag = the SHAP root cause is not a sensor that can explain the predicted fault "
        "(expert_system.EXPECTED_CAUSES). Pooled over seeds.",
        "",
        markdown(rel_table),
        "",
        f"Fisher exact test (flagged vs reliable, correct vs wrong): odds ratio {odds:.2f}, p = {p:.2g}. "
        f"Wrong classifier faults caught by the flag: {errors_caught * 100:.1f}%.",
        "",
    ]
    (RESULTS_DIR / "xai_extras_results.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Done in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
