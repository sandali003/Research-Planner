"""Experiments 1 and 2: component ablation and modality ablation.

Exp 1 (RQ1): does the hybrid system beat its parts?
    Rules only / XGBoost only / Anomaly only / Rules + XGBoost /
    Rules + Anomaly / Full hybrid / Full hybrid (tuned)
Exp 2 (RQ2): does multi-modal fusion help?
    OBD only / OBD + Vibration / OBD + Voltage / All modalities

Protocol
  - Base data: real normal OBD-II readings, faults injected (fault_injection.py)
  - 5-fold GroupKFold by vehicle, repeated with 5 seeds
  - The anomaly model is retrained in every fold on the training
    vehicles only (the saved model has seen every normal row)
  - The XGBoost classifier is the saved model; it was trained on a
    different dataset, so no test reading was seen in training
  - "Full hybrid" = untuned fusion (no confidence gate, threshold = 95th
    percentile of training scores). "Full hybrid (tuned)" = gate and
    threshold tuned per fold on the training vehicles only (fusion_tuning.py)
  - Metrics are pooled over the 5 folds of a seed, then mean +- std over seeds
  - McNemar's exact test: full hybrid vs every other setup (seed 0)

Test readings use the same random stream as before tuning was added, so
results/before_tuning/ablation_predictions.csv holds the same readings.

Run (from the component folder):  python benchmark/run_ablation.py
"""

from pathlib import Path
import json
import sys
import time

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import binomtest
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parent))
sys.path.insert(0, str(BENCH_DIR))

import expert_system  # noqa: E402
from fault_injection import FAULT_TYPES, build_test_set, load_normal_readings  # noqa: E402
from fusion_tuning import (  # noqa: E402
    ANOMALY_FEATURES, CATEGORY, CLASSES, anomaly_model, anomaly_score, build_tuning_set, grid_search,
    predicted_label, rule_categories, with_magnitude,
)

MODEL_DIR = BENCH_DIR.parent / "models"
RESULTS_DIR = BENCH_DIR / "results"

SEEDS = [0, 1, 2, 3, 4]
N_FOLDS = 5
UNTUNED_PERCENTILE = 95  # same rule as train_anomaly_model.py

# Expert system runs: (use classifier, use anomaly model, use vibration, use voltage)
ES_VARIANTS = {
    "rules": (False, False, True, True),
    "rules_xgb": (True, False, True, True),
    "rules_anomaly": (False, True, True, True),
    "full": (True, True, True, True),
    "obd_only": (False, False, False, False),
    "obd_voltage": (True, False, False, True),
}

COMPONENT_SETUPS = {
    "Rules only": "rules",
    "XGBoost only": "xgb",
    "Anomaly only": "anomaly",
    "Rules + XGBoost": "rules_xgb",
    "Rules + Anomaly": "rules_anomaly",
    "Full hybrid": "full",
    "Full hybrid (tuned)": "tuned",
}
MODALITY_SETUPS = {
    "OBD only": "obd_only",
    "OBD + Vibration": "rules_anomaly",  # classifier needs voltage, so it is skipped
    "OBD + Voltage": "obd_voltage",
    "OBD + Vibration + Voltage": "full",
}


