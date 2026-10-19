import { describe, expect, it } from 'vitest';
import { buildFeatures, missingInputs, vibrationFeatures } from '../src/services/preprocessing.service.js';

const G = 16384;

describe('vibrationFeatures', () => {
  it('is ~0 for a vehicle at rest (constant gravity vector)', () => {
    const rest = Array.from({ length: 20 }, () => ({ accel_x: 0, accel_y: 0, accel_z: G }));
    const v = vibrationFeatures(rest, G);
    expect(v.rms).toBeCloseTo(0, 6);
    expect(v.peak).toBeCloseTo(0, 6);
  });

  it('removes gravity and measures the oscillation', () => {
    const shaking = Array.from({ length: 100 }, (_, i) => ({
      accel_x: 0, accel_y: 0, accel_z: G + (i % 2 ? 0.1 : -0.1) * G,
    }));
    const v = vibrationFeatures(shaking, G);
    expect(v.rms).toBeCloseTo(0.1, 2);
    expect(v.peak).toBeCloseTo(0.1, 2);
  });

  it('returns null with too few samples', () => {
    expect(vibrationFeatures([{ accel_x: 1, accel_y: 1, accel_z: 1 }], G)).toEqual({ rms: null, peak: null });
  });
});

describe('buildFeatures', () => {
  const sensors = [
    { accel_x: 0, accel_y: 0, accel_z: G, temp_c: 90, voltage_v: 14.0 },
    { accel_x: 0, accel_y: 0, accel_z: G + 200, temp_c: 92, voltage_v: 14.2 },
    { accel_x: 0, accel_y: 0, accel_z: G, temp_c: -127, voltage_v: 99 }, // glitches are dropped
  ];
  const obd = [{ rpm: 850, engine_load: 20, dtc_codes: ['P0300'] }, { rpm: 870, engine_load: 22, dtc_codes: ['P0300', 'P0562'] }];

  it('averages valid readings, drops out-of-range ones, merges DTCs', () => {
    const f = buildFeatures(sensors, obd, G);
    expect(f.ds18b20_temp_c).toBeCloseTo(91);
    expect(f.battery_voltage_v).toBeCloseTo(14.1);
    expect(f.engine_rpm).toBeCloseTo(860);
    expect(f.dtc_codes).toBe('P0300;P0562');
    expect(missingInputs(f)).toEqual([]);
  });

  it('reports missing inputs', () => {
    expect(missingInputs(buildFeatures([], [], G))).toEqual([
      'ds18b20_temp_c', 'battery_voltage_v', 'vibration_rms_g', 'vibration_peak_g',
    ]);
  });
});
