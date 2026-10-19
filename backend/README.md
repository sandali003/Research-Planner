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
```

## Flow
1. `POST /api/v1/auth/register` -> token
2. `POST /api/v1/vehicles` -> vehicle; `POST /api/v1/vehicles/:id/devices` -> **device api_key (shown once)**
3. ESP32 sends header `x-device-key` to
   - `POST /api/v1/readings` `{"readings":[{"accel_x":..,"accel_y":..,"accel_z":..,"temperature_c":..,"pin_voltage_v":..}]}`
   - `POST /api/v1/readings/obd` `{"readings":[{"rpm":..,"engine_load":..,"dtc_codes":["P0300"]}]}`
4. `POST /api/v1/vehicles/:id/assessments` `{"window_seconds":10}` -> score, condition, SHAP factors, explanation
5. `GET /api/v1/vehicles/:id/health-summary` -> contract for Components 2-4

Other: `POST /api/v1/sessions` (+ `/:id/stop`, `GET /:id`), `GET /api/v1/assessments/:id`, `GET /health`, `/health/db`, `/health/ml`.

## Notes
- Raw MPU6050 counts are converted to vibration RMS/peak in g (`ACCEL_LSB_PER_G`); gravity is removed per window.
- ESP32 pin voltage is multiplied by `VOLTAGE_DIVIDER_RATIO` to get battery voltage - set it to your divider.
- Tests: `npm test`.
