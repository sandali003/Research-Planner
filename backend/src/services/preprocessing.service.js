// Turns a window of raw ESP32 + OBD-II readings into the feature set the ML model expects.
// Pure functions (no I/O) so they are easy to unit test.

const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;

/**
 * Vibration RMS / peak in g from raw MPU6050 counts.
 * Gravity is removed by subtracting the mean acceleration magnitude over the window.
 */
export function vibrationFeatures(samples, lsbPerG) {
  const mags = samples
    .filter((s) => s.accel_x != null && s.accel_y != null && s.accel_z != null)
    .map((s) => Math.hypot(s.accel_x, s.accel_y, s.accel_z) / lsbPerG);
  if (mags.length < 2) return { rms: null, peak: null };
  const m = mean(mags);
  const dyn = mags.map((v) => v - m);
  return {
    rms: Math.sqrt(mean(dyn.map((d) => d * d))),
    peak: Math.max(...dyn.map(Math.abs)),
  };
}

const numeric = (rows, key) => rows.map((r) => r[key]).filter((v) => typeof v === 'number' && Number.isFinite(v));

/** Reject physically impossible readings (sensor glitches) before averaging. */
const inRange = (v, lo, hi) => v >= lo && v <= hi;

export function buildFeatures(sensorRows, obdRows, lsbPerG = 16384) {
  const temps = numeric(sensorRows, 'temp_c').filter((v) => inRange(v, -40, 150));
  const volts = numeric(sensorRows, 'voltage_v').filter((v) => inRange(v, 0, 20));
  const vib = vibrationFeatures(sensorRows, lsbPerG);

  const dtcs = [...new Set(obdRows.flatMap((r) => r.dtc_codes || []))];
  const rpm = numeric(obdRows, 'rpm');
  const load = numeric(obdRows, 'engine_load');

  return {
    ds18b20_temp_c: temps.length ? mean(temps) : null,
    battery_voltage_v: volts.length ? mean(volts) : null,
    vibration_rms_g: vib.rms,
    vibration_peak_g: vib.peak,
    dtc_codes: dtcs.join(';'),
    engine_rpm: rpm.length ? mean(rpm) : null,
    engine_load_pct: load.length ? mean(load) : null,
  };
}

/** Required inputs for a meaningful assessment; returns the names that are missing. */
export function missingInputs(f) {
  return ['ds18b20_temp_c', 'battery_voltage_v', 'vibration_rms_g', 'vibration_peak_g'].filter((k) => f[k] == null);
}
