import { describe, expect, it } from 'vitest';
import { averageObd, deteriorationSummary, vehicleAge } from '../src/services/deterioration.service.js';
import { deteriorationBody } from '../src/routes/vehicles.routes.js';

describe('vehicleAge', () => {
  it('counts from mid-year of manufacture', () => {
    expect(vehicleAge(2016, new Date(Date.UTC(2024, 0, 1)))).toBeCloseTo(7.5, 1);
  });

  it('is never negative', () => {
    expect(vehicleAge(2030, new Date(Date.UTC(2024, 0, 1)))).toBe(0);
  });
});

describe('averageObd', () => {
  const row = (rpm, engine_load, coolant_temp) => ({ rpm, engine_load, coolant_temp });

  it('averages each field over the rows that have it', () => {
    const r = averageObd([row(800, 20, 88), row(900, null, 90), row(1000, 30, 92), row(null, 40, 90)]);
    expect(r).toEqual({ engine_rpm: 900, engine_load: 30, coolant_temp: 90 });
  });

  it('returns null when a field has too few readings', () => {
    expect(averageObd([row(800, 20, 88), row(900, 25, null), row(1000, 30, null)])).toBeNull();
    expect(averageObd([])).toBeNull();
  });
});

describe('deteriorationBody', () => {
  it('accepts a component list', () => {
    const r = deteriorationBody.parse({
      odometer_km: 120000,
      components: [{ component: 'Brakes', component_state: 'Poor' }, { component: 'Engine', component_state: 'Good' }],
    });
    expect(r.components).toHaveLength(2);
  });

  it('turns the single-component form into a list', () => {
    const r = deteriorationBody.parse({ odometer_km: 1, component: 'Brakes', component_state: 'Fair' });
    expect(r.components).toEqual([{ component: 'Brakes', component_state: 'Fair' }]);
    expect(r).not.toHaveProperty('component');
  });

  it('rejects no components, duplicates and unknown states', () => {
    expect(deteriorationBody.safeParse({ odometer_km: 1 }).success).toBe(false);
    expect(deteriorationBody.safeParse({
      odometer_km: 1,
      components: [{ component: 'Brakes', component_state: 'Poor' }, { component: 'Brakes', component_state: 'Good' }],
    }).success).toBe(false);
    expect(deteriorationBody.safeParse({ odometer_km: 1, component: 'Brakes', component_state: 'Bad' }).success).toBe(false);
  });
});

describe('deteriorationSummary', () => {
  const base = {
    created_at: '2026-10-21', status: 'High', expected_score: 70, observed_score: 50, component: 'Brakes', deviation: -20,
    components: [{ component: 'Brakes', status: 'High' }, { component: 'Battery', status: 'Normal' }],
  };

  it('reports both outputs and the decision from the real-data assessment', () => {
    const risk = { probability: 0.42, level: 'High', comparable_defect_rate: 0.1, base_rate: 0.3 };
    const s = deteriorationSummary({
      ...base,
      contextual: {
        available: true, worst_component: 'Brakes',
        overall: { effective_age: 14, age_gap: 5, worse_than_pct: 92, next_test_risk: risk },
        components: [{ component: 'Brakes', status: 'High' }],
        decision: { key: 'repair_now', risk_components: ['Brakes'] },
      },
    });
    expect(s).toMatchObject({ worse_than_pct: 92, next_test_risk: risk, decision: 'repair_now', at_risk_components: ['Brakes'] });
  });

  it('leaves the risk empty without a real-data assessment', () => {
    const s = deteriorationSummary({ ...base, contextual: null });
    expect(s).toMatchObject({ next_test_risk: null, decision: null, at_risk_components: [], high_deterioration_components: ['Brakes'] });
  });
});
