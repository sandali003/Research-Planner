import { pool, query } from '../config/db.js';
import { env } from '../config/env.js';

/** The vehicle's open session, or a new one if none is open (device can stream without manual start). */
async function openSessionId(vehicleId) {
  const { rows } = await query(
    'SELECT id FROM sessions WHERE vehicle_id = $1 AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1',
    [vehicleId],
  );
  if (rows[0]) return rows[0].id;
  const created = await query('INSERT INTO sessions (vehicle_id) VALUES ($1) RETURNING id', [vehicleId]);
  return created.rows[0].id;
}

// Multi-row insert with parameter placeholders; columns are fixed in code, never from user input.
async function bulkInsert(table, columns, rows) {
  if (!rows.length) return 0;
  const values = [];
  const placeholders = rows.map((row, i) => {
    values.push(...row);
    return `(${row.map((_, j) => `$${i * columns.length + j + 1}`).join(',')})`;
  });
  const client = await pool.connect();
  try {
    await client.query(`INSERT INTO ${table} (${columns.join(',')}) VALUES ${placeholders.join(',')}`, values);
  } finally {
    client.release();
  }
  return rows.length;
}

export async function ingestSensorReadings(vehicleId, readings) {
  const sessionId = await openSessionId(vehicleId);
  const rows = readings.map((r) => [
    sessionId,
    r.ts ?? new Date(),
    r.accel_x ?? null,
    r.accel_y ?? null,
    r.accel_z ?? null,
    r.temperature_c ?? null,
    // ESP32 sends the ADC pin voltage; convert to battery voltage via the divider ratio.
    r.pin_voltage_v != null ? r.pin_voltage_v * env.VOLTAGE_DIVIDER_RATIO : null,
  ]);
  const saved = await bulkInsert('sensor_readings', ['session_id', 'ts', 'accel_x', 'accel_y', 'accel_z', 'temp_c', 'voltage_v'], rows);
  return { sessionId, saved };
}

export async function ingestObdReadings(vehicleId, readings) {
  const sessionId = await openSessionId(vehicleId);
  const rows = readings.map((r) => [
    sessionId,
    r.ts ?? new Date(),
    r.rpm ?? null,
    r.engine_load ?? null,
    r.coolant_temp ?? null,
    r.intake_temp ?? null,
    r.speed ?? null,
    r.dtc_codes ?? [],
  ]);
  const saved = await bulkInsert('obd_readings', ['session_id', 'ts', 'rpm', 'engine_load', 'coolant_temp', 'intake_temp', 'speed', 'dtc_codes'], rows);
  return { sessionId, saved };
}
