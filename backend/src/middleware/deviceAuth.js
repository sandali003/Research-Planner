import crypto from 'node:crypto';
import { query } from '../config/db.js';
import { HttpError, asyncHandler } from '../utils/httpError.js';

export const hashKey = (key) => crypto.createHash('sha256').update(key).digest('hex');
export const generateKey = () => crypto.randomBytes(24).toString('hex');

// ESP32 authenticates with the x-device-key header; the key identifies device + vehicle.
export const requireDevice = asyncHandler(async (req, _res, next) => {
  const key = req.headers['x-device-key'];
  if (!key || typeof key !== 'string') throw new HttpError(401, 'Missing x-device-key');
  const { rows } = await query('SELECT id, vehicle_id FROM devices WHERE api_key_hash = $1', [hashKey(key)]);
  if (!rows[0]) throw new HttpError(401, 'Invalid device key');
  req.device = { id: rows[0].id, vehicleId: rows[0].vehicle_id };
  next();
});
