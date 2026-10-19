import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { pool } from '../config/db.js';
import { logger } from '../config/logger.js';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../migrations');

const files = (await readdir(dir)).filter((f) => f.endsWith('.sql')).sort();
for (const f of files) {
  logger.info(`applying ${f}`);
  await pool.query(await readFile(path.join(dir, f), 'utf8'));
}
await pool.end();
logger.info('migrations complete');
