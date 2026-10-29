# AutoSense: Explainable Vehicle Health, Fault, Deterioration and Value Assessment

Research project **J26-IT-386**. AutoSense combines OBD-II diagnostics with low-cost external IoT
sensors (temperature, battery voltage, vibration) to tell a vehicle owner or used-car buyer how healthy
a car is, what hidden faults it may have, how it compares with similar cars of the same age and mileage,
and which repairs are worth doing before selling. The focus is Toyota models common in Sri Lanka
(Axio, Allion, Premio, Corolla, Vitz, Yaris).

Every component explains its output (SHAP, rule-based reasons, counterfactual "what-if" advice) instead
of returning a bare label.

## Research problem

- OBD-II scanners show fault codes that most owners cannot interpret, and only after a fault threshold is crossed.
- OBD-II cannot see vibration or gradual battery and thermal decline.
- A mechanic inspection is costly and varies from mechanic to mechanic.
- AI-based tools give a label ("Poor") without saying why or what to fix first.
- Used-car prices in Sri Lanka are high, but buyers and sellers have no objective way to link condition to value.

## System overview

```
 ESP32 + sensors ─┐                                   ┌─ C1 Health assessment     :8001
 (DS18B20, MPU6050,│   x-device-key    ┌──────────┐    ├─ C2 Hidden fault + mitigation :8002
  voltage divider, ├──────────────────>│ Node API │───>├─ C3 Deterioration         :8003
  ELM327 OBD-II)  ─┘                   │  :3000   │    └─ C4 Value uplift          :8004
                                       └────┬─────┘
 Next.js frontend :3001 <───── JWT ─────────┤
                                            └── PostgreSQL / Supabase
```

## Components

| # | Component | Folder | Question it answers |
|---|---|---|---|
| C1 | AI Vehicle Health Assessment | [ai-vehicle-health-assessment/](ai-vehicle-health-assessment/) | How healthy is the car right now, and why? |
| C2 | Hidden Fault Prediction & Mitigation | [vehical-hidden-fault-and-mitigation/](vehical-hidden-fault-and-mitigation/) | Which faults are developing, how severe, and what should be done? |
| C3 | Age- and Mileage-Adjusted Deterioration | [Component3-Deterioration/](Component3-Deterioration/) | Is the car worse than comparable cars, and how likely is it to fail its next inspection? |
| C4 | Maintenance Valuation / Value Uplift | [component4/](component4/) | Which repairs are worth doing before selling, and how much could they add to the price? |

### C1: AI Vehicle Health Assessment

Two-layer hybrid model:

1. **Rules** turn raw readings into four component scores (0-100): engine temperature, battery/electrical,
   vibration, and OBD-II (fault codes × engine operation from RPM and load, including lugging and over-revving).
2. A **monotonic gradient boosting** model (`HistGradientBoostingRegressor`) combines them into an overall
   score; a better component score can never lower the overall score.
3. Condition bands: Good ≥ 80, Fair 60-80, Poor 50-60, Critical < 50.
4. **Explanations** at three levels: SHAP impact per component, plain-language reasons from the raw
   readings and DTC meanings, and a what-if estimate of the score if the worst component were repaired.

Results (simulated labels, 20% hold-out): R² 0.907, MAE 2.6 points, condition accuracy 94.3%
(majority baseline 84.1%). A linear baseline reaches the same R²; the gradient boosting model is used for
its monotonic constraint and SHAP explanations. See [EVALUATION.md](ai-vehicle-health-assessment/EVALUATION.md).

### C2: Hidden Fault Prediction & Mitigation

- **XGBoost** fault classifier (RPM, battery voltage, engine temperature, load).
- **One-Class SVM** anomaly model on OBD-II + vibration.
- **SHAP** explanations for each model and counterfactuals towards healthy readings.
- **Experta expert system** fuses rules and ML outputs, assigns severity and builds a mitigation plan
  (immediate actions + longevity tips).

Fault-injection benchmark (5 seeds × 5-fold GroupKFold by vehicle): full hybrid macro-F1 64.1% vs
rules only 26.6% and XGBoost only 48.2%; OBD-only input 11.9% vs OBD + vibration + voltage 64.1%.
See [benchmark/results/results.md](vehical-hidden-fault-and-mitigation/benchmark/results/results.md).

