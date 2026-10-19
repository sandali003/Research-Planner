import { env } from '../config/env.js';
import { HttpError } from '../utils/httpError.js';

async function call(baseUrl, path, init) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), env.ML_TIMEOUT_MS);
  try {
    const res = await fetch(`${baseUrl}${path}`, { ...init, signal: ctrl.signal });
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

// Component 3 (Component3-Deterioration/app.py)
export const assessDeterioration = (input) =>
  call(env.DETERIORATION_SERVICE_URL, '/api/deterioration', postJson(input));

export const deteriorationHealth = () => call(env.DETERIORATION_SERVICE_URL, '/health');
