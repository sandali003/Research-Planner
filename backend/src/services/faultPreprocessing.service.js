// Turns a window of raw ESP32 + OBD-II readings into the inputs of the
// hidden fault component (Component 2). Pure functions (no I/O).

const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;

const numeric = (rows, key, lo, hi) => rows
  .map((r) => r[key])
  .filter((v) => typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi);

const meanOrNull = (values) => (values.length ? mean(values) : null);

/**
 * Per-axis vibration in g from raw MPU6050 counts.
 * Gravity (and sensor mounting angle) is removed by subtracting each axis'
 * mean over the window; the RMS of what is left is the vibration level.
 */
export function axisVibration(samples, lsbPerG) {
  const pts = samples.filter((s) => [s.accel_x, s.accel_y, s.accel_z].every((v) => typeof v === 'number'));
  if (pts.length < 2) return null;
  const rms = (axis) => {
    const vals = pts.map((s) => s[axis] / lsbPerG);
    const m = mean(vals);
    return Math.sqrt(mean(vals.map((v) => (v - m) ** 2)));
  };
  return { x: rms('accel_x'), y: rms('accel_y'), z: rms('accel_z') };
}

export function buildFaultFeatures(sensorRows, obdRows, lsbPerG = 16384, vehicleModel = null) {
  const vib = axisVibration(sensorRows, lsbPerG);
  const coolant = meanOrNull(numeric(obdRows, 'coolant_temp', -40, 150));
  const ds18b20 = meanOrNull(numeric(sensorRows, 'temp_c', -40, 150));

  return {
    engine_rpm: meanOrNull(numeric(obdRows, 'rpm', 0, 10000)),
    engine_load_pct: meanOrNull(numeric(obdRows, 'engine_load', 0, 100)),
    coolant_temp_c: coolant,
    // Engine temperature for the classifier: OBD coolant temp first, DS18B20 as fallback
    engine_temp_c: coolant ?? ds18b20,
    ds18b20_temp_c: ds18b20,
    battery_voltage_v: meanOrNull(numeric(sensorRows, 'voltage_v', 0, 20)),
    vibration_x_g: vib?.x ?? null,
    vibration_y_g: vib?.y ?? null,
    vibration_z_g: vib?.z ?? null,
    vehicle_model: vehicleModel,
    dtc_codes: [...new Set(obdRows.flatMap((r) => r.dtc_codes || []))],
  };
}

// Inputs needed by each model of the component
const MODEL_INPUTS = {
  fault_classifier: ['engine_rpm', 'battery_voltage_v', 'engine_temp_c', 'engine_load_pct'],
  obd_rules_and_anomaly: ['engine_rpm', 'engine_load_pct', 'coolant_temp_c', 'vibration_x_g', 'vibration_y_g', 'vibration_z_g'],
};

/** Missing inputs per model; empty object when at least one model can run. */
export function missingFaultInputs(f) {
  const missing = Object.fromEntries(
    Object.entries(MODEL_INPUTS).map(([model, keys]) => [model, keys.filter((k) => f[k] == null)]),
  );
  return Object.values(missing).some((keys) => keys.length === 0) ? {} : missing;
}
