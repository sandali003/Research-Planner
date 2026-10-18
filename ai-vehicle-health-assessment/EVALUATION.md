# Evaluation report (grouped/stratified 5-fold CV)

All datasets are synthetic or rule-labelled; scores measure recovery of the label rule, not real-vehicle accuracy.

### inspection  (20000 rows, target `health_class`, GroupKFold 5-fold)
Metric: macro-F1 (mean ± std over folds)

| model | score |
|---|---|
| HistGB | 0.810 ± 0.008 |
| Baseline(majority/mean) | 0.242 ± 0.002 |
| ShallowTree(depth3) | 0.529 ± 0.003 |

Per-class recall (HistGB, pooled folds): Healthy=0.88 (n=7874), Needs Attention=0.90 (n=11404), Poor=0.60 (n=722)

Confusion matrix (rows=true, cols=pred):
```
                 Healthy  Needs Attention  Poor
Healthy             6891              983     0
Needs Attention      971            10274   159
Poor                   0              288   434
```

**Flags:** none

### external_sensor  (10000 rows, target `health_class_simulated`, GroupKFold 5-fold)
Metric: macro-F1 (mean ± std over folds)

| model | score |
|---|---|
| HistGB | 0.836 ± 0.027 |
| Baseline(majority/mean) | 0.305 ± 0.001 |
| ShallowTree(depth3) | 0.699 ± 0.075 |

Per-class recall (HistGB, pooled folds): Fair=0.81 (n=1351), Good=0.98 (n=8438), Poor=0.65 (n=211)

Confusion matrix (rows=true, cols=pred):
```
      Fair  Good  Poor
Fair  1092   232    27
Good   195  8243     0
Poor    73     0   138
```

**Flags:** none

### battery  (8000 rows, target `fault_label`, GroupKFold 5-fold)
Metric: macro-F1 (mean ± std over folds)

| model | score |
|---|---|
| HistGB | 0.832 ± 0.052 |
| Baseline(majority/mean) | 0.206 ± 0.003 |
| ShallowTree(depth3) | 0.734 ± 0.020 |

Per-class recall (HistGB, pooled folds): Charging_System_Warning=0.95 (n=1007), Cooling_System_Warning=0.92 (n=788), Engine_Abnormality_Suspected=0.49 (n=602), Normal=0.96 (n=5603)

Confusion matrix (rows=true, cols=pred):
```
                              Charging_System_Warning  Cooling_System_Warning  Engine_Abnormality_Suspected  Normal
Charging_System_Warning                           955                       0                             0      52
Cooling_System_Warning                             10                     725                            24      29
Engine_Abnormality_Suspected                        4                      98                           297     203
Normal                                             38                      84                            93    5388
```

**Flags:** none

### petrol_engine  (8000 rows, target `Target_Score`, KFold 5-fold)
Metric: R² (mean ± std over folds)

| model | score |
|---|---|
| HistGB | 0.998 ± 0.000 |
| Baseline(majority/mean) | -0.001 ± 0.001 |
| ShallowTree(depth3) | 0.810 ± 0.004 |

**Flags:** NEAR-PERFECT SCORE: suspicious / trivially separable.

### engine_data  (19535 rows, target `Engine Condition`, StratifiedKFold 5-fold)
Metric: macro-F1 (mean ± std over folds)

| model | score |
|---|---|
| HistGB | 0.605 ± 0.004 |
| Baseline(majority/mean) | 0.387 ± 0.000 |
| ShallowTree(depth3) | 0.545 ± 0.022 |

Per-class recall (HistGB, pooled folds): 0=0.37 (n=7218), 1=0.84 (n=12317)

Confusion matrix (rows=true, cols=pred):
```
      0      1
0  2695   4523
1  2030  10287
```

**Flags:** none

### engine_fault  (10000 rows, target `Engine_Condition`, StratifiedKFold 5-fold)
Metric: macro-F1 (mean ± std over folds)

| model | score |
|---|---|
| HistGB | 0.289 ± 0.008 |
| Baseline(majority/mean) | 0.249 ± 0.000 |
| ShallowTree(depth3) | 0.255 ± 0.007 |

Per-class recall (HistGB, pooled folds): 0=0.90 (n=5963), 1=0.09 (n=3037), 2=0.00 (n=1000)

Confusion matrix (rows=true, cols=pred):
```
      0    1   2
0  5371  559  33
1  2739  281  17
2   900   96   4
```

**Flags:** NO SIGNAL: barely beats the trivial baseline.
