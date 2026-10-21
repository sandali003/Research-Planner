# Sri Lankan market valuation (Component 4, model 1)

ikman.lk Toyota car ads (Sep 2022 - Apr 2023, asking prices). 12,104 ads after cleaning, 6,421 sellers. Test set: 20% of sellers (2,488 ads), never seen in training.

## All models

| Feature set | Model | CV MAE | MAE | RMSE | R2 | MAPE_% |
|---|---|---|---|---|---|---|
| Market only | LinearRegression | 1,009,929 | 956,822 | 3,324,576 | 0.806 | 13.345 |
| Market only | RandomForest | 811,721 | 844,018 | 3,394,713 | 0.798 | 11.782 |
| Market only | GradientBoosting | 892,537 | 893,385 | 3,363,843 | 0.802 | 11.956 |
| Market only | XGBoost | 879,440 | 855,701 | 3,322,309 | 0.807 | 11.791 |
| Market + attributes | LinearRegression | 1,010,565 | 958,173 | 3,325,320 | 0.806 | 13.353 |
| Market + attributes | RandomForest | 807,669 | 839,668 | 3,387,705 | 0.799 | 11.734 |
| Market + attributes | GradientBoosting | 898,604 | 900,337 | 3,352,194 | 0.803 | 11.987 |
| Market + attributes | XGBoost | 885,105 | 879,702 | 3,354,193 | 0.803 | 11.880 |

## Best model per feature set (chosen by cross-validated MAE)

- Market only: **RandomForest**, test MAE LKR 844,018, R2 0.798, MAPE 11.8%
- Market + attributes: **RandomForest**, test MAE LKR 839,668, R2 0.799, MAPE 11.7%
- MAE change from the attributes: -0.5%

## Attribute premiums (hedonic regression, R2 0.919, 95% CI clustered by seller)

| Attribute | Price difference | 95% CI | Significant | Ads |
|---|---|---|---|---|
| single_owner | -0.3% | -1.5% to +0.8% | no | 1,906 |
| service_records | +0.5% | -0.5% to +1.5% | no | 1,289 |
| new_tyres | -0.0% | -1.4% to +1.3% | no | 1,230 |
| new_battery | +0.3% | -1.9% to +2.5% | no | 578 |
| accident_free | +0.7% | -2.7% to +4.1% | no | 537 |
| original_paint | +0.5% | -2.1% to +3.1% | no | 334 |
| needs_repair | -1.4% | -4.3% to +1.7% | no | 631 |

Claims made by sellers in the ad text; associations in asking prices, not guaranteed effects.

## Error for the AutoSense target models

| Model | Test ads | MAE | MAPE_% |
|---|---|---|---|
| Axio | 241 | 425,060 | 5.827 |
| Premio | 156 | 1,666,650 | 13.220 |
| Allion | 144 | 469,356 | 6.406 |
| Vitz | 288 | 338,758 | 6.033 |
| Corolla | 297 | 457,428 | 20.004 |
| Yaris | 31 | 533,027 | 8.726 |
