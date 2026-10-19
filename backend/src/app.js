import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import { env } from './config/env.js';
import { errorHandler, notFound } from './middleware/errorHandler.js';
import authRoutes from './routes/auth.routes.js';
import vehicleRoutes from './routes/vehicles.routes.js';
import sessionRoutes from './routes/sessions.routes.js';
import readingRoutes from './routes/readings.routes.js';
import assessmentRoutes from './routes/assessments.routes.js';
import healthRoutes from './routes/health.routes.js';
import hiddenFaultRoutes from './routes/hiddenFaults.routes.js';

export const app = express();

app.disable('x-powered-by');
app.use(helmet());
app.use(cors({ origin: env.corsOrigins, credentials: false }));
app.use(express.json({ limit: '256kb' }));

// Brute-force protection on login/register; device ingestion gets a higher ceiling.
app.use('/api/v1/auth', rateLimit({ windowMs: 15 * 60 * 1000, limit: 30, standardHeaders: true, legacyHeaders: false }));
app.use('/api/v1/readings', rateLimit({ windowMs: 60 * 1000, limit: 300, standardHeaders: true, legacyHeaders: false }));

app.use('/health', healthRoutes);
app.use('/api/v1/auth', authRoutes);
app.use('/api/v1/vehicles', vehicleRoutes);
app.use('/api/v1/vehicles', hiddenFaultRoutes);
app.use('/api/v1/sessions', sessionRoutes);
app.use('/api/v1/readings', readingRoutes);
app.use('/api/v1/assessments', assessmentRoutes);

app.use(notFound);
app.use(errorHandler);
