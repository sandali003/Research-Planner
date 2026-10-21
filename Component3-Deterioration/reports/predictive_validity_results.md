# Predictive validity of the contextual assessment (Component 3, step 4)

2023 MOT tests joined to the same car's next test 9-16 months later in 2024. 435,411 cars with a follow-up; results on 87,078 held-out cars. Outcome: a major (or dangerous) defect at the 2024 test, overall or in the component.

## Ranking (higher is better)

| Target | Predictor | n | positive rate | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|
| Overall | A Age + mileage only | 87078 | 29.8% | 0.685 | 0.448 |
| Overall | B Current condition only | 87078 | 29.8% | 0.634 | 0.384 |
| Overall | C Proposed (contextual) | 87078 | 29.8% | 0.567 | 0.340 |
| Overall | D Proposed + condition | 87078 | 29.8% | 0.686 | 0.443 |
| Brakes | A Age + mileage only | 87078 | 6.6% | 0.729 | 0.138 |
| Brakes | B Current condition only | 87078 | 6.6% | 0.641 | 0.109 |
| Brakes | C Proposed (contextual) | 87078 | 6.6% | 0.538 | 0.094 |
| Brakes | D Proposed + condition | 87078 | 6.6% | 0.747 | 0.150 |
| Suspension | A Age + mileage only | 87078 | 8.3% | 0.711 | 0.164 |
| Suspension | B Current condition only | 87078 | 8.3% | 0.626 | 0.124 |
| Suspension | C Proposed (contextual) | 87078 | 8.3% | 0.534 | 0.109 |
| Suspension | D Proposed + condition | 87078 | 8.3% | 0.720 | 0.169 |
| Steering | A Age + mileage only | 87078 | 0.3% | 0.772 | 0.014 |
| Steering | B Current condition only | 87078 | 0.3% | 0.564 | 0.011 |
| Steering | C Proposed (contextual) | 87078 | 0.3% | 0.339 | 0.010 |
| Steering | D Proposed + condition | 87078 | 0.3% | 0.339 | 0.010 |
| Tyres | A Age + mileage only | 87078 | 5.2% | 0.585 | 0.066 |
| Tyres | B Current condition only | 87078 | 5.2% | 0.588 | 0.067 |
| Tyres | C Proposed (contextual) | 87078 | 5.2% | 0.550 | 0.066 |
| Tyres | D Proposed + condition | 87078 | 5.2% | 0.627 | 0.080 |
| Emissions Leaks | A Age + mileage only | 87078 | 3.1% | 0.832 | 0.110 |
| Emissions Leaks | B Current condition only | 87078 | 3.1% | 0.614 | 0.089 |
| Emissions Leaks | C Proposed (contextual) | 87078 | 3.1% | 0.382 | 0.067 |
| Emissions Leaks | D Proposed + condition | 87078 | 3.1% | 0.847 | 0.144 |

## Bootstrap 95% CI of the ROC-AUC gain over B (current condition only)

| Target | Comparison | AUC gain 95% CI |
|---|---|---|
| Overall | C Proposed (contextual) vs B | -0.069 to -0.066 |
| Overall | D Proposed + condition vs B | +0.049 to +0.054 |
| Brakes | C Proposed (contextual) vs B | -0.107 to -0.099 |
| Brakes | D Proposed + condition vs B | +0.100 to +0.111 |
| Suspension | C Proposed (contextual) vs B | -0.095 to -0.088 |
| Suspension | D Proposed + condition vs B | +0.089 to +0.098 |
| Steering | C Proposed (contextual) vs B | -0.249 to -0.201 |
| Steering | D Proposed + condition vs B | -0.249 to -0.201 |
| Tyres | C Proposed (contextual) vs B | -0.043 to -0.034 |
| Tyres | D Proposed + condition vs B | +0.034 to +0.044 |
| Emissions Leaks | C Proposed (contextual) vs B | -0.238 to -0.225 |
| Emissions Leaks | D Proposed + condition vs B | +0.225 to +0.240 |

## Flags: precision / recall / F1 (A and B flag the same number of cars as C)