def run_seed(seed):
    classifier = joblib.load(MODEL_DIR / "autosense_fault_model.joblib")
    with open(MODEL_DIR / "model_metadata.json", encoding="utf-8") as f:
        classifier_features = json.load(f)["features"]

    base = load_normal_readings()
    rng = np.random.default_rng(seed)               # test readings
    tune_rng = np.random.default_rng(seed + 1000)   # tuning readings (training vehicles)
    folds = GroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)

    records, tuned_params = [], []
    for fold, (train_idx, test_idx) in enumerate(folds.split(base, groups=base["vehicle_id"])):
        train = with_magnitude(base.iloc[train_idx])
        detector = anomaly_model().fit(train[ANOMALY_FEATURES])
        untuned_threshold = np.percentile(anomaly_score(detector, train), UNTUNED_PERCENTILE)

        # Nested tuning on the training vehicles only
        oof_scores, tuning = build_tuning_set(base.iloc[train_idx], classifier, classifier_features,
                                              tune_rng, seed)
        best, _ = grid_search(oof_scores, tuning)
        tuned_params.append({"seed": seed, "fold": fold, **best.to_dict()})

        test = build_test_set(base.iloc[test_idx], rng)
        pred = classifier.predict(test[classifier_features])
        conf = classifier.predict_proba(test[classifier_features]).max(axis=1)
        scores = anomaly_score(detector, test)

        for i, row in enumerate(test.itertuples(index=False)):
            prediction = {"fault": str(pred[i]), "confidence": float(conf[i])}
            untuned = {"score": float(scores[i]), "threshold": float(untuned_threshold),
                       "flagged": bool(scores[i] >= untuned_threshold)}
            tuned = {"score": float(scores[i]), "threshold": best["anomaly_threshold"],
                     "flagged": bool(scores[i] >= best["anomaly_threshold"])}

            categories = {"xgb": set() if pred[i] == "Normal" else {CATEGORY[str(pred[i])]},
                          "anomaly": {"Unknown"} if untuned["flagged"] else set()}
            expert_system.CLASSIFIER_MIN_CONFIDENCE = 0.0
            for name, (use_xgb, use_anom, use_vib, use_volt) in ES_VARIANTS.items():
                categories[name] = rule_categories(
                    row, use_vib, use_volt,
                    prediction if use_xgb else None, untuned if use_anom else None,
                )
            expert_system.CLASSIFIER_MIN_CONFIDENCE = best["confidence_gate"]
            categories["tuned"] = rule_categories(row, prediction=prediction, anomaly=tuned)

            record = {"seed": seed, "fold": fold, "true": row.true_fault, "severity": row.severity}
            for name, cats in categories.items():
                record[f"{name}_label"] = predicted_label(cats, row.true_fault)
                record[f"{name}_detected"] = bool(cats)
            records.append(record)
    return pd.DataFrame(records), pd.DataFrame(tuned_params)


def metrics(df, key):
    label = df[f"{key}_label"]
    detected = df[f"{key}_detected"]
    is_fault = df["true"] != "Normal"
    out = {
        "macro_f1": f1_score(df["true"], label, labels=CLASSES, average="macro", zero_division=0),
        "accuracy": float((label == df["true"]).mean()),
        "detection_recall": float(detected[is_fault].mean()),
        "false_alarm_rate": float(detected[~is_fault].mean()),
    }
    for fault in FAULT_TYPES:
        rows = df["true"] == fault
        out[f"recall_{fault}"] = float((label[rows] == fault).mean())
    return out


def summarise(all_runs, setups):
    rows = []
    for name, key in setups.items():
        per_seed = pd.DataFrame([metrics(g, key) for _, g in all_runs.groupby("seed")])
        row = {"setup": name}
        for col in per_seed.columns:
            row[f"{col}_mean"] = per_seed[col].mean()
            row[f"{col}_std"] = per_seed[col].std()
        rows.append(row)
    return pd.DataFrame(rows)


def mcnemar(df, key_a, key_b):
    """Exact McNemar test on per-reading correctness."""
    a = df[f"{key_a}_label"] == df["true"]
    b = df[f"{key_b}_label"] == df["true"]
    only_a, only_b = int((a & ~b).sum()), int((~a & b).sum())
    if only_a + only_b == 0:
        return only_a, only_b, 1.0
    return only_a, only_b, binomtest(only_a, only_a + only_b, 0.5).pvalue


def severity_curve(all_runs, setups):
    faulty = all_runs[all_runs["true"] != "Normal"]
    rows = []
    for name, key in setups.items():
        for (fault, severity), g in faulty.groupby(["true", "severity"]):
            rows.append({"setup": name, "fault": fault, "severity": severity,
                         "detection_rate": g[f"{key}_detected"].mean(),
                         "correct_fault_rate": (g[f"{key}_label"] == fault).mean()})
    return pd.DataFrame(rows)


