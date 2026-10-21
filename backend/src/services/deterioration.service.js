import { pool, query } from '../config/db.js';
import { HttpError } from '../utils/httpError.js';
import { assessDeterioration, deteriorationHealth } from './mlClient.service.js';

const OBD_WINDOW_MINUTES = 30;
const MIN_OBD_ROWS = 3;

/** Vehicle age in years; mid-year manufacture date, same as the training data. */
export function vehicleAge(year, now = new Date()) {
  const built = new Date(Date.UTC(year, 6, 1));
  return Math.max(0, (now - built) / (365.25 * 24 * 3600 * 1000));
}

/** Mean of each OBD field over rows that have it; null unless all three fields have enough rows. */
export function averageObd(rows) {
  const mean = (key) => {
    const vals = rows.map((r) => r[key]).filter((v) => v !== null && v !== undefined && Number.isFinite(Number(v)));
    return vals.length >= MIN_OBD_ROWS ? vals.reduce((a, b) => a + Number(b), 0) / vals.length : null;
  };
  const reading = { engine_rpm: mean('rpm'), engine_load: mean('engine_load'), coolant_temp: mean('coolant_temp') };
  return Object.values(reading).every((v) => v !== null) ? reading : null;
}

/** Recent OBD-II readings from the vehicle's newest session (sent by the IoT device). */
async function sessionObd(vehicleId) {
  const { rows } = await query(
    `SELECT o.rpm, o.engine_load, o.coolant_temp FROM obd_readings o
     JOIN sessions s ON s.id = o.session_id
     WHERE s.vehicle_id = $1 AND o.ts >= now() - make_interval(mins => $2)
     ORDER BY o.ts DESC LIMIT 500`,
    [vehicleId, OBD_WINDOW_MINUTES],
  );
  return averageObd(rows);
}

/**
 * Calls Component 3 for every inspected component and stores the run.
 * Model and age default to the vehicle record; OBD-II defaults to the vehicle's recent IoT readings.
 */
export async function runDeterioration(vehicle, input) {
  const vehicleModel = input.vehicle_model ?? vehicle.model;
  if (!vehicleModel) throw new HttpError(422, 'vehicle_model is required (vehicle has no model set)');

  const ageYears = input.age_years ?? (vehicle.year ? vehicleAge(vehicle.year) : null);
  if (ageYears == null) throw new HttpError(422, 'age_years is required (vehicle has no year set)');

  let obd = input.obd ?? null;
  let obdSource = obd ? 'request' : null;
  if (!obd) {
    obd = await sessionObd(vehicle.id);
    obdSource = obd ? 'session' : null;
  }

  const request = {
    vehicle_model: vehicleModel,
    age_years: Math.round(ageYears * 100) / 100,
    odometer_km: input.odometer_km,
    components: input.components,
    ...(obd && { obd }),
    ...(input.fuel_type && { fuel_type: input.fuel_type }),
    ...(input.engine_cc && { engine_cc: input.engine_cc }),
  };

  const started = Date.now();
  const [result, health] = await Promise.all([
    assessDeterioration(request),
    deteriorationHealth().catch(() => null),
  ]);
  const latencyMs = Date.now() - started;

  const worst = result.components.find((c) => c.component === result.worst_component);
  const advice = Object.fromEntries(result.recommendations.map((r) => [r.component, r.advice]));

  // pg sends JS arrays as Postgres arrays, so JSON columns get JSON.stringify
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const { rows } = await client.query(
      `INSERT INTO deterioration_assessments
         (vehicle_id, vehicle_model, age_years, odometer_km, component, component_state,
          expected_score, observed_score, deviation, status, reasons, model_version, latency_ms,
          km_per_year, warnings, obd, obd_source, contextual, legacy_status, fuel_type, engine_cc)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
       RETURNING *`,
      [
        vehicle.id, result.vehicle_model_used, request.age_years, request.odometer_km,
        worst.component, worst.component_state,
        result.expected_condition, result.observed_condition, result.worst_deviation, result.status,
        JSON.stringify(worst.reasons ?? []), health?.model_version ?? null, latencyMs,
        result.km_per_year, JSON.stringify(result.warnings ?? []),
        obd ? JSON.stringify({ reading: obd, ...result.obd }) : null, obdSource,
        result.contextual ? JSON.stringify(result.contextual) : null, result.legacy_status ?? null,
        request.fuel_type ?? null, request.engine_cc ?? null,
      ],
    );
    const assessment = rows[0];

    const components = [];
    for (const c of result.components) {
      const inserted = await client.query(
        `INSERT INTO deterioration_components
           (assessment_id, component, component_state, expected_score, observed_score, deviation, status, reasons, advice)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
         RETURNING component, component_state, expected_score, observed_score, deviation, status, reasons, advice`,
        [
          assessment.id, c.component, c.component_state, c.expected_condition, c.observed_condition,
          c.deterioration_deviation, c.deterioration_status, JSON.stringify(c.reasons ?? []), advice[c.component] ?? null,
        ],
      );
      components.push(inserted.rows[0]);
    }
    await client.query('COMMIT');

    return { ...assessment, components: sortWorstFirst(components) };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

const sortWorstFirst = (components) => [...components].sort((a, b) => a.deviation - b.deviation);

/** One stored assessment with its components, or null. */
export async function getDeterioration(where, params) {
  const { rows } = await query(`SELECT * FROM deterioration_assessments WHERE ${where} ORDER BY created_at DESC LIMIT 1`, params);
  if (!rows[0]) return null;
  const comps = await query(
    `SELECT component, component_state, expected_score, observed_score, deviation, status, reasons, advice
     FROM deterioration_components WHERE assessment_id = $1`,
    [rows[0].id],
  );
  return { ...rows[0], components: sortWorstFirst(comps.rows) };
}

/** Compact result for other components (e.g. Component 2 uses high-deterioration components as input). */
export function deteriorationSummary(a) {
  if (!a) return null;
  const ctx = a.contextual?.available ? a.contextual : null;
  // Real-data statuses where the contextual assessment covers a component, the
  // inspection-data model's status for the others
  const contextualStatus = Object.fromEntries((ctx?.components ?? []).map((c) => [c.component, c.status]));
  return {
    assessed_at: a.created_at,
    status: a.status,
    expected_score: a.expected_score,
    observed_score: a.observed_score,
    worst_component: ctx?.worst_component ?? a.component,
    worst_deviation: a.deviation,
    effective_age: ctx?.overall.effective_age ?? null,
    age_gap: ctx?.overall.age_gap ?? null,
    worse_than_pct: ctx?.overall.worse_than_pct ?? null,
    // Second output: risk of a major defect at the next inspection, and the combined decision
    next_test_risk: ctx?.overall.next_test_risk ?? null,
    decision: ctx?.decision?.key ?? null,
    at_risk_components: ctx?.decision?.risk_components ?? [],
    high_deterioration_components: a.components
      .filter((c) => (contextualStatus[c.component] ?? c.status) !== 'Normal')
      .map((c) => c.component),
  };
}
