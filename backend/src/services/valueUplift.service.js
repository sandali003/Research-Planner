import { query } from '../config/db.js';
import { HttpError } from '../utils/httpError.js';
import { getDeterioration } from './deterioration.service.js';
import { valueUplift } from './mlClient.service.js';

/**
 * Component 4: personalised value-uplift plan for a vehicle.
 * Uses the vehicle's latest Component 3 assessment (real-data contextual result: age, mileage,
 * condition among comparable cars) and latest Component 2 hidden fault check (faults + severity),
 * plus the owner's budget, days until the sale and buyer type.
 */
export async function runValueUplift(vehicle, input) {
  const deterioration = await getDeterioration('vehicle_id = $1', [vehicle.id]);
  const ctx = deterioration?.contextual;
  if (!ctx?.available) {
    throw new HttpError(422, 'Run a deterioration assessment (Component 3) for this vehicle first, with at least '
      + 'one of brakes, suspension, steering, tyres or exhaust inspected.', { needs: 'deterioration' });
  }

  const { rows } = await query(
    'SELECT result, created_at FROM fault_assessments WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 1',
    [vehicle.id],
  );
  const faultCheck = rows[0] ?? null;
  const faults = (faultCheck?.result?.issues ?? []).map((i) => ({ fault: i.fault, severity: i.severity }));

  const body = {
    vehicle: {
      model: deterioration.vehicle_model,
      age_years: deterioration.age_years,
      mileage_km: input.mileage_km ?? deterioration.odometer_km,
      engine_cc: input.engine_cc ?? deterioration.engine_cc ?? null,
      fuel_type: input.fuel_type ?? deterioration.fuel_type ?? null,
    },
    contextual: {
      overall: { grade_distribution: ctx.overall.grade_distribution },
      components: ctx.components.map((c) => ({
        component: c.component, mot_group: c.mot_group, observed_grade: c.observed_grade,
      })),
    },
    faults,
    budget_lkr: input.budget_lkr ?? null,
    sell_within_days: input.sell_within_days ?? null,
    buyer: input.buyer ?? 'private',
  };

  const started = Date.now();
  const result = await valueUplift(body);
  return {
    ...result,
    vehicle: body.vehicle,
    latency_ms: Date.now() - started,
    sources: {
      deterioration_id: deterioration.id,
      deterioration_at: deterioration.created_at,
      fault_check_at: faultCheck?.created_at ?? null,
      fault_count: faults.length,
    },
  };
}
