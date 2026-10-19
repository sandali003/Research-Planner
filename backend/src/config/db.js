import pg from 'pg';
import { env } from './env.js';

// Hosted databases (e.g. Supabase) require SSL; a local PostgreSQL usually has it off.
export const pool = new pg.Pool({
  connectionString: env.DATABASE_URL,
  max: 10,
  ssl: env.DATABASE_SSL ? { rejectUnauthorized: false } : undefined,
});
export const query = (text, params) => pool.query(text, params);
