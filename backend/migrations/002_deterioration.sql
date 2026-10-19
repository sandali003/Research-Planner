-- Component 3: age- and mileage-adjusted deterioration assessments
CREATE TABLE IF NOT EXISTS deterioration_assessments (
  id              SERIAL PRIMARY KEY,
  vehicle_id      INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  vehicle_model   TEXT NOT NULL,
  age_years       REAL NOT NULL,
  odometer_km     REAL NOT NULL,
  component       TEXT NOT NULL,
  component_state TEXT NOT NULL CHECK (component_state IN ('Good', 'Fair', 'Poor', 'Critical')),
  expected_score  REAL NOT NULL,   -- condition expected for age + mileage (0-100)
  observed_score  REAL NOT NULL,   -- condition estimated from inspection evidence (0-100)
  deviation       REAL NOT NULL,   -- observed - expected; negative = worse than expected
  status          TEXT NOT NULL,   -- Normal / Slightly high / High
  reasons         JSONB NOT NULL DEFAULT '[]',
  model_version   TEXT,
  latency_ms      INTEGER,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS deterioration_vehicle_created ON deterioration_assessments (vehicle_id, created_at DESC);
