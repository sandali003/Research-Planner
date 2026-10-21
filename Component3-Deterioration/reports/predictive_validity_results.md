# Predictive validity of the contextual assessment (Component 3, step 4)

2023 MOT tests joined to the same car's next test 9-16 months later in 2024. 435,411 cars with a follow-up; results on 87,078 held-out cars. Outcome: a major (or dangerous) defect at the 2024 test, overall or in the component.

## Ranking (higher is better)

| Target | Predictor | n | positive rate | ROC-AUC | PR-AUC | AUC within age band |
|---|---|---|---|---|---|---|
| Overall | A Age + mileage only | 87078 | 29.8% | 0.685 | 0.448 | 0.593 |
| Overall | B Current condition only | 87078 | 29.8% | 0.634 | 0.384 | 0.588 |
| Overall | C Proposed (contextual) | 87078 | 29.8% | 0.567 | 0.340 | 0.563 |
| Overall | C-tail Tail percentile | 87078 | 29.8% | 0.593 | 0.337 | 0.575 |
| Overall | D Proposed + condition | 87078 | 29.8% | 0.686 | 0.443 | 0.606 |
| Overall | E Combined (dual output) | 87078 | 29.8% | 0.700 | 0.476 | 0.621 |
| Overall | F Ablation: E without percentile | 87078 | 29.8% | 0.700 | 0.476 | 0.620 |
| Brakes | A Age + mileage only | 87078 | 6.6% | 0.729 | 0.138 | 0.619 |
| Brakes | B Current condition only | 87078 | 6.6% | 0.641 | 0.109 | 0.617 |
| Brakes | C Proposed (contextual) | 87078 | 6.6% | 0.538 | 0.094 | 0.559 |
| Brakes | C-tail Tail percentile | 87078 | 6.6% | 0.634 | 0.096 | 0.614 |
| Brakes | D Proposed + condition | 87078 | 6.6% | 0.747 | 0.150 | 0.672 |
| Brakes | E Combined (dual output) | 87078 | 6.6% | 0.754 | 0.162 | 0.675 |
| Brakes | F Ablation: E without percentile | 87078 | 6.6% | 0.754 | 0.163 | 0.674 |
| Suspension | A Age + mileage only | 87078 | 8.3% | 0.711 | 0.164 | 0.652 |
| Suspension | B Current condition only | 87078 | 8.3% | 0.626 | 0.124 | 0.580 |
| Suspension | C Proposed (contextual) | 87078 | 8.3% | 0.534 | 0.109 | 0.491 |
| Suspension | C-tail Tail percentile | 87078 | 8.3% | 0.619 | 0.110 | 0.575 |
| Suspension | D Proposed + condition | 87078 | 8.3% | 0.720 | 0.169 | 0.671 |
| Suspension | E Combined (dual output) | 87078 | 8.3% | 0.728 | 0.177 | 0.677 |
| Suspension | F Ablation: E without percentile | 87078 | 8.3% | 0.727 | 0.178 | 0.677 |
| Steering | A Age + mileage only | 87078 | 0.3% | 0.772 | 0.014 | 0.710 |
| Steering | B Current condition only | 87078 | 0.3% | 0.564 | 0.011 | 0.551 |
| Steering | C Proposed (contextual) | 87078 | 0.3% | 0.339 | 0.010 | 0.369 |
| Steering | C-tail Tail percentile | 87078 | 0.3% | 0.563 | 0.011 | 0.551 |
| Steering | D Proposed + condition | 87078 | 0.3% | 0.339 | 0.010 | 0.369 |
| Steering | E Combined (dual output) | 87078 | 0.3% | 0.791 | 0.023 | 0.734 |
| Steering | F Ablation: E without percentile | 87078 | 0.3% | 0.791 | 0.023 | 0.733 |
| Tyres | A Age + mileage only | 87078 | 5.2% | 0.585 | 0.066 | 0.575 |
| Tyres | B Current condition only | 87078 | 5.2% | 0.588 | 0.067 | 0.585 |
| Tyres | C Proposed (contextual) | 87078 | 5.2% | 0.550 | 0.066 | 0.550 |
| Tyres | C-tail Tail percentile | 87078 | 5.2% | 0.584 | 0.064 | 0.583 |
| Tyres | D Proposed + condition | 87078 | 5.2% | 0.627 | 0.080 | 0.621 |
| Tyres | E Combined (dual output) | 87078 | 5.2% | 0.632 | 0.082 | 0.627 |
| Tyres | F Ablation: E without percentile | 87078 | 5.2% | 0.632 | 0.082 | 0.627 |
| Emissions Leaks | A Age + mileage only | 87078 | 3.1% | 0.832 | 0.110 | 0.701 |
| Emissions Leaks | B Current condition only | 87078 | 3.1% | 0.614 | 0.089 | 0.580 |
| Emissions Leaks | C Proposed (contextual) | 87078 | 3.1% | 0.382 | 0.067 | 0.448 |
| Emissions Leaks | C-tail Tail percentile | 87078 | 3.1% | 0.613 | 0.069 | 0.579 |
| Emissions Leaks | D Proposed + condition | 87078 | 3.1% | 0.847 | 0.144 | 0.713 |
| Emissions Leaks | E Combined (dual output) | 87078 | 3.1% | 0.852 | 0.165 | 0.730 |
| Emissions Leaks | F Ablation: E without percentile | 87078 | 3.1% | 0.852 | 0.165 | 0.731 |

