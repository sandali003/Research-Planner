# Condition effect on sale price (Component 4, model 2)

US wholesale auction sales 2014-2015: 473,287 sales (34,952 Toyota), condition 10-49 (higher is better). Target: log(selling price / market value MMR). Test set: 20% of VINs.

## Test set

| Model | MAE log ratio | R2 log ratio | Price MAE $ | Toyota price MAE $ |
|---|---|---|---|---|
| No condition (baseline) | 0.1107 | 0.075 | 1027 | 872 |
| Linear | 0.1068 | 0.149 | 1029 | 867 |
| Gradient Boosting | 0.0977 | 0.257 | 905 | 748 |
| XGBoost | 0.0976 | 0.253 | 901 | 748 |

## Repeat-sale validation (1,276 cars sold twice in the test set)

Predicted change between the two sales vs the actual change in price-to-market ratio.

| Model | Pairs | Corr(predicted, actual change) | MAE of change | Right direction (|condition change| >= 5) |
|---|---|---|---|---|
| No condition (baseline) | 1276 | 0.286 | 0.1378 | 0.458 |
| Linear | 1276 | 0.336 | 0.1289 | 0.718 |
| Gradient Boosting | 1276 | 0.357 | 0.129 | 0.72 |
| XGBoost | 1276 | 0.374 | 0.1279 | 0.72 |

## Price by condition for a typical Toyota (best model: XGBoost; relative to condition 35)

| condition | price_vs_condition_35_pct |
|---|---|
| 15 | -24.3700008392334 |
| 20 | -16.329999923706055 |
| 25 | -6.760000228881836 |
| 30 | -3.0 |
| 35 | 0.0 |
| 40 | 2.0199999809265137 |
| 45 | 4.78000020980835 |
| 49 | 6.059999942779541 |

## Toyota condition distribution by age (for mapping Component 3 percentiles)

| age band | 0.05 | 0.1 | 0.25 | 0.5 | 0.75 | 0.9 | 0.95 |
|---|---|---|---|---|---|---|---|
| (-0.001, 2.0] | 25.0 | 28.0 | 35.0 | 39.0 | 43.0 | 46.0 | 48.0 |
| (2.0, 4.0] | 19.0 | 24.0 | 29.0 | 37.0 | 42.0 | 45.0 | 47.0 |
| (4.0, 6.0] | 19.0 | 19.0 | 25.0 | 31.0 | 37.0 | 42.0 | 44.0 |
| (6.0, 8.0] | 19.0 | 19.0 | 24.0 | 29.0 | 35.0 | 41.0 | 43.0 |
| (8.0, 10.0] | 19.0 | 19.0 | 21.0 | 27.0 | 34.0 | 37.0 | 41.0 |
| (10.0, 14.0] | 19.0 | 19.0 | 19.0 | 26.0 | 31.0 | 36.0 | 38.0 |
| (14.0, 30.0] | 19.0 | 19.0 | 19.0 | 21.0 | 27.0 | 33.0 | 36.0 |
