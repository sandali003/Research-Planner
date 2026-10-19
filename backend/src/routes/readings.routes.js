import { Router } from 'express';
import { z } from 'zod';
import { requireDevice } from '../middleware/deviceAuth.js';
import { validate } from '../middleware/validate.js';
import { ingestObdReadings, ingestSensorReadings } from '../services/ingestion.service.js';
import { asyncHandler } from '../utils/httpError.js';

const router = Router();
router.use(requireDevice);

const ts = z.coerce.date().optional();

const sensorBatch = z.object({
  readings: z.array(z.object({
    ts,
    accel_x: z.number().int().min(-32768).max(32767).optional(),
    accel_y: z.number().int().min(-32768).max(32767).optional(),
    accel_z: z.number().int().min(-32768).max(32767).optional(),
    temperature_c: z.number().min(-60).max(200).optional(),
    pin_voltage_v: z.number().min(0).max(5).optional(),
  })).min(1).max(500),
});

const obdBatch = z.object({
  readings: z.array(z.object({
    ts,
    rpm: z.number().min(0).max(20000).optional(),
    engine_load: z.number().min(0).max(100).optional(),
    coolant_temp: z.number().min(-60).max(250).optional(),
    intake_temp: z.number().min(-60).max(250).optional(),
    speed: z.number().min(0).max(400).optional(),
    dtc_codes: z.array(z.string().regex(/^[PCBU][0-9A-F]{4}$/i)).max(20).optional(),
  })).min(1).max(500),
});

router.post('/', validate(sensorBatch), asyncHandler(async (req, res) => {
  res.status(201).json(await ingestSensorReadings(req.device.vehicleId, req.body.readings));
}));

router.post('/obd', validate(obdBatch), asyncHandler(async (req, res) => {
  res.status(201).json(await ingestObdReadings(req.device.vehicleId, req.body.readings));
}));

export default router;