AUC within age band: weighted mean ROC-AUC inside the age bands 0-6, 6-9, 9-12, 12-15, 15-100 years (age signal removed).

## Bootstrap 95% CI of the ROC-AUC gains

| Target | Comparison | AUC gain 95% CI |
|---|---|---|
| Overall | C Proposed (contextual) vs B | -0.069 to -0.066 |
| Overall | C-tail Tail percentile vs B | -0.042 to -0.039 |
| Overall | C-tail Tail percentile vs C | +0.025 to +0.028 |
| Overall | D Proposed + condition vs B | +0.049 to +0.055 |
| Overall | E Combined (dual output) vs B | +0.064 to +0.070 |
| Overall | E Combined (dual output) vs A | +0.014 to +0.017 |
| Overall | E Combined (dual output) vs F | -0.000 to +0.000 |
| Brakes | C Proposed (contextual) vs B | -0.107 to -0.099 |
| Brakes | C-tail Tail percentile vs B | -0.009 to -0.006 |
| Brakes | C-tail Tail percentile vs C | +0.091 to +0.100 |
| Brakes | D Proposed + condition vs B | +0.100 to +0.111 |
| Brakes | E Combined (dual output) vs B | +0.107 to +0.119 |
| Brakes | E Combined (dual output) vs A | +0.021 to +0.028 |
| Brakes | E Combined (dual output) vs F | -0.000 to +0.000 |
| Suspension | C Proposed (contextual) vs B | -0.096 to -0.088 |
| Suspension | C-tail Tail percentile vs B | -0.007 to -0.005 |
| Suspension | C-tail Tail percentile vs C | +0.081 to +0.089 |
| Suspension | D Proposed + condition vs B | +0.090 to +0.099 |
| Suspension | E Combined (dual output) vs B | +0.097 to +0.107 |
| Suspension | E Combined (dual output) vs A | +0.014 to +0.020 |
| Suspension | E Combined (dual output) vs F | +0.000 to +0.001 |
| Steering | C Proposed (contextual) vs B | -0.248 to -0.201 |
| Steering | C-tail Tail percentile vs B | -0.000 to +0.000 |
| Steering | C-tail Tail percentile vs C | +0.202 to +0.247 |
| Steering | D Proposed + condition vs B | -0.247 to -0.198 |
| Steering | E Combined (dual output) vs B | +0.206 to +0.249 |
| Steering | E Combined (dual output) vs A | +0.010 to +0.028 |
| Steering | E Combined (dual output) vs F | -0.000 to +0.000 |
| Tyres | C Proposed (contextual) vs B | -0.043 to -0.034 |
| Tyres | C-tail Tail percentile vs B | -0.005 to -0.003 |
| Tyres | C-tail Tail percentile vs C | +0.030 to +0.039 |
| Tyres | D Proposed + condition vs B | +0.034 to +0.044 |
| Tyres | E Combined (dual output) vs B | +0.039 to +0.049 |
| Tyres | E Combined (dual output) vs A | +0.042 to +0.055 |
| Tyres | E Combined (dual output) vs F | -0.000 to +0.000 |
| Emissions Leaks | C Proposed (contextual) vs B | -0.239 to -0.226 |
| Emissions Leaks | C-tail Tail percentile vs B | -0.002 to -0.001 |
| Emissions Leaks | C-tail Tail percentile vs C | +0.223 to +0.237 |
| Emissions Leaks | D Proposed + condition vs B | +0.225 to +0.239 |
| Emissions Leaks | E Combined (dual output) vs B | +0.231 to +0.246 |
| Emissions Leaks | E Combined (dual output) vs A | +0.017 to +0.023 |
| Emissions Leaks | E Combined (dual output) vs F | +0.000 to +0.000 |

## Flags: precision / recall / F1 (A and B flag the same number of cars as the app's C-tail flags)

