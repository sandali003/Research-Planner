# Ablation results (fault injection benchmark)

5 seeds x 5-fold GroupKFold by vehicle; 6236 test readings per seed (25% clean, 75% injected faults, severity 1-5). Values are mean ± std over seeds, in %. McNemar: exact test on seed 0, (readings only the full system got right / only the other setup got right).

## Exp 1 - Component ablation

| Setup | Macro F1 | Detection recall | False alarm rate | Charging recall | Cooling recall | Vibration recall | McNemar vs full (p) |
|---|---|---|---|---|---|---|---|
| Rules only | 26.6 ± 0.3 | 17.7 ± 0.2 | 4.0 ± 0.0 | 0.0 ± 0.0 | 3.9 ± 0.5 | 38.3 ± 0.3 | 0 (1750/151) |
| XGBoost only | 48.2 ± 0.2 | 41.4 ± 0.3 | 5.5 ± 0.0 | 55.3 ± 0.5 | 61.7 ± 0.4 | 0.0 ± 0.0 | 7.6e-76 (607/127) |
| Anomaly only | 12.7 ± 0.0 | 43.0 ± 0.5 | 7.6 ± 0.3 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 (2449/121) |
| Rules + XGBoost | 63.5 ± 0.2 | 55.2 ± 0.3 | 9.1 ± 0.0 | 55.3 ± 0.5 | 61.9 ± 0.4 | 38.3 ± 0.3 | 8.5e-22 (0/71) |
| Rules + Anomaly | 28.3 ± 0.3 | 44.0 ± 0.4 | 9.6 ± 0.2 | 0.0 ± 0.0 | 3.9 ± 0.5 | 38.3 ± 0.3 | 0 (1750/64) |
| Full hybrid | 64.1 ± 0.2 | 63.2 ± 0.4 | 13.9 ± 0.2 | 55.3 ± 0.5 | 61.9 ± 0.4 | 38.3 ± 0.3 | – |

## Exp 2 - Modality ablation

| Setup | Macro F1 | Detection recall | False alarm rate | Charging recall | Cooling recall | Vibration recall | McNemar vs full (p) |
|---|---|---|---|---|---|---|---|
| OBD only | 11.9 ± 0.2 | 5.3 ± 0.2 | 4.0 ± 0.0 | 0.0 ± 0.0 | 3.9 ± 0.5 | 0.0 ± 0.0 | 0 (2353/151) |
| OBD + Vibration | 28.3 ± 0.3 | 44.0 ± 0.4 | 9.6 ± 0.2 | 0.0 ± 0.0 | 3.9 ± 0.5 | 38.3 ± 0.3 | 0 (1750/64) |
| OBD + Voltage | 48.1 ± 0.2 | 43.5 ± 0.3 | 9.1 ± 0.0 | 55.3 ± 0.5 | 61.9 ± 0.4 | 0.0 ± 0.0 | 5.1e-106 (603/71) |
| OBD + Vibration + Voltage | 64.1 ± 0.2 | 63.2 ± 0.4 | 13.9 ± 0.2 | 55.3 ± 0.5 | 61.9 ± 0.4 | 38.3 ± 0.3 | – |
