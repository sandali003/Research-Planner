import { Router } from 'express';
import { z } from 'zod';
import { query } from '../config/db.js';
import { requireUser } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';
import { getAccessibleVehicle } from '../repositories/vehicles.repo.js';
import { HttpError, asyncHandler } from '../utils/httpError.js';

const router = Router();
router.use(requireUser);

const startBody = z.object({
  vehicle_id: z.number().int().positive(),
  condition: z.enum(['idle', 'driving']).default('idle'),
});

// Starting a session closes any session still open for that vehicle.
router.post('/', validate(startBody), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.body.vehicle_id, req.user);
  await query('UPDATE sessions SET ended_at = now() WHERE vehicle_id = $1 AND ended_at IS NULL', [vehicle.id]);
  const { rows } = await query(
    'INSERT INTO sessions (vehicle_id, condition) VALUES ($1,$2) RETURNING *',
    [vehicle.id, req.body.condition],
  );
  res.status(201).json(rows[0]);
}));

const idParam = z.object({ id: z.coerce.number().int().positive() });

async function ownedSession(id, user) {
  const { rows } = await query('SELECT * FROM sessions WHERE id = $1', [id]);
  if (!rows[0]) throw new HttpError(404, 'Session not found');
  await getAccessibleVehicle(rows[0].vehicle_id, user);
  return rows[0];
}

router.post('/:id/stop', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  await ownedSession(req.params.id, req.user);
  const { rows } = await query('UPDATE sessions SET ended_at = COALESCE(ended_at, now()) WHERE id = $1 RETURNING *', [req.params.id]);
  res.json(rows[0]);
}));

router.get('/:id', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  const session = await ownedSession(req.params.id, req.user);
  const counts = await query(
    `SELECT (SELECT count(*) FROM sensor_readings WHERE session_id = $1)::int AS sensor_readings,
            (SELECT count(*) FROM obd_readings WHERE session_id = $1)::int AS obd_readings`,
    [session.id],
  );
  res.json({ ...session, ...counts.rows[0] });
}));

export default router;
