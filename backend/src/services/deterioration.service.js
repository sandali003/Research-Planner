import { query } from '../config/db.js';
import { HttpError } from '../utils/httpError.js';
import { assessDeterioration, deteriorationHealth } from './mlClient.service.js';

/** Vehicle age in years; mid-year manufacture date, same as the training data. */
export function vehicleAge(year, now = new Date()) {
  const built = new Date(Date.UTC(year, 6, 1));
  return Math.max(0, (now - built) / (365.25 * 24 * 3600 * 1000));
}

/** Calls Component 3 and stores the result. Model and age default to the vehicle record. */
export async function runDeterioration(vehicle, input) {
  const vehicleModel = input.vehicle_model ?? vehicle.model;
  if (!vehicleModel) throw new HttpError(422, 'vehicle_model is required (vehicle has no model set)');

  const ageYears = input.age_years ?? (vehicle.year ? vehicleAge(vehicle.year) : null);
  if (ageYears == null) throw new HttpError(422, 'age_years is required (vehicle has no year set)');

  const request = {
    vehicle_model: vehicleModel,
    age_years: Math.round(ageYears * 100) / 100,
    odometer_km: input.odometer_km,
    component: input.component,
    component_state: input.component_state,
  };

  const started = Date.now();
  const [result, health] = await Promise.all([
    assessDeterioration(request),
    deteriorationHealth().catch(() => null),
  ]);
  const latencyMs = Date.now() - started;

  const { rows } = await query(
    `INSERT INTO deterioration_assessments
       (vehicle_id, vehicle_model, age_years, odometer_km, component, component_state,
        expected_score, observed_score, deviation, status, reasons, model_version, latency_ms)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
     RETURNING *`,
    [
      vehicle.id, request.vehicle_model, request.age_years, request.odometer_km,
      request.component, request.component_state,
      result.expected_condition, result.observed_condition, result.deterioration_deviation,
      result.deterioration_status,
      JSON.stringify(result.reasons ?? []), // pg sends JS arrays as Postgres arrays, not JSON
      health?.model_version ?? null, latencyMs,
    ],
  );
  return rows[0];
}
