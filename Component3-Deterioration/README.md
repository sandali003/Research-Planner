# Component 3 – Age- and Mileage-Adjusted Vehicle Deterioration Assessment

Part of the AutoSense platform (J26-IT-386). Learns the condition expected for a
vehicle's age and mileage, estimates its observed condition from inspection
evidence, and flags accelerated deterioration when observed falls below expected.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Web app

```
.venv\Scripts\python -m uvicorn app:app --port 8003
```

Open http://127.0.0.1:8003 in a browser. API docs: http://127.0.0.1:8003/docs

The Node backend (`../backend`) calls this service on port 8003 and stores each
deterioration assessment in PostgreSQL (`deterioration_assessments` table).

## Scripts

| Script | What it does | Output |
|---|---|---|
| `data_prep.py` | Shared cleaning: removes duplicate rows, normalises labels, parses numbers, joins inspections with odometer readings | – |
| `train_deterioration_model.py` | Component 3 core: expected model (age, km, model) + observed model (inspection evidence) → deviation → status. Compared with age/mileage-only and current-condition-only baselines using vehicle-level 5-fold CV | `models/deterioration_model.joblib`, `reports/deterioration_results.csv` |
| `predict_deterioration.py` | Assess one vehicle | – |
| `train_condition_model.py` | Overall condition (Good/Fair/Poor/Critical) from component condition | `models/vehicle_condition_model.joblib` |
| `train_model.py` / `predict.py` | Recommended solution from service history + problem | `models/solution_prediction_model.joblib` |
| `train_obd_anomaly_model.py` | Unsupervised OBD-II anomaly detection (no labels available) | `models/obd_anomaly_model.joblib`, `reports/obd_vehicle_anomaly.csv` |
| `external_data/build_mot_toyota.py` | Toyota Yaris / Vitz / Corolla tests from the UK MOT anonymised data (DVSA), with failure / minor / advisory counts per component | `external_data/mot_toyota_<year>.csv` / `.xlsx` (not in git) |
| `mot_condition.py` + `train_expected_condition.py` | Condition grades from the official DVSA defect categories; probabilistic, monotonic expected-condition baseline (age, km, platform, fuel, engine) for the overall vehicle and per component, compared with marginal / platform-only / age-only baselines | `models/expected_condition_model.joblib`, `reports/expected_condition_results.md` |

All trained models are in `models/`.

## Current results (unseen vehicles)

| Poor-condition detection | F1 | ROC-AUC |
|---|---|---|
| A. Age + mileage only | 0.21 | 0.505 |
| B. Current condition only | 0.589 | 0.832 |
| C. Proposed deviation method | 0.592 | 0.846 |

The expected-condition model has R² ≈ −0.03: in the current synthetic data,
age and mileage have no relationship with inspection score, so the age/mileage
adjustment adds almost nothing yet. Retrain with real service-centre data.

## Data notes

- All datasets except the 24000-record OBD log are synthetic.
- `inspection_score` is not used as a model input: `overall_condition` is the score cut into ranges, so it would leak the answer.
- The 4000-record inspection file has no relationship between component and overall condition and is not used for the final condition model.
- The 24000-record OBD file is a single car (2009, recorded 2017); its Toyota model column is not meaningful.
- OBD vehicle IDs do not match inspection vehicle IDs, so OBD data cannot yet be joined into Component 3.