| Target | Flag | Predictor | flagged | precision | recall | f1 |
|---|---|---|---|---|---|---|
| Overall | High (worst 10%) | C-tail Tail percentile | 5.0% | 36.5% | 6.1% | 10.5% |
| Overall | High (worst 10%) | A Age + mileage only | 5.0% | 53.0% | 8.9% | 15.3% |
| Overall | High (worst 10%) | B Current condition only | 5.0% | 45.5% | 7.6% | 13.1% |
| Overall | High + Slightly high (worst 25%) | C-tail Tail percentile | 12.5% | 32.7% | 13.7% | 19.3% |
| Overall | High + Slightly high (worst 25%) | A Age + mileage only | 12.5% | 50.2% | 21.1% | 29.7% |
| Overall | High + Slightly high (worst 25%) | B Current condition only | 12.5% | 44.3% | 18.6% | 26.2% |
| Brakes | High (worst 10%) | C-tail Tail percentile | 3.6% | 11.9% | 6.4% | 8.3% |
| Brakes | High (worst 10%) | A Age + mileage only | 3.6% | 17.2% | 9.3% | 12.1% |
| Brakes | High (worst 10%) | B Current condition only | 3.6% | 19.0% | 10.3% | 13.3% |
| Brakes | High + Slightly high (worst 25%) | C-tail Tail percentile | 11.9% | 12.7% | 23.1% | 16.4% |
| Brakes | High + Slightly high (worst 25%) | A Age + mileage only | 11.9% | 16.4% | 29.6% | 21.1% |
| Brakes | High + Slightly high (worst 25%) | B Current condition only | 11.9% | 15.3% | 27.8% | 19.8% |
| Suspension | High (worst 10%) | C-tail Tail percentile | 3.4% | 10.3% | 4.2% | 6.0% |
| Suspension | High (worst 10%) | A Age + mileage only | 3.4% | 21.9% | 9.0% | 12.8% |
| Suspension | High (worst 10%) | B Current condition only | 3.4% | 19.0% | 7.8% | 11.1% |
| Suspension | High + Slightly high (worst 25%) | C-tail Tail percentile | 12.1% | 15.5% | 22.6% | 18.4% |
| Suspension | High + Slightly high (worst 25%) | A Age + mileage only | 12.1% | 18.8% | 27.5% | 22.3% |
| Suspension | High + Slightly high (worst 25%) | B Current condition only | 12.1% | 17.3% | 25.3% | 20.5% |
| Steering | High (worst 10%) | C-tail Tail percentile | 0.8% | 6.0% | 13.4% | 8.3% |
| Steering | High (worst 10%) | A Age + mileage only | 0.8% | 2.2% | 5.0% | 3.1% |
| Steering | High (worst 10%) | B Current condition only | 0.8% | 6.0% | 13.4% | 8.3% |
| Steering | High + Slightly high (worst 25%) | C-tail Tail percentile | 0.8% | 6.0% | 13.4% | 8.3% |
| Steering | High + Slightly high (worst 25%) | A Age + mileage only | 0.8% | 2.2% | 5.0% | 3.1% |
| Steering | High + Slightly high (worst 25%) | B Current condition only | 0.8% | 6.0% | 13.4% | 8.3% |
| Tyres | High (worst 10%) | C-tail Tail percentile | 4.8% | 9.3% | 8.6% | 8.9% |
| Tyres | High (worst 10%) | A Age + mileage only | 4.8% | 7.8% | 7.3% | 7.5% |
| Tyres | High (worst 10%) | B Current condition only | 4.8% | 9.3% | 8.6% | 8.9% |
| Tyres | High + Slightly high (worst 25%) | C-tail Tail percentile | 9.6% | 7.5% | 13.9% | 9.8% |
| Tyres | High + Slightly high (worst 25%) | A Age + mileage only | 9.6% | 7.5% | 13.9% | 9.8% |
| Tyres | High + Slightly high (worst 25%) | B Current condition only | 9.6% | 8.8% | 16.2% | 11.4% |
| Emissions Leaks | High (worst 10%) | C-tail Tail percentile | 2.5% | 19.0% | 15.5% | 17.0% |
| Emissions Leaks | High (worst 10%) | A Age + mileage only | 2.5% | 15.3% | 12.5% | 13.7% |
| Emissions Leaks | High (worst 10%) | B Current condition only | 2.5% | 26.3% | 21.4% | 23.6% |
| Emissions Leaks | High + Slightly high (worst 25%) | C-tail Tail percentile | 4.4% | 17.8% | 25.5% | 21.0% |
| Emissions Leaks | High + Slightly high (worst 25%) | A Age + mileage only | 4.4% | 13.8% | 19.8% | 16.3% |
| Emissions Leaks | High + Slightly high (worst 25%) | B Current condition only | 4.4% | 18.3% | 26.2% | 21.5% |
