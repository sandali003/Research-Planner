import type { AssessmentResult } from './types';

export const CONDITION_COLOR: Record<AssessmentResult['condition'], string> = {
  Good: 'var(--good)',
  Fair: 'var(--fair)',
  Poor: 'var(--poor)',
  Critical: 'var(--critical)',
};

export const fmt = (v: number | null | undefined, digits = 1) =>
  v == null || Number.isNaN(v) ? '—' : v.toFixed(digits);

export const fmtTime = (iso: string) => new Date(iso).toLocaleString();

/** Vibration RMS (g) of raw MPU6050 counts with gravity removed; mirrors the backend preprocessing. */
export function vibrationSeries(rows: { accel_x: number | null; accel_y: number | null; accel_z: number | null }[], lsbPerG = 16384) {
  const mags = rows.map((r) =>
    r.accel_x == null || r.accel_y == null || r.accel_z == null
      ? null
      : Math.hypot(r.accel_x, r.accel_y, r.accel_z) / lsbPerG,
  );
  const valid = mags.filter((m): m is number => m != null);
  if (!valid.length) return mags.map(() => null);
  const mean = valid.reduce((s, v) => s + v, 0) / valid.length;
  return mags.map((m) => (m == null ? null : Math.abs(m - mean)));
}
