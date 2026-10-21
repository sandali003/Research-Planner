# Expected-condition baseline (Component 3, step 2)

Data: UK MOT 2023, Toyota Yaris / Vitz / Corolla, 525,901 tests of 508,109 vehicles. Test set: 20% of vehicles, never seen in training.
Grades follow the DVSA defect categories (mot_condition.py). Lower log loss / RPS is better; PIT KS is the distance of the percentiles from uniform (0 = perfectly calibrated).

| Target | Model | log_loss | rps | pit_ks |
|---|---|---|---|---|
| Overall | Marginal | 1.4152 | 0.1836 | 0.0043 |
| Overall | Platform only | 1.4111 | 0.1829 | 0.0037 |
| Overall | Age only | 1.3396 | 0.1667 | 0.0029 |
| Overall | Proposed (age + km + platform + fuel + engine) | 1.3187 | 0.1623 | 0.0028 |
| Brakes | Marginal | 0.7254 | 0.1058 | 0.0039 |
| Brakes | Platform only | 0.719 | 0.1047 | 0.0041 |
| Brakes | Age only | 0.685 | 0.0999 | 0.0023 |
| Brakes | Proposed (age + km + platform + fuel + engine) | 0.6775 | 0.0983 | 0.0049 |
| Suspension | Marginal | 0.7959 | 0.1212 | 0.003 |
| Suspension | Platform only | 0.7935 | 0.1211 | 0.0025 |
| Suspension | Age only | 0.7141 | 0.11 | 0.0021 |
| Suspension | Proposed (age + km + platform + fuel + engine) | 0.6995 | 0.1072 | 0.0025 |
| Steering | Marginal | 0.063 | 0.0058 | 0.002 |
| Steering | Platform only | 0.0614 | 0.0058 | 0.0024 |
| Steering | Age only | 0.0588 | 0.0058 | 0.0021 |
| Steering | Proposed (age + km + platform + fuel + engine) | 0.0568 | 0.0058 | 0.0018 |
| Tyres | Marginal | 0.7298 | 0.0987 | 0.0024 |
| Tyres | Platform only | 0.7297 | 0.0987 | 0.0046 |
| Tyres | Age only | 0.7275 | 0.0983 | 0.0025 |
| Tyres | Proposed (age + km + platform + fuel + engine) | 0.7245 | 0.0977 | 0.0022 |
| Emissions Leaks | Marginal | 0.2662 | 0.0391 | 0.0015 |
| Emissions Leaks | Platform only | 0.2604 | 0.0389 | 0.0028 |
| Emissions Leaks | Age only | 0.23 | 0.0373 | 0.0024 |
| Emissions Leaks | Proposed (age + km + platform + fuel + engine) | 0.2197 | 0.0364 | 0.0023 |

Best model per target (log loss):

| Target | Model |
|---|---|
| Brakes | Proposed (age + km + platform + fuel + engine) |
| Emissions Leaks | Proposed (age + km + platform + fuel + engine) |
| Overall | Proposed (age + km + platform + fuel + engine) |
| Steering | Proposed (age + km + platform + fuel + engine) |
| Suspension | Proposed (age + km + platform + fuel + engine) |
| Tyres | Proposed (age + km + platform + fuel + engine) |

## Expected overall condition by age (petrol, median engine size and km per year)

Expected grade: 5 Good ... 1 Dangerous.

| platform | age_years | odometer_km | expected_grade | p_major_or_worse |
|---|---|---|---|---|
| Yaris | 2 | 17118.0 | 4.77 | 0.051 |
| Yaris | 4 | 34236.0 | 4.42 | 0.092 |
| Yaris | 6 | 51354.0 | 4.26 | 0.125 |
| Yaris | 8 | 68472.0 | 4.11 | 0.155 |
| Yaris | 10 | 85590.0 | 3.77 | 0.269 |
| Yaris | 12 | 102708.0 | 3.67 | 0.3 |
| Yaris | 14 | 119826.0 | 3.48 | 0.351 |
| Yaris | 16 | 136944.0 | 3.27 | 0.399 |
| Yaris | 18 | 154062.0 | 3.15 | 0.417 |
| Yaris | 20 | 171180.0 | 3.08 | 0.441 |
| Corolla | 2 | 18844.0 | 4.79 | 0.038 |
| Corolla | 4 | 37688.0 | 4.53 | 0.079 |
| Corolla | 6 | 56532.0 | 4.33 | 0.107 |
| Corolla | 8 | 75376.0 | 4.13 | 0.158 |
| Corolla | 10 | 94220.0 | 3.9 | 0.236 |
| Corolla | 12 | 113064.0 | 3.73 | 0.281 |
| Corolla | 14 | 131908.0 | 3.53 | 0.319 |
| Corolla | 16 | 150752.0 | 3.23 | 0.375 |
| Corolla | 18 | 169596.0 | 3.05 | 0.442 |
| Corolla | 20 | 188440.0 | 2.97 | 0.47 |
