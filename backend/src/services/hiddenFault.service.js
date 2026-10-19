import { query } from '../config/db.js';
import { env } from '../config/env.js';
import { HttpError } from '../utils/httpError.js';
import { latestSession } from './assessment.service.js';
import { buildFaultFeatures, missingFaultInputs } from './faultPreprocessing.service.js';
import { predictHiddenFaults } from './mlClient.service.js';

const MAX_WINDOW_ROWS = 2000;

async function assessAndSave(vehicleId, sessionId, source, features) {
  const started = Date.now();
  const result = await predictHiddenFaults(features);
  const latencyMs = Date.now() - started;

  const { rows } = await query(
    `INSERT INTO fault_assessments
       (vehicle_id, session_id, source, status, primary_fault, severity, features, result, latency_ms)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
     RETURNING id, created_at`,
    [vehicleId, sessionId, source, result.status, result.primary_fault, result.overall_severity,
      features, result, latencyMs],
  );

  return { id: rows[0].id, created_at: rows[0].created_at, source, latency_ms: latencyMs, features, ...result };
}

/** Hidden fault check on the latest IoT + OBD-II readings of the vehicle. */
export async function runFaultCheck(vehicle, windowSeconds) {
  const sessionId = await latestSession(vehicle.id);
  if (!sessionId) throw new HttpError(409, 'No collection session for this vehicle');

  const [sensor, obd] = await Promise.all([
    query(
      `SELECT accel_x, accel_y, accel_z, temp_c, voltage_v FROM sensor_readings
       WHERE session_id = $1 AND ts >= now() - make_interval(secs => $2)
       ORDER BY ts DESC LIMIT ${MAX_WINDOW_ROWS}`,
      [sessionId, windowSeconds],
    ),
    query(
      `SELECT rpm, engine_load, coolant_temp, dtc_codes FROM obd_readings
       WHERE session_id = $1 AND ts >= now() - make_interval(secs => $2)
       ORDER BY ts DESC LIMIT ${MAX_WINDOW_ROWS}`,
      [sessionId, windowSeconds],
    ),
  ]);

  const features = buildFaultFeatures(sensor.rows, obd.rows, env.ACCEL_LSB_PER_G, vehicle.model);
  const missing = missingFaultInputs(features);
  if (Object.keys(missing).length) {
    throw new HttpError(422, 'Not enough recent sensor data for a hidden fault check', { missing, windowSeconds });
  }

  return assessAndSave(vehicle.id, sessionId, 'iot', features);
}

/** Hidden fault check on readings typed in by the user (no device needed). */
export function runManualFaultCheck(vehicle, inputs) {
  return assessAndSave(vehicle.id, null, 'manual', { ...inputs, vehicle_model: vehicle.model });
}

export async function listFaultChecks(vehicleId) {
  const { rows } = await query(
    `SELECT id, source, status, primary_fault, severity, latency_ms, created_at
     FROM fault_assessments WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 50`,
    [vehicleId],
  );
  return rows;
}

export async function getFaultCheck(vehicleId, checkId) {
  const { rows } = await query(
    checkId == null
      ? 'SELECT * FROM fault_assessments WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 1'
      : 'SELECT * FROM fault_assessments WHERE vehicle_id = $1 AND id = $2',
    checkId == null ? [vehicleId] : [vehicleId, checkId],
  );
  return rows[0] ?? null;
}
