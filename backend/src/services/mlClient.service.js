import { env } from '../config/env.js';
import { HttpError } from '../utils/httpError.js';

async function callService(name, baseUrl, timeoutMs, path, init) {
async function call(baseUrl, path, init) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${baseUrl}${path}`, { ...init, signal: ctrl.signal });
    if (res.status === 422) {
      const body = await res.json().catch(() => null);
      throw new HttpError(422, `${name} rejected the inputs`, body?.detail);
    }
    if (!res.ok) throw new HttpError(502, `${name} returned ${res.status}`);
    if (!res.ok) throw new HttpError(502, `ML service returned ${res.status}`);
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
const call = (path, init) => callService('ML service', env.ML_SERVICE_URL, env.ML_TIMEOUT_MS, path, init);

export const predict = (features) => call('/predict', postJson(features));

export const mlHealth = () => call('/health');

// Component 2: hidden fault prediction and mitigation service
const callHiddenFault = (path, init) =>
  callService('Hidden fault service', env.HIDDEN_FAULT_URL, env.HIDDEN_FAULT_TIMEOUT_MS, path, init);

export const predictHiddenFaults = (features) => callHiddenFault('/predict', postJson(features));

export const hiddenFaultHealth = () => callHiddenFault('/health');

export const predict = (features) => call(env.ML_SERVICE_URL, '/predict', postJson(features));

export const mlHealth = () => call(env.ML_SERVICE_URL, '/health');

// Component 3 (Component3-Deterioration/app.py)
export const assessDeterioration = (input) =>
  call(env.DETERIORATION_SERVICE_URL, '/api/deterioration', postJson(input));

export const deteriorationHealth = () => call(env.DETERIORATION_SERVICE_URL, '/health');
