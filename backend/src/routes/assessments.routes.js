import { Router } from 'express';
import { z } from 'zod';
import { query } from '../config/db.js';
import { requireUser } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';
import { getAccessibleVehicle } from '../repositories/vehicles.repo.js';
import { HttpError, asyncHandler } from '../utils/httpError.js';

const router = Router();
router.use(requireUser);

router.get('/:id', validate(z.object({ id: z.coerce.number().int().positive() }), 'params'),
  asyncHandler(async (req, res) => {
    const { rows } = await query('SELECT * FROM assessments WHERE id = $1', [req.params.id]);
    if (!rows[0]) throw new HttpError(404, 'Assessment not found');
    await getAccessibleVehicle(rows[0].vehicle_id, req.user); // ownership check
    res.json(rows[0]);
  }));

export default router;
