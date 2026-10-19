import { describe, expect, it } from 'vitest';
import { vehicleAge } from '../src/services/deterioration.service.js';

describe('vehicleAge', () => {
  it('counts from mid-year of manufacture', () => {
    expect(vehicleAge(2016, new Date(Date.UTC(2024, 0, 1)))).toBeCloseTo(7.5, 1);
  });

  it('is never negative', () => {
    expect(vehicleAge(2030, new Date(Date.UTC(2024, 0, 1)))).toBe(0);
  });
});
