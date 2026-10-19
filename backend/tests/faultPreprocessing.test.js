import { describe, expect, it } from 'vitest';
import { axisVibration, buildFaultFeatures, missingFaultInputs } from '../src/services/faultPreprocessing.service.js';

const G = 16384;

describe('axisVibration', () => {
  it('is ~0 on every axis for a vehicle at rest, whatever the mounting angle', () => {
    const rest = Array.from({ length: 20 }, () => ({ accel_x: 0.3 * G, accel_y: 0, accel_z: 0.95 * G }));
    const v = axisVibration(rest, G);
    expect(v.x).toBeCloseTo(0, 6);
    expect(v.y).toBeCloseTo(0, 6);
    expect(v.z).toBeCloseTo(0, 6);
  });

  it('measures the oscillation on the shaking axis only', () => {
    const shaking = Array.from({ length: 100 }, (_, i) => ({
      accel_x: 0, accel_y: 0, accel_z: G + (i % 2 ? 0.2 : -0.2) * G,
    }));
    const v = axisVibration(shaking, G);
    expect(v.x).toBeCloseTo(0, 6);
    expect(v.z).toBeCloseTo(0.2, 2);
  });

  it('returns null with too few samples', () => {
    expect(axisVibration([{ accel_x: 1, accel_y: 1, accel_z: 1 }], G)).toBeNull();
  });
});

describe('buildFaultFeatures', () => {
  const sensor = [
    { accel_x: 0, accel_y: 0, accel_z: G, temp_c: 80, voltage_v: 14.0 },
    { accel_x: 0, accel_y: 0, accel_z: G, temp_c: 999, voltage_v: 14.2 }, // glitch temp ignored
  ];
  const obd = [
    { rpm: 800, engine_load: 30, coolant_temp: 88, dtc_codes: ['P0300'] },
    { rpm: 900, engine_load: 40, coolant_temp: 90, dtc_codes: ['P0300'] },
  ];

  it('averages OBD-II and sensor values and keeps unique DTCs', () => {
    const f = buildFaultFeatures(sensor, obd, G, 'Axio');
    expect(f.engine_rpm).toBe(850);
    expect(f.engine_load_pct).toBe(35);
    expect(f.coolant_temp_c).toBe(89);
    expect(f.engine_temp_c).toBe(89);
    expect(f.ds18b20_temp_c).toBe(80);
    expect(f.battery_voltage_v).toBeCloseTo(14.1, 6);
    expect(f.vehicle_model).toBe('Axio');
    expect(f.dtc_codes).toEqual(['P0300']);
  });

  it('falls back to the DS18B20 temperature when there is no OBD coolant temp', () => {
    const f = buildFaultFeatures(sensor, [{ rpm: 800, engine_load: 30 }], G);
    expect(f.coolant_temp_c).toBeNull();
    expect(f.engine_temp_c).toBe(80);
  });
});

describe('missingFaultInputs', () => {
  const full = {
    engine_rpm: 800, engine_load_pct: 30, coolant_temp_c: 88, engine_temp_c: 88, battery_voltage_v: 14,
    vibration_x_g: 0.1, vibration_y_g: 0.1, vibration_z_g: 0.1,
  };

  it('is empty when both models can run', () => {
    expect(missingFaultInputs(full)).toEqual({});
  });

  it('is empty when only one model can run', () => {
    expect(missingFaultInputs({ ...full, vibration_x_g: null })).toEqual({});
  });

  it('lists what each model is missing when neither can run', () => {
    const m = missingFaultInputs({ ...full, engine_rpm: null });
    expect(m.fault_classifier).toEqual(['engine_rpm']);
    expect(m.obd_rules_and_anomaly).toEqual(['engine_rpm']);
  });
});
