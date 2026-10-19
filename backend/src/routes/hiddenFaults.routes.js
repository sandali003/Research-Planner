import { Router } from 'express';
import { z } from 'zod';
import { requireUser } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';
import { getAccessibleVehicle } from '../repositories/vehicles.repo.js';
import {
  getFaultCheck, listFaultChecks, runFaultCheck, runManualFaultCheck,
} from '../services/hiddenFault.service.js';
import { HttpError, asyncHandler } from '../utils/httpError.js';

// Component 2: Hidden Fault Prediction and Mitigation (mounted under /api/v1/vehicles)
const router = Router();
router.use(requireUser);

const idParam = z.object({ id: z.coerce.number().int().positive() });
const checkParam = idParam.extend({ checkId: z.coerce.number().int().positive() });

const manualInputs = z.object({
  engine_rpm: z.number().min(0).max(10000).optional(),
  engine_load_pct: z.number().min(0).max(100).optional(),
  coolant_temp_c: z.number().min(-40).max(150).optional(),
  battery_voltage_v: z.number().min(0).max(20).optional(),
  vibration_x_g: z.number().min(-4).max(4).optional(),
  vibration_y_g: z.number().min(-4).max(4).optional(),
  vibration_z_g: z.number().min(-4).max(4).optional(),
  dtc_codes: z.array(z.string().regex(/^[PCBU][0-9A-F]{4}$/i)).max(20).optional(),
});

// Run a check on the latest device readings
router.post('/:id/hidden-faults', validate(idParam, 'params'),
  validate(z.object({ window_seconds: z.number().int().min(2).max(300).default(30) })),
  asyncHandler(async (req, res) => {
    const vehicle = await getAccessibleVehicle(req.params.id, req.user);
    res.status(201).json(await runFaultCheck(vehicle, req.body.window_seconds));
  }));

// Run a check on readings entered by hand
router.post('/:id/hidden-faults/manual', validate(idParam, 'params'), validate(manualInputs),
  asyncHandler(async (req, res) => {
    const vehicle = await getAccessibleVehicle(req.params.id, req.user);
    res.status(201).json(await runManualFaultCheck(vehicle, req.body));
  }));

router.get('/:id/hidden-faults', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.params.id, req.user);
  res.json(await listFaultChecks(vehicle.id));
}));

router.get('/:id/hidden-faults/latest', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.params.id, req.user);
  res.json(await getFaultCheck(vehicle.id, null));
}));

router.get('/:id/hidden-faults/:checkId', validate(checkParam, 'params'), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.params.id, req.user);
  const check = await getFaultCheck(vehicle.id, req.params.checkId);
  if (!check) throw new HttpError(404, 'Hidden fault check not found');
  res.json(check);
}));

export default router;