### C3: Age- and Mileage-Adjusted Deterioration

- Calibrated, monotonic "expected condition" baseline for a car's age, mileage and platform, learned from
  real UK MOT inspections (DVSA anonymised data, Toyota Yaris / Vitz / Corolla).
- Output 1: condition percentile among comparable cars and condition-equivalent age.
- Output 2: probability of a major defect at the next inspection (validated on 2023 → 2024 tests).
- Combined into a decision: repair now / monitor / plan maintenance / routine.

See [Component3-Deterioration/README.md](Component3-Deterioration/README.md) and its `reports/` folder.

### C4: Value Uplift

- Sri Lankan market value model trained on ikman.lk Toyota ads (12,104 ads; Random Forest,
  test MAPE 11.7%, split by seller).
- Condition-to-price effect model from verified-condition auction data.
- Combines C3's condition grade and C2's high-severity faults (always repaired first) with repair costs,
  budget, days until sale and buyer type to recommend the repairs with the highest net gain.

See [component4/real/reports/](component4/real/reports/).

## Platform

| Part | Folder | Stack |
|---|---|---|
| IoT firmware | [research ardunio iot/autosense_obd/](research%20ardunio%20iot/autosense_obd/) | ESP32, DS18B20, MPU6050, voltage divider, ELM327 (Bluetooth) |
| Backend API | [backend/](backend/) | Node.js, Express, PostgreSQL (Supabase-compatible), JWT, device API keys |
| ML service (C1) | [ml-service/](ml-service/) | FastAPI wrapper around `health_assessment.assess()` |
| Frontend | [frontend/](frontend/) | Next.js 14, React 18, TypeScript |

## Running locally

**Prerequisites:** Python 3.11 (C1, C3, C4), Python 3.12+ (C2, for XGBoost 3.4), Node.js, PostgreSQL.

1. **Database and backend** (see [backend/README.md](backend/README.md))
   ```
   cd backend
   cp .env.example .env          # set DATABASE_URL and JWT_SECRET
   npm install
   npm run migrate
   npm run dev                   # http://localhost:3000
   ```

2. **ML services**: create each virtual environment once (commands at the top of
   [start-models.ps1](start-models.ps1)), then start all four:
   ```
   .\start-models.ps1            # ports 8001, 8002, 8003, 8004
   ```

3. **Frontend**
   ```
   cd frontend
   cp .env.example .env.local    # NEXT_PUBLIC_API_URL=http://localhost:3000/api/v1
   npm install
   npm run dev                   # http://localhost:3001
   ```

4. **IoT device** (optional): copy `secrets.example.h` to `secrets.h`, fill in Wi-Fi, backend URL and the
   device key from `POST /api/v1/vehicles/:id/devices`, then flash with board "ESP32 Dev Module" and
   partition scheme "Huge APP". Without hardware, every component accepts manual readings from the frontend.

## Repository layout

```
ai-vehicle-health-assessment/        C1 models, training, evaluation, demo UIs
vehical-hidden-fault-and-mitigation/ C2 models, expert system, benchmark, user study
Component3-Deterioration/            C3 MOT-based deterioration and next-test risk
component4/                          C4 valuation and value-uplift engine
ml-service/                          FastAPI service for C1
backend/                             Express API, migrations, tests
frontend/                            Next.js web app
research ardunio iot/                ESP32 / Arduino sketches
AutoSense/                           early prototype API and dashboard
start-models.ps1                     starts the four Python services
```

## Data and limitations

- C1 and C2 are trained mainly on **synthetic or rule-labelled** datasets; their scores show that the
  models recover the labelling rules, not accuracy on real vehicles.
- C3 uses real UK MOT data; C4 uses real Sri Lankan ads (asking prices, not sale prices) and US auction data.
- Repair costs in C4 are placeholder estimates.
- Validation on real vehicles checked by mechanics is future work.

## Team

Sandali Wellage · Malindu Jayawickrama · Tharuka Umayanga · Savindu Thisanga
