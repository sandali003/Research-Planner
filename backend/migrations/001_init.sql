CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'user',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicles (
  id         SERIAL PRIMARY KEY,
  owner_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  vin        TEXT,
  make       TEXT,
  model      TEXT,
  year       INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS devices (
  id           SERIAL PRIMARY KEY,
  vehicle_id   INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  name         TEXT,
  api_key_hash TEXT NOT NULL UNIQUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
  id         SERIAL PRIMARY KEY,
  vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  condition  TEXT NOT NULL DEFAULT 'idle' CHECK (condition IN ('idle', 'driving')),
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sessions_vehicle_open ON sessions (vehicle_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS sensor_readings (
  id         BIGSERIAL PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
  accel_x    INTEGER,
  accel_y    INTEGER,
  accel_z    INTEGER,
  temp_c     REAL,
  voltage_v  REAL        -- battery voltage after divider conversion
);
CREATE INDEX IF NOT EXISTS sensor_readings_session_ts ON sensor_readings (session_id, ts);

CREATE TABLE IF NOT EXISTS obd_readings (
  id           BIGSERIAL PRIMARY KEY,
  session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
  rpm          REAL,
  engine_load  REAL,
  coolant_temp REAL,
  intake_temp  REAL,
  speed        REAL,
  dtc_codes    TEXT[] NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS obd_readings_session_ts ON obd_readings (session_id, ts);

CREATE TABLE IF NOT EXISTS assessments (
  id               SERIAL PRIMARY KEY,
  vehicle_id       INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  session_id       INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  overall_score    REAL NOT NULL,
  condition        TEXT NOT NULL,
  features         JSONB NOT NULL,
  result           JSONB NOT NULL,   -- component scores, SHAP factors, explanation
  model_version    TEXT,
  latency_ms       INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS assessments_vehicle_created ON assessments (vehicle_id, created_at DESC);

-- Mechanic / expert reference scores used to validate the model against real labels
CREATE TABLE IF NOT EXISTS reference_labels (
  id             SERIAL PRIMARY KEY,
  vehicle_id     INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  session_id     INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  mechanic_score REAL NOT NULL CHECK (mechanic_score BETWEEN 0 AND 100),
  notes          TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
