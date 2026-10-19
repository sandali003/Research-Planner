import { Router } from 'express';
import { z } from 'zod';
import { query } from '../config/db.js';
import { requireUser } from '../middleware/auth.js';
import { generateKey, hashKey } from '../middleware/deviceAuth.js';
import { validate } from '../middleware/validate.js';
import { getAccessibleVehicle } from '../repositories/vehicles.repo.js';
import { runAssessment } from '../services/assessment.service.js';
import { runDeterioration } from '../services/deterioration.service.js';
import { asyncHandler } from '../utils/httpError.js';

const router = Router();
router.use(requireUser);

const idParam = z.object({ id: z.coerce.number().int().positive() });
const vehicleBody = z.object({
  vin: z.string().max(32).optional(),
  make: z.string().max(60).optional(),
  model: z.string().max(60).optional(),
  year: z.number().int().min(1950).max(2100).optional(),
});

router.post('/', validate(vehicleBody), asyncHandler(async (req, res) => {
  const { vin, make, model, year } = req.body;
  const { rows } = await query(
    'INSERT INTO vehicles (owner_id, vin, make, model, year) VALUES ($1,$2,$3,$4,$5) RETURNING *',
    [req.user.id, vin ?? null, make ?? null, model ?? null, year ?? null],
  );
  res.status(201).json(rows[0]);
}));

router.get('/', asyncHandler(async (req, res) => {
  const { rows } = await query('SELECT * FROM vehicles WHERE owner_id = $1 ORDER BY id DESC', [req.user.id]);
  res.json(rows);
}));

// Register an ESP32: the plaintext key is returned once and only its hash is stored.
router.post('/:id/devices', validate(idParam, 'params'), validate(z.object({ name: z.string().max(60).optional() })),
  asyncHandler(async (req, res) => {
    const vehicle = await getAccessibleVehicle(req.params.id, req.user);
    const key = generateKey();
    const { rows } = await query(
      'INSERT INTO devices (vehicle_id, name, api_key_hash) VALUES ($1,$2,$3) RETURNING id, vehicle_id, name',
      [vehicle.id, req.body.name ?? null, hashKey(key)],
    );
    res.status(201).json({ ...rows[0], api_key: key, note: 'Store this key now; it will not be shown again.' });
  }));

// Latest raw readings (oldest first) from the vehicle's newest session, for the live dashboard.
router.get('/:id/readings/latest', validate(idParam, 'params'),
  validate(z.object({ limit: z.coerce.number().int().min(1).max(300).default(60) }), 'query'),
  asyncHandler(async (req, res) => {
    const vehicle = await getAccessibleVehicle(req.params.id, req.user);
    const session = await query(
      `SELECT id, condition, started_at, ended_at FROM sessions WHERE vehicle_id = $1
       ORDER BY (ended_at IS NULL) DESC, started_at DESC LIMIT 1`,
      [vehicle.id],
    );
    const s = session.rows[0];
    if (!s) return res.json({ session: null, sensor: [], obd: [] });
    const [sensor, obd] = await Promise.all([
      query(`SELECT ts, accel_x, accel_y, accel_z, temp_c, voltage_v FROM
               (SELECT * FROM sensor_readings WHERE session_id = $1 ORDER BY ts DESC LIMIT $2) t ORDER BY ts`, [s.id, req.query.limit]),
      query(`SELECT ts, rpm, engine_load, coolant_temp, intake_temp, speed, dtc_codes FROM
               (SELECT * FROM obd_readings WHERE session_id = $1 ORDER BY ts DESC LIMIT $2) t ORDER BY ts`, [s.id, req.query.limit]),
    ]);
    res.json({ session: s, sensor: sensor.rows, obd: obd.rows });
  }));

// Full result (SHAP factors etc.) of the newest assessment, or null.
router.get('/:id/assessments/latest', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.params.id, req.user);
  const { rows } = await query('SELECT * FROM assessments WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 1', [vehicle.id]);
  res.json(rows[0] ?? null);
}));

// ---- assessments ----
router.post('/:id/assessments', validate(idParam, 'params'),
  validate(z.object({ window_seconds: z.number().int().min(2).max(300).default(10) })),
  asyncHandler(async (req, res) => {
    const vehicle = await getAccessibleVehicle(req.params.id, req.user);
    res.status(201).json(await runAssessment(vehicle.id, req.body.window_seconds));
  }));

router.get('/:id/assessments', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.params.id, req.user);
  const { rows } = await query(
    `SELECT id, session_id, overall_score, condition, model_version, latency_ms, created_at
     FROM assessments WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 50`,
    [vehicle.id],
  );
  res.json(rows);
}));

// ---- Component 3: deterioration ----
// vehicle_model and age_years default to the vehicle's model and year.
const deteriorationBody = z.object({
  odometer_km: z.number().min(0).max(2_000_000),
  component: z.string().min(1).max(60),
  component_state: z.enum(['Good', 'Fair', 'Poor', 'Critical']),
  vehicle_model: z.string().min(1).max(60).optional(),
  age_years: z.number().min(0).max(60).optional(),
});

router.post('/:id/deterioration', validate(idParam, 'params'), validate(deteriorationBody),
  asyncHandler(async (req, res) => {
    const vehicle = await getAccessibleVehicle(req.params.id, req.user);
    res.status(201).json(await runDeterioration(vehicle, req.body));
  }));

router.get('/:id/deterioration', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.params.id, req.user);
  const { rows } = await query(
    'SELECT * FROM deterioration_assessments WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 50',
    [vehicle.id],
  );
  res.json(rows);
}));

// Stable contract for Components 2-4: latest score + the processed features it was based on.
router.get('/:id/health-summary', validate(idParam, 'params'), asyncHandler(async (req, res) => {
  const vehicle = await getAccessibleVehicle(req.params.id, req.user);
  const { rows } = await query(
    'SELECT * FROM assessments WHERE vehicle_id = $1 ORDER BY created_at DESC LIMIT 1',
    [vehicle.id],
  );
  const a = rows[0];
  res.json({
    vehicle_id: vehicle.id,
    assessed_at: a?.created_at ?? null,
    overall_score: a?.overall_score ?? null,
    condition: a?.condition ?? null,
    component_scores: a?.result.components ?? null,
    features: a?.features ?? null,
    explanation: a?.result.explanation ?? null,
  });
}));

export default router;
