# Counterfactuals and XAI reliability (fault injection benchmark)

3 seeds x 5-fold GroupKFold by vehicle; same test readings as the other benchmarks.

## Counterfactual repair targets

Readings = injected faults the model reported. Values in %, mean ± std over seeds; n per seed. Right sensor = only the injected sensor is changed. Plausible = the minimal target is already inside the healthy 5th-95th percentile range; the minimal change stops at the model's decision boundary, so this is often outside it, which is why the system shows the healthy range as the repair goal. Restoration = share of the injected change that has to be undone to clear the alarm (median).

| Model | Fault | n | Valid | Right sensor | Single sensor | Plausible target | Restoration needed (median) |
|---|---|---|---|---|---|---|---|
| One-Class SVM anomaly | Cooling | 1093 | 99.3 ± 0.1 | 92.8 ± 0.2 | 96.1 ± 0.2 | 21.4 ± 0.4 | 50% |
| One-Class SVM anomaly | Vibration | 792 | 99.4 ± 0.2 | 97.0 ± 0.2 | 99.1 ± 0.2 | 42.8 ± 1.0 | 64% |
| XGBoost classifier | Charging | 882 | 99.7 ± 0.1 | 98.0 ± 0.5 | 99.7 ± 0.2 | 1.5 ± 0.4 | 43% |
| XGBoost classifier | Cooling | 962 | 99.7 ± 0.1 | 94.1 ± 0.3 | 98.6 ± 0.2 | 34.6 ± 0.6 | 42% |

## XAI reliability flag (classifier)

Flag = the SHAP root cause is not a sensor that can explain the predicted fault (expert_system.EXPECTED_CAUSES). Pooled over seeds.

| Readings | n | Flagged low reliability | Accuracy if reliable | Accuracy if flagged |
|---|---|---|---|---|
| All classifier faults | 6049 | 21.9% | 97.4% | 64.1% |
| On clean readings (false alarms) | 258 | 82.6% | 0.0% | 0.0% |

Fisher exact test (flagged vs reliable, correct vs wrong): odds ratio 20.81, p = 9.1e-227. Wrong classifier faults caught by the flag: 79.4%.
