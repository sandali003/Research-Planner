import { Router } from 'express';
import bcrypt from 'bcryptjs';
import { z } from 'zod';
import { query } from '../config/db.js';
import { signToken } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';
import { HttpError, asyncHandler } from '../utils/httpError.js';

const router = Router();
const credentials = z.object({ email: z.string().email().toLowerCase(), password: z.string().min(8).max(128) });

router.post('/register', validate(credentials), asyncHandler(async (req, res) => {
  const hash = await bcrypt.hash(req.body.password, 10);
  try {
    const { rows } = await query(
      'INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id, email, role',
      [req.body.email, hash],
    );
    res.status(201).json({ user: rows[0], token: signToken(rows[0]) });
  } catch (err) {
    if (err.code === '23505') throw new HttpError(409, 'Email already registered');
    throw err;
  }
}));

router.post('/login', validate(credentials), asyncHandler(async (req, res) => {
  const { rows } = await query('SELECT id, email, role, password_hash FROM users WHERE email = $1', [req.body.email]);
  const user = rows[0];
  if (!user || !(await bcrypt.compare(req.body.password, user.password_hash))) {
    throw new HttpError(401, 'Invalid email or password');
  }
  res.json({ user: { id: user.id, email: user.email, role: user.role }, token: signToken(user) });
}));

export default router;