| Target | Flag | Predictor | flagged | precision | recall | f1 |
|---|---|---|---|---|---|---|
| Overall | High (worst 10%) | C Proposed (contextual) | 8.2% | 36.2% | 10.0% | 15.6% |
| Overall | High (worst 10%) | A Age + mileage only | 8.2% | 52.0% | 14.3% | 22.4% |
| Overall | High (worst 10%) | B Current condition only | 8.2% | 44.8% | 12.3% | 19.3% |
| Overall | High + Slightly high (worst 25%) | C Proposed (contextual) | 22.7% | 35.3% | 27.0% | 30.6% |
| Overall | High + Slightly high (worst 25%) | A Age + mileage only | 22.7% | 48.1% | 36.7% | 41.6% |
| Overall | High + Slightly high (worst 25%) | B Current condition only | 22.7% | 43.5% | 33.2% | 37.7% |
| Brakes | High (worst 10%) | C Proposed (contextual) | 7.9% | 14.5% | 17.5% | 15.8% |
| Brakes | High (worst 10%) | A Age + mileage only | 7.9% | 16.9% | 20.3% | 18.5% |
| Brakes | High (worst 10%) | B Current condition only | 7.9% | 17.2% | 20.7% | 18.8% |
| Brakes | High + Slightly high (worst 25%) | C Proposed (contextual) | 19.7% | 12.6% | 37.5% | 18.8% |
| Brakes | High + Slightly high (worst 25%) | A Age + mileage only | 19.7% | 14.9% | 44.4% | 22.3% |
| Brakes | High + Slightly high (worst 25%) | B Current condition only | 19.7% | 13.9% | 41.3% | 20.8% |
| Suspension | High (worst 10%) | C Proposed (contextual) | 8.8% | 15.1% | 15.9% | 15.5% |
| Suspension | High (worst 10%) | A Age + mileage only | 8.8% | 19.6% | 20.7% | 20.1% |
| Suspension | High (worst 10%) | B Current condition only | 8.8% | 18.5% | 19.6% | 19.0% |
| Suspension | High + Slightly high (worst 25%) | C Proposed (contextual) | 15.8% | 14.9% | 28.3% | 19.5% |
| Suspension | High + Slightly high (worst 25%) | A Age + mileage only | 15.8% | 18.1% | 34.5% | 23.8% |
| Suspension | High + Slightly high (worst 25%) | B Current condition only | 15.8% | 16.8% | 32.0% | 22.1% |
| Steering | High (worst 10%) | C Proposed (contextual) | 0.8% | 6.0% | 13.4% | 8.3% |
| Steering | High (worst 10%) | A Age + mileage only | 0.8% | 2.2% | 5.0% | 3.1% |
| Steering | High (worst 10%) | B Current condition only | 0.8% | 6.0% | 13.4% | 8.3% |
| Steering | High + Slightly high (worst 25%) | C Proposed (contextual) | 0.8% | 6.0% | 13.4% | 8.3% |
| Steering | High + Slightly high (worst 25%) | A Age + mileage only | 0.8% | 2.2% | 5.0% | 3.1% |
| Steering | High + Slightly high (worst 25%) | B Current condition only | 0.8% | 6.0% | 13.4% | 8.3% |
| Tyres | High (worst 10%) | C Proposed (contextual) | 5.2% | 8.8% | 8.8% | 8.8% |
| Tyres | High (worst 10%) | A Age + mileage only | 5.2% | 7.8% | 7.8% | 7.8% |
| Tyres | High (worst 10%) | B Current condition only | 5.2% | 9.2% | 9.2% | 9.2% |
| Tyres | High + Slightly high (worst 25%) | C Proposed (contextual) | 26.9% | 8.4% | 43.3% | 14.1% |
| Tyres | High + Slightly high (worst 25%) | A Age + mileage only | 26.9% | 7.0% | 36.1% | 11.7% |
| Tyres | High + Slightly high (worst 25%) | B Current condition only | 26.9% | 8.4% | 43.4% | 14.1% |
| Emissions Leaks | High (worst 10%) | C Proposed (contextual) | 3.5% | 19.8% | 22.5% | 21.1% |
| Emissions Leaks | High (worst 10%) | A Age + mileage only | 3.5% | 14.6% | 16.6% | 15.5% |
| Emissions Leaks | High (worst 10%) | B Current condition only | 3.5% | 20.9% | 23.8% | 22.2% |
| Emissions Leaks | High + Slightly high (worst 25%) | C Proposed (contextual) | 4.6% | 17.5% | 26.2% | 21.0% |
| Emissions Leaks | High + Slightly high (worst 25%) | A Age + mileage only | 4.6% | 13.7% | 20.5% | 16.4% |
| Emissions Leaks | High + Slightly high (worst 25%) | B Current condition only | 4.6% | 17.7% | 26.4% | 21.2% |
