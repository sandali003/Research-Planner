"""XAI evaluation with ground-truth explanations.

In the fault injection benchmark we know which sensor was changed, so we
can test whether SHAP points at the true root cause - something most XAI
studies cannot measure.

  RQ-X1 Root cause: is the top SHAP sensor group the injected one?
        (top-1 / top-2 accuracy; group = sum of SHAP values of its features)
  RQ-X2 Naming hidden anomalies: the anomaly model only says "unusual";
        can SHAP name the cause?
  RQ-X3 Faithfulness (deletion test): resetting the top group to its normal
        value should change the output more than resetting a random group.
  RQ-X4 Stability: does the top group stay the same under small sensor noise?

Baselines for RQ-X1: random group, and the group whose value is furthest
from normal (largest |z-score| against the training vehicles) - a simple
non-XAI root-cause heuristic.

Explained readings: injected faults the model reported (classifier predicted
a fault / anomaly score over the 95th percentile of training scores).
Same folds and test readings as run_ablation.py.

Run (from the component folder):  python benchmark/run_xai_eval.py
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
from sklearn.model_selection import GroupKFold

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parent))
sys.path.insert(0, str(BENCH_DIR))

from fault_injection import build_test_set, load_normal_readings  # noqa: E402
from fusion_tuning import ANOMALY_FEATURES, anomaly_model, anomaly_score, with_magnitude  # noqa: E402

MODEL_DIR = BENCH_DIR.parent / "models"
RESULTS_DIR = BENCH_DIR / "results"

SEEDS = [0, 1, 2]
N_FOLDS = 5
THRESHOLD_PERCENTILE = 95
MAX_ANOMALY_PER_FAULT = 60     # KernelExplainer is slow: readings explained per fault and fold
KERNEL_BACKGROUND_SIZE = 10    # same as explainer.py
KERNEL_SAMPLES = 200
NOISE_FRACTION = 0.05          # stability: noise sd = 5% of the feature's normal sd
NOISE_REPEATS = 3

GROUP = {
    "engine_rpm": "RPM",
    "engine_load_pct": "Load",
    "battery_voltage_v": "Voltage",
    "engine_temp_c": "Temperature",
    "coolant_temp_c": "Temperature",
    "vibration_x_g": "Vibration",
    "vibration_y_g": "Vibration",
    "vibration_z_g": "Vibration",
    "vibration_magnitude_g": "Vibration",
}
TRUE_GROUP = {"Charging": "Voltage", "Cooling": "Temperature", "Vibration": "Vibration"}


def group_scores(features, values):
    """Sum per sensor group (SHAP values) as a Series, largest first."""
    return pd.Series(values, index=[GROUP[f] for f in features]).groupby(level=0).sum().sort_values(ascending=False)


def zscore_ranking(row, features, mean, std):
    z = (row[features] - mean[features]).abs() / std[features]
    return pd.Series(z.values, index=[GROUP[f] for f in features]).groupby(level=0).max().sort_values(ascending=False)


def reset_group(df, features, group, normal_median):
    out = df.copy()
    for f in features:
        if GROUP[f] == group:
            out[f] = normal_median[f]
    if group == "Vibration" and "vibration_magnitude_g" in out:
        out = with_magnitude(out)
    return out


def add_noise(df, features, std, rng):
    out = df.copy()
    for f in features:
        out[f] = out[f] + rng.normal(0, NOISE_FRACTION * std[f], len(out))
    if "vibration_magnitude_g" in features:
        out = with_magnitude(out)
    return out


def evaluate_readings(model_name, readings, features, explain, output, flagged, mean, std, median, rng):
    """Root cause, faithfulness and stability for one model on its explained readings."""
    groups = sorted({GROUP[f] for f in features})
    rows = []
    for i in range(len(readings)):
        row = readings.iloc[[i]]
        true = TRUE_GROUP[row["true_fault"].iloc[0]]
        shap_rank = group_scores(features, explain(row))
        z_rank = zscore_ranking(row.iloc[0], features, mean, std)
        top = shap_rank.index[0]

        # Deletion test: reset the top group vs a random other group
        before = output(row)
        others = [g for g in groups if g != top]
        random_group = others[rng.integers(len(others))]
        after_top = output(reset_group(row, features, top, median))
        after_random = output(reset_group(row, features, random_group, median))

        # Stability under small sensor noise
        same_top = [
            group_scores(features, explain(add_noise(row, features, std, rng))).index[0] == top
            for _ in range(NOISE_REPEATS)
        ]

        rows.append({
            "model": model_name,
            "fault": row["true_fault"].iloc[0],
            "severity": int(row["severity"].iloc[0]),
            "true_group": true,
            "shap_top1": top == true,
            "shap_top2": true in shap_rank.index[:2],
            "zscore_top1": z_rank.index[0] == true,
            "random_top1": 1 / len(groups),
            "output_drop_top": before - after_top,
            "output_drop_random": before - after_random,
            "flip_top": not flagged(after_top),
            "flip_random": not flagged(after_random),
            "stability": float(np.mean(same_top)),
        })
    return rows


def run_seed(seed):
    classifier = joblib.load(MODEL_DIR / "autosense_fault_model.joblib")
    with open(MODEL_DIR / "model_metadata.json", encoding="utf-8") as f:
        clf_features = json.load(f)["features"]
    tree = shap.TreeExplainer(classifier.estimator_)
    classes = list(classifier.classes_)

    base = load_normal_readings()
    rng = np.random.default_rng(seed)          # same test readings as run_ablation.py
    xai_rng = np.random.default_rng(seed + 2000)
    folds = GroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)

    rows = []
    for train_idx, test_idx in folds.split(base, groups=base["vehicle_id"]):
        train = with_magnitude(base.iloc[train_idx])
        all_features = clf_features + [f for f in ANOMALY_FEATURES if f not in clf_features]
        mean, std, median = train[all_features].mean(), train[all_features].std(), train[all_features].median()

        detector = anomaly_model().fit(train[ANOMALY_FEATURES])
        threshold = np.percentile(anomaly_score(detector, train), THRESHOLD_PERCENTILE)
        background = shap.kmeans(train[ANOMALY_FEATURES].values, KERNEL_BACKGROUND_SIZE)
        kernel = shap.KernelExplainer(
            lambda x: anomaly_score(detector, pd.DataFrame(x, columns=ANOMALY_FEATURES)), background)

        test = build_test_set(base.iloc[test_idx], rng)
        faulty = test[test["true_fault"] != "Normal"].reset_index(drop=True)

        # --- Classifier: explain the predicted class (voltage and temperature faults)
        pred = classifier.predict(faulty[clf_features]).astype(str)
        clf_rows = faulty[(pred != "Normal") & faulty["true_fault"].isin(["Charging", "Cooling"])]
        clf_pred = dict(zip(clf_rows.index, pred[clf_rows.index]))

        def clf_explain(row, _target=None):
            values = np.asarray(tree(row[clf_features]).values)[0]
            return values[:, classes.index(clf_pred[row.index[0]])]

        def clf_output(row):  # probability of the originally predicted class
            return float(classifier.predict_proba(row[clf_features])[0][classes.index(clf_pred[row.index[0]])])

        def clf_flagged(prob):
            return prob >= 0.5

        rows += evaluate_readings("XGBoost classifier", clf_rows, clf_features, clf_explain, clf_output,
                                  clf_flagged, mean, std, median, xai_rng)

        # --- Anomaly model: explain the anomaly score (temperature and vibration faults)
        scores = anomaly_score(detector, faulty)
        flagged = faulty[(scores >= threshold) & faulty["true_fault"].isin(["Cooling", "Vibration"])]
        if flagged.empty:
            continue
        sample = pd.concat([
            g.sample(min(len(g), MAX_ANOMALY_PER_FAULT), random_state=seed)
            for _, g in flagged.groupby("true_fault")
        ])

        def an_explain(row):
            return np.asarray(kernel.shap_values(row[ANOMALY_FEATURES].values,
                                                 nsamples=KERNEL_SAMPLES, silent=True))[0]

        def an_output(row):
            return float(anomaly_score(detector, row)[0])

        def an_flagged(score):
            return score >= threshold

        rows += evaluate_readings("One-Class SVM anomaly", sample, ANOMALY_FEATURES, an_explain, an_output,
                                  an_flagged, mean, std, median, xai_rng)

    out = pd.DataFrame(rows)
    out["seed"] = seed
    return out


def summarise(df):
    metrics = {
        "shap_top1": "SHAP top-1", "shap_top2": "SHAP top-2", "zscore_top1": "z-score top-1",
        "random_top1": "Random", "flip_top": "Flip (reset top)", "flip_random": "Flip (reset random)",
        "stability": "Stability",
    }
    rows = []
    for (model, fault), g in df.groupby(["model", "fault"]):
        per_seed = g.groupby("seed")[list(metrics) + ["output_drop_top", "output_drop_random"]].mean()
        row = {"Model": model, "Fault": fault, "n": len(g) // df["seed"].nunique()}
        for col, name in metrics.items():
            row[name] = f"{per_seed[col].mean() * 100:.1f} ± {per_seed[col].std() * 100:.1f}"
        row["Output drop (top / random)"] = (f"{per_seed['output_drop_top'].mean():.3f} / "
                                             f"{per_seed['output_drop_random'].mean():.3f}")
        rows.append(row)
    return pd.DataFrame(rows)


def markdown(df):
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |", "|---" * len(df.columns) + "|"]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    started = time.perf_counter()
    if "--report-only" in sys.argv:  # rebuild the report from the saved per-reading results
        df = pd.read_csv(RESULTS_DIR / "xai_per_reading.csv")
    else:
        df = pd.concat(Parallel(n_jobs=len(SEEDS))(delayed(run_seed)(s) for s in SEEDS), ignore_index=True)
        df.to_csv(RESULTS_DIR / "xai_per_reading.csv", index=False)

    summary = summarise(df)
    summary.to_csv(RESULTS_DIR / "xai_summary.csv", index=False)
    by_severity = (df.groupby(["model", "fault", "severity"])["shap_top1"].mean().unstack() * 100).round(1)

    report = [
        "# XAI evaluation (ground-truth root causes)",
        "",
        f"{len(SEEDS)} seeds x {N_FOLDS}-fold GroupKFold by vehicle. Explained readings = injected faults the "
        "model reported. Values in %, mean ± std over seeds. n = explained readings per seed.",
        "Flip = the model stops reporting the fault after the group is reset to its normal (median) value.",
        "Output drop = fall in predicted-class probability (classifier) or anomaly score (anomaly model).",
        "",
        markdown(summary),
        "",
        "## SHAP top-1 accuracy by fault severity (%)",
        "",
        markdown(by_severity.reset_index()),
        "",
    ]
    (RESULTS_DIR / "xai_results.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Done in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
