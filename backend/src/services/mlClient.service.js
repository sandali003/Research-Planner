import { env } from '../config/env.js';
import { HttpError } from '../utils/httpError.js';

async function call(path, init) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), env.ML_TIMEOUT_MS);
  try {
    const res = await fetch(`${env.ML_SERVICE_URL}${path}`, { ...init, signal: ctrl.signal });
    if (!res.ok) throw new HttpError(502, `ML service returned ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof HttpError) throw err;
    throw new HttpError(503, 'ML service unavailable');
  } finally {
    clearTimeout(timer);
  }
}

export const predict = (features) =>
  call('/predict', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(features),
  });

export const mlHealth = () => call('/health');
