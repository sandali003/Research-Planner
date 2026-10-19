# AutoSense backend (Node/Express)

Express API: auth, vehicles, ESP32 ingestion, sessions, assessments. Scoring is delegated to the
Python service in `../ml-service` (wraps `ai-vehicle-health-assessment/health_assessment.py`).

## Run
```
createdb autosense_db                        # PostgreSQL
cp .env.example .env                         # set DATABASE_URL, JWT_SECRET
npm install && npm run migrate && npm run dev

# ML service (repo root, with the Python deps from ai-vehicle-health-assessment/requirements.txt + fastapi uvicorn)
uvicorn server:app --app-dir ml-service --port 8001

# Hidden fault service (Component 2)
cd vehical-hidden-fault-and-mitigation
.venv\Scripts\activate                        # pip install -r requirements.txt
uvicorn api:app --port 8002

# Component 3 deterioration service (from Component3-Deterioration, see its README)
.venv\Scripts\python -m uvicorn app:app --port 8003
```

## Hidden fault prediction & mitigation (Component 2)
- `POST /api/v1/vehicles/:id/hidden-faults` `{"window_seconds":60}` -> check on the latest IoT + OBD-II readings
- `POST /api/v1/vehicles/:id/hidden-faults/manual` `{"engine_rpm":..,"battery_voltage_v":..,"vibration_x_g":..}` -> check on typed-in readings
- `GET /api/v1/vehicles/:id/hidden-faults` (history), `/latest`, `/:checkId`; `GET /health/hidden-fault`

Each result has the predicted faults, confidence, severity and a mitigation plan (immediate actions + longevity tips),
stored in `fault_assessments`.

## Flow
1. `POST /api/v1/auth/register` -> token
2. `POST /api/v1/vehicles` -> vehicle; `POST /api/v1/vehicles/:id/devices` -> **device api_key (shown once)**
3. ESP32 sends header `x-device-key` to
   - `POST /api/v1/readings` `{"readings":[{"accel_x":..,"accel_y":..,"accel_z":..,"temperature_c":..,"pin_voltage_v":..}]}`
   - `POST /api/v1/readings/obd` `{"readings":[{"rpm":..,"engine_load":..,"dtc_codes":["P0300"]}]}`
4. `POST /api/v1/vehicles/:id/assessments` `{"window_seconds":10}` -> score, condition, SHAP factors, explanation
5. `GET /api/v1/vehicles/:id/health-summary` -> contract for Components 2-4
6. Component 3: `POST /api/v1/vehicles/:id/deterioration`
   `{"odometer_km":120000,"component":"Brakes","component_state":"Poor"}` -> expected vs observed
   condition, deviation, status; saved in `deterioration_assessments`. `vehicle_model` / `age_years`
   default to the vehicle's model / year. History: `GET /api/v1/vehicles/:id/deterioration`

Other: `POST /api/v1/sessions` (+ `/:id/stop`, `GET /:id`), `GET /api/v1/assessments/:id`, `GET /health`, `/health/db`, `/health/ml`, `/health/deterioration`.

## Notes
- Raw MPU6050 counts are converted to vibration RMS/peak in g (`ACCEL_LSB_PER_G`); gravity is removed per window.
- ESP32 pin voltage is multiplied by `VOLTAGE_DIVIDER_RATIO` to get battery voltage - set it to your divider.
- Tests: `npm test`.
