import { env } from '../config/env.js';
import { HttpError } from '../utils/httpError.js';

async function callService(name, baseUrl, timeoutMs, path, init) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${baseUrl}${path}`, { ...init, signal: ctrl.signal });
    if (res.status === 422) {
      const body = await res.json().catch(() => null);
      throw new HttpError(422, `${name} rejected the inputs`, body?.detail);
    }
    if (!res.ok) throw new HttpError(502, `${name} returned ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof HttpError) throw err;
    throw new HttpError(503, `${name} unavailable`);
  } finally {
    clearTimeout(timer);
  }
}

const postJson = (body) => ({
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

// Component 1: vehicle health service (ml-service)
const callHealth = (path, init) => callService('ML service', env.ML_SERVICE_URL, env.ML_TIMEOUT_MS, path, init);

export const predict = (features) => callHealth('/predict', postJson(features));

export const mlHealth = () => callHealth('/health');

// Component 2: hidden fault prediction and mitigation service
const callHiddenFault = (path, init) =>
  callService('Hidden fault service', env.HIDDEN_FAULT_URL, env.HIDDEN_FAULT_TIMEOUT_MS, path, init);

export const predictHiddenFaults = (features) => callHiddenFault('/predict', postJson(features));

export const hiddenFaultHealth = () => callHiddenFault('/health');

// Component 3: deterioration service (Component3-Deterioration/app.py)
const callDeterioration = (path, init) =>
  callService('Deterioration service', env.DETERIORATION_SERVICE_URL, env.DETERIORATION_TIMEOUT_MS, path, init);

// Component-wise assessment (one or more inspected components)
export const assessDeterioration = (input) => callDeterioration('/api/assess', postJson(input));

export const deteriorationHealth = () => callDeterioration('/health');

// Component 4: value-uplift service (component4/real/api.py)
const callValuation = (path, init) =>
  callService('Valuation service', env.VALUATION_SERVICE_URL, env.VALUATION_TIMEOUT_MS, path, init);

export const valueUplift = (body) => callValuation('/api/value-uplift', postJson(body));

export const valuationHealth = () => callValuation('/health');

// Chart data: expected condition by age, and the training inspections for one vehicle model
export async function deteriorationContext(vehicleModel, kmPerYear) {
  const model = encodeURIComponent(vehicleModel);
  const [curve, history] = await Promise.all([
    callDeterioration(`/api/expected-curve?vehicle_model=${model}&km_per_year=${kmPerYear}`),
    callDeterioration(`/api/history?vehicle_model=${model}`),
  ]);
  return { curve, ...history };
}
