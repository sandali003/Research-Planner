import { Router } from 'express';
import { z } from 'zod';
import { requireUser } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';
import { getAccessibleVehicle } from '../repositories/vehicles.repo.js';
import { runValueUplift } from '../services/valueUplift.service.js';
import { asyncHandler } from '../utils/httpError.js';

// Component 4: Maintenance Recommendation and Condition-Based Valuation (mounted under /api/v1/vehicles)
const router = Router();
router.use(requireUser);

const idParam = z.object({ id: z.coerce.number().int().positive() });

export const upliftBody = z.object({
  budget_lkr: z.number().min(0).max(100_000_000).optional(),
  sell_within_days: z.number().int().min(0).max(365).optional(),
  buyer: z.enum(['private', 'dealer']).optional(),
  // Defaults: the latest deterioration assessment's odometer, fuel and engine size
  mileage_km: z.number().min(0).max(600_000).optional(),
  fuel_type: z.enum(['petrol', 'diesel', 'hybrid']).optional(),
  engine_cc: z.number().min(600).max(6000).optional(),
});

router.post('/:id/value-uplift', validate(idParam, 'params'), validate(upliftBody),
  asyncHandler(async (req, res) => {
    const vehicle = await getAccessibleVehicle(req.params.id, req.user);
    res.json(await runValueUplift(vehicle, req.body));
  }));

export default router;
