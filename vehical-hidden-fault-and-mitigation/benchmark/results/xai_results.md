# XAI evaluation (ground-truth root causes)

3 seeds x 5-fold GroupKFold by vehicle. Explained readings = injected faults the model reported. Values in %, mean ± std over seeds. n = explained readings per seed.
Flip = the model stops reporting the fault after the group is reset to its normal (median) value.
Output drop = fall in predicted-class probability (classifier) or anomaly score (anomaly model).

| Model | Fault | n | SHAP top-1 | SHAP top-2 | z-score top-1 | Random | Flip (reset top) | Flip (reset random) | Stability | Output drop (top / random) |
|---|---|---|---|---|---|---|---|---|---|---|
| One-Class SVM anomaly | Cooling | 300 | 90.8 ± 2.5 | 97.1 ± 0.8 | 88.1 ± 0.7 | 25.0 ± 0.0 | 91.0 ± 1.5 | 5.7 ± 2.4 | 99.3 ± 0.1 | 2.713 / 0.084 |
| One-Class SVM anomaly | Vibration | 300 | 98.0 ± 0.3 | 100.0 ± 0.0 | 96.3 ± 0.0 | 25.0 ± 0.0 | 94.1 ± 0.4 | 5.9 ± 0.5 | 99.8 ± 0.1 | 2.966 / 0.090 |
| XGBoost classifier | Charging | 882 | 97.2 ± 0.3 | 98.4 ± 0.2 | 97.1 ± 0.3 | 25.0 ± 0.0 | 99.2 ± 0.2 | 2.2 ± 0.1 | 99.1 ± 0.2 | 0.975 / 0.011 |
| XGBoost classifier | Cooling | 962 | 69.2 ± 0.8 | 80.5 ± 1.0 | 93.4 ± 0.9 | 25.0 ± 0.0 | 83.1 ± 0.7 | 14.7 ± 0.2 | 94.2 ± 0.6 | 0.745 / 0.096 |

## SHAP top-1 accuracy by fault severity (%)

| model | fault | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| One-Class SVM anomaly | Cooling | 40.4 | 74.2 | 93.5 | 98.7 | 100.0 |
| One-Class SVM anomaly | Vibration | 96.9 | 93.0 | 96.9 | 100.0 | 99.7 |
| XGBoost classifier | Charging | 50.0 | 87.9 | 98.5 | 99.8 | 100.0 |
| XGBoost classifier | Cooling | 9.1 | 32.2 | 39.5 | 91.7 | 97.7 |
