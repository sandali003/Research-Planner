import { Router } from 'express';
import { query } from '../config/db.js';
import { hiddenFaultHealth, mlHealth } from '../services/mlClient.service.js';
import { asyncHandler } from '../utils/httpError.js';

const router = Router();

router.get('/', (_req, res) => res.json({ status: 'ok' }));

router.get('/db', asyncHandler(async (_req, res) => {
  await query('SELECT 1');
  res.json({ database: 'connected' });
}));

router.get('/ml', asyncHandler(async (_req, res) => {
  res.json(await mlHealth());
}));

router.get('/hidden-fault', asyncHandler(async (_req, res) => {
  res.json(await hiddenFaultHealth());
}));

export default router;
