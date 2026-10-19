import 'dotenv/config';
import { z } from 'zod';

const schema = z.object({
  PORT: z.coerce.number().default(3000),
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  DATABASE_URL: z.string().min(1),
  DATABASE_SSL: z.enum(['true', 'false']).default('false').transform((v) => v === 'true'),
  JWT_SECRET: z.string().min(16),
  JWT_EXPIRES_IN: z.string().default('12h'),
  ML_SERVICE_URL: z.string().url().default('http://127.0.0.1:8001'),
  ML_TIMEOUT_MS: z.coerce.number().default(1500),
  HIDDEN_FAULT_URL: z.string().url().default('http://127.0.0.1:8002'),
  HIDDEN_FAULT_TIMEOUT_MS: z.coerce.number().default(2000),
  DETERIORATION_SERVICE_URL: z.string().url().default('http://127.0.0.1:8002'),
  ACCEL_LSB_PER_G: z.coerce.number().default(16384),
  VOLTAGE_DIVIDER_RATIO: z.coerce.number().default(5),
  CORS_ORIGINS: z.string().default(''),
});

const parsed = schema.safeParse(process.env);
if (!parsed.success) {
  console.error('Invalid environment configuration:', parsed.error.flatten().fieldErrors);
  process.exit(1);
}

export const env = {
  ...parsed.data,
  corsOrigins: parsed.data.CORS_ORIGINS.split(',').map((s) => s.trim()).filter(Boolean),
};
