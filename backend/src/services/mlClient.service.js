import { env } from '../config/env.js';
import { HttpError } from '../utils/httpError.js';

async function call(baseUrl, path, init, timeoutMs = env.ML_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${baseUrl}${path}`, { ...init, signal: ctrl.signal });
    // Pass validation errors (e.g. unknown component) through to the caller
    if (res.status === 422) throw new HttpError(422, 'ML service rejected the input', (await res.json()).detail);
    if (!res.ok) throw new HttpError(502, `ML service returned ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof HttpError) throw err;
    throw new HttpError(503, 'ML service unavailable');
  } finally {
    clearTimeout(timer);
  }
}

const postJson = (body) => ({
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

export const predict = (features) => call(env.ML_SERVICE_URL, '/predict', postJson(features));

export const mlHealth = () => call(env.ML_SERVICE_URL, '/health');

// Component 3 (Component3-Deterioration/app.py): component-wise deterioration assessment
export const assessDeterioration = (input) =>
  call(env.DETERIORATION_SERVICE_URL, '/api/assess', postJson(input), env.DETERIORATION_TIMEOUT_MS);

export const deteriorationHealth = () => call(env.DETERIORATION_SERVICE_URL, '/health');
