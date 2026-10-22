"""Prints the accuracy of the Component 2 models and the hybrid system.

Read-only: reads the saved metadata and benchmark results, trains nothing.
    python show_accuracy.py            summary
    python show_accuracy.py --classes  also per-class results of the classifier
"""

from pathlib import Path
import json
import subprocess
import sys

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
RESULTS_DIR = BASE_DIR / "benchmark" / "results"


def pct(x):
    return f"{100 * x:.1f}%"


classifier = json.loads((MODEL_DIR / "model_metadata.json").read_text())
anomaly = json.loads((MODEL_DIR / "obd_anomaly_metadata.json").read_text())

print("===== 1. XGBOOST FAULT CLASSIFIER (known faults) =====")
test = classifier["test_metrics"]
val = classifier["cv_results"][classifier["model"]]
print("Validation (grouped 5-fold CV on the training data):")
print(f"  accuracy {pct(val['accuracy']['mean'])} +- {pct(val['accuracy']['std'])}, "
      f"balanced accuracy {pct(val['balanced_accuracy']['mean'])}, macro F1 {val['macro_f1']['mean']:.3f}")
print("Test (held-out 20%, never seen in training):")
print(f"Test accuracy:          {pct(test['accuracy'])}")
print(f"Test balanced accuracy: {pct(test['balanced_accuracy'])}")
print(f"Test macro F1:          {test['macro_f1']:.3f}")
print(f"Baseline (Logistic Regression) macro F1: {classifier['baseline_test_macro_f1']:.3f}")
print("\nModels compared (grouped 5-fold CV macro F1):")
for name, scores in classifier["cv_results"].items():
    f1 = scores["macro_f1"]
    chosen = "  <- selected" if name == classifier["model"] else ""
    print(f"  {name:<20} {f1['mean']:.3f} +- {f1['std']:.3f}{chosen}")

print("\n===== 2. ONE-CLASS SVM ANOMALY MODEL (hidden faults) =====")
best = anomaly["results"][anomaly["model"]]
print(f"ROC-AUC:          {best['roc_auc']:.3f}")
print(f"PR-AUC:           {best['pr_auc']:.3f}")
print(f"Recall:           {pct(best['recall'])}")
print(f"Precision:        {pct(best['precision'])}")
print(f"False alarm rate: {pct(best['false_alarm_rate'])}")
print("\nModels compared (ROC-AUC):")
for name, scores in anomaly["results"].items():
    chosen = "  <- selected" if name == anomaly["model"] else ""
    print(f"  {name:<20} {scores['roc_auc']:.3f}{chosen}")

print("\n===== 3. FULL HYBRID SYSTEM (fault injection benchmark) =====")
exp1 = pd.read_csv(RESULTS_DIR / "exp1_components.csv")
print(f"{'Setup':<28}{'Macro F1':>10}{'Recall':>10}{'False alarms':>14}")
for _, row in exp1.iterrows():
    print(f"{row['setup']:<28}{pct(row['macro_f1_mean']):>10}"
          f"{pct(row['detection_recall_mean']):>10}{pct(row['false_alarm_rate_mean']):>14}")

print("\nSensors used (macro F1):")
exp2 = pd.read_csv(RESULTS_DIR / "exp2_modalities.csv")
for _, row in exp2.iterrows():
    print(f"  {row['setup']:<28}{pct(row['macro_f1_mean']):>8}")

print("\n===== 4. XAI ROOT CAUSE (SHAP top-1 accuracy, random = 25%) =====")
xai = pd.read_csv(RESULTS_DIR / "xai_summary.csv")
for _, row in xai.iterrows():
    print(f"  {row['Model']:<24}{row['Fault']:<12}{row['SHAP top-1']}%")

if "--classes" in sys.argv:
    print("\n===== 5. CLASSIFIER PER CLASS =====")
    subprocess.run([sys.executable, str(BASE_DIR / "evaluate_battery_classes.py")], cwd=BASE_DIR, check=True)