def fmt(summary, col):
    return [f"{m * 100:.1f} ± {s * 100:.1f}" for m, s in zip(summary[f"{col}_mean"], summary[f"{col}_std"])]


def markdown_table(summary, seed0, all_setups, reference="full"):
    cols = [("macro_f1", "Macro F1"), ("detection_recall", "Detection recall"),
            ("false_alarm_rate", "False alarm rate")] + [(f"recall_{f}", f"{f} recall") for f in FAULT_TYPES]
    lines = [f"| Setup | " + " | ".join(h for _, h in cols) + f" | McNemar vs {reference} (p) |",
             "|---" * (len(cols) + 2) + "|"]
    values = {c: fmt(summary, c) for c, _ in cols}
    for i, name in enumerate(summary["setup"]):
        key = all_setups[name]
        if key == reference:
            p_text = "–"
        else:
            ref_only, other_only, p = mcnemar(seed0, reference, key)
            p_text = f"{p:.2g} ({ref_only}/{other_only})"
        lines.append(f"| {name} | " + " | ".join(values[c][i] for c, _ in cols) + f" | {p_text} |")
    return "\n".join(lines)


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    started = time.perf_counter()
    runs = Parallel(n_jobs=len(SEEDS))(delayed(run_seed)(s) for s in SEEDS)
    all_runs = pd.concat([r for r, _ in runs], ignore_index=True)
    tuned_params = pd.concat([p for _, p in runs], ignore_index=True)
    all_runs.to_csv(RESULTS_DIR / "ablation_predictions.csv", index=False)
    tuned_params.to_csv(RESULTS_DIR / "tuned_params_per_fold.csv", index=False)

    components = summarise(all_runs, COMPONENT_SETUPS)
    modalities = summarise(all_runs, MODALITY_SETUPS)
    components.to_csv(RESULTS_DIR / "exp1_components.csv", index=False)
    modalities.to_csv(RESULTS_DIR / "exp2_modalities.csv", index=False)
    severity_curve(all_runs, COMPONENT_SETUPS).to_csv(RESULTS_DIR / "severity_curve.csv", index=False)

    seed0 = all_runs[all_runs["seed"] == 0]
    gate_counts = tuned_params["confidence_gate"].value_counts().to_dict()
    pct_counts = tuned_params["threshold_percentile"].value_counts().to_dict()
    report = [
        "# Ablation results (fault injection benchmark)",
        "",
        f"{len(SEEDS)} seeds x {N_FOLDS}-fold GroupKFold by vehicle; "
        f"{len(seed0)} test readings per seed (25% clean, 75% injected faults, severity 1-5). "
        "Values are mean ± std over seeds, in %. McNemar: exact test on seed 0, "
        "(readings only the reference got right / only the other setup got right).",
        "",
        "## Exp 1 - Component ablation",
        "",
        markdown_table(components, seed0, COMPONENT_SETUPS),
        "",
        "## Exp 1b - Tuned fusion vs untuned",
        "",
        "Confidence gate and anomaly threshold tuned per fold on the training vehicles only.",
        f"Chosen confidence gates (folds): {gate_counts}; threshold percentiles (folds): {pct_counts}",
        "",
        markdown_table(components[components["setup"].isin(["Full hybrid", "Full hybrid (tuned)"])],
                       seed0, COMPONENT_SETUPS, reference="tuned"),
        "",
        "## Exp 2 - Modality ablation",
        "",
        markdown_table(modalities, seed0, MODALITY_SETUPS),
        "",
    ]
    (RESULTS_DIR / "results.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Done in {time.perf_counter() - started:.0f} s. Results in {RESULTS_DIR}")


if __name__ == "__main__":
    main()
