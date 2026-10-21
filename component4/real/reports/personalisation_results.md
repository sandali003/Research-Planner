# Personalised value-uplift vs generic advice (Component 4 evaluation)

300 real Sri Lankan Toyota ads (Axio, Premio, Allion, Vitz, Corolla, Yaris), each with the defects of a real UK MOT Toyota of the same age; 53% have at least one defect and are scored. 6 owner situations each. Plans use typical costs and the model's estimates; outcomes use a random actual cost (min-max quote) and an uncertain value effect (x U(0.6, 1.2), percentile error N(0, 0.05)).

## All situations

|  | Mean net gain LKR | Mean value gain LKR | Mean cost LKR | Owner loses money % | Value per LKR spent | Mean repairs |
|---|---|---|---|---|---|---|
| Do nothing | 0.00 | 0.00 | 0.00 | 0.00 | nan | 0.00 |
| Generic: schedule | 328,913 | 412,920 | 84,007 | 25.58 | 4.92 | 1.14 |
| Generic: worst first | 348,091 | 433,894 | 85,804 | 20.55 | 5.06 | 1.13 |
| Personalised | 360,793 | 433,755 | 72,962 | 1.47 | 5.94 | 0.90 |

## Mean net gain (LKR) by owner situation

|  | Do nothing | Generic: schedule | Generic: worst first | Personalised |
|---|---|---|---|---|
| budget 40,000 · private · 7 day(s) | 0.00 | 161,132 | 164,100 | 178,205 |
| budget 100,000 · private · 7 day(s) | 0.00 | 404,570 | 469,829 | 485,304 |
| budget 250,000 · private · 7 day(s) | 0.00 | 661,717 | 668,006 | 672,560 |
| budget 100,000 · dealer · 7 day(s) | 0.00 | 162,354 | 192,446 | 207,921 |
| budget 250,000 · dealer · 7 day(s) | 0.00 | 266,270 | 269,609 | 275,276 |
| budget 100,000 · private · 1 day(s) | 0.00 | 317,436 | 324,552 | 345,491 |

## Personalised minus the better generic plan (paired, per car and situation)

Mean +12,478 LKR (bootstrap 95% CI +10,550 to +14,326); personalised is better in 20%, equal in 80%, worse in 0% (worse only where actual costs or effects differ from the estimates).

## Is the plan personalised?

Different plans for the same car across the 6 owner situations: mean 1.9; 78% of cars get more than one plan.

Repair costs are placeholder estimates; the value effect comes from US auction data (model 2) applied to Sri Lankan market values (model 1).
