import { query } from '../config/db.js';
import { HttpError } from '../utils/httpError.js';

/** Returns the vehicle if it belongs to the user (admins may access any); 404 otherwise. */
export async function getAccessibleVehicle(vehicleId, user) {
  const { rows } = await query('SELECT * FROM vehicles WHERE id = $1', [vehicleId]);
  const v = rows[0];
  if (!v || (v.owner_id !== user.id && user.role !== 'admin')) throw new HttpError(404, 'Vehicle not found');
  return v;
}
