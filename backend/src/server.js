import { app } from './app.js';
import { env } from './config/env.js';
import { pool } from './config/db.js';
import { logger } from './config/logger.js';

const server = app.listen(env.PORT, () => logger.info(`AutoSense API listening on :${env.PORT}`));

async function shutdown(signal) {
  logger.info(`${signal} received, shutting down`);
  server.close(async () => {
    await pool.end();
    process.exit(0);
  });
}
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
