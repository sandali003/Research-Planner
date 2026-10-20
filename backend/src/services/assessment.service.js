import { query } from '../config/db.js';
import { env } from '../config/env.js';
import { HttpError } from '../utils/httpError.js';
import { buildFeatures, missingInputs } from './preprocessing.service.js';
import { predict } from './mlClient.service.js';

const MAX_WINDOW_ROWS = 2000;

/** Newest session for the vehicle (open session preferred). */
export async function latestSession(vehicleId) {
  const { rows } = await query(
    `SELECT id FROM sessions WHERE vehicle_id = $1
     ORDER BY (ended_at IS NULL) DESC, started_at DESC LIMIT 1`,
    [vehicleId],
  );
  return rows[0]?.id ?? null;
}

export async function runAssessment(vehicleId, windowSeconds) {
  const sessionId = await latestSession(vehicleId);
  if (!sessionId) throw new HttpError(409, 'No collection session for this vehicle');

  const [sensor, obd] = await Promise.all([
    query(
      `SELECT accel_x, accel_y, accel_z, temp_c, voltage_v FROM sensor_readings
       WHERE session_id = $1 AND ts >= now() - make_interval(secs => $2)
       ORDER BY ts DESC LIMIT ${MAX_WINDOW_ROWS}`,
      [sessionId, windowSeconds],
    ),
    query(
      `SELECT rpm, engine_load, dtc_codes FROM obd_readings
       WHERE session_id = $1 AND ts >= now() - make_interval(secs => $2)
       ORDER BY ts DESC LIMIT ${MAX_WINDOW_ROWS}`,
      [sessionId, windowSeconds],
    ),
  ]);

  const features = buildFeatures(sensor.rows, obd.rows, env.ACCEL_LSB_PER_G);
  const missing = missingInputs(features);
  if (missing.length) {
    throw new HttpError(422, 'Not enough recent sensor data for an assessment', { missing, windowSeconds });
  }

  return scoreAndSave(vehicleId, sessionId, features);
}

/** Assessment on readings typed in by the user (no session). */
export async function runManualAssessment(vehicleId, inputs) {
  const features = {
    ds18b20_temp_c: inputs.ds18b20_temp_c,
    battery_voltage_v: inputs.battery_voltage_v,
    vibration_rms_g: inputs.vibration_rms_g,
    vibration_peak_g: inputs.vibration_peak_g,
    dtc_codes: [...new Set((inputs.dtc_codes ?? []).map((c) => c.toUpperCase()))].join(';'),
    engine_rpm: inputs.engine_rpm ?? null,
    engine_load_pct: inputs.engine_load_pct ?? null,
  };
  return scoreAndSave(vehicleId, null, features);
}

async function scoreAndSave(vehicleId, sessionId, features) {
  const started = Date.now();
  const result = await predict(features);
  const latencyMs = Date.now() - started;

  const { rows } = await query(
    `INSERT INTO assessments
       (vehicle_id, session_id, overall_score, condition, features, result, model_version, latency_ms)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
     RETURNING id, created_at`,
    [vehicleId, sessionId, result.overall, result.condition, features, result, result.model_version ?? null, latencyMs],
  );

  return { id: rows[0].id, created_at: rows[0].created_at, latency_ms: latencyMs, features, ...result };
}
