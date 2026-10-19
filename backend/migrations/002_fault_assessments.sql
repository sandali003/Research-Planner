-- Component 2: Hidden Fault Prediction and Mitigation results
CREATE TABLE IF NOT EXISTS fault_assessments (
  id            SERIAL PRIMARY KEY,
  vehicle_id    INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  session_id    INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  source        TEXT NOT NULL CHECK (source IN ('iot', 'manual')),
  status        TEXT NOT NULL,     -- 'Normal' | 'Fault detected'
  primary_fault TEXT NOT NULL,
  severity      TEXT NOT NULL,     -- 'None' | 'Low' | 'Medium' | 'High'
  features      JSONB NOT NULL,    -- inputs sent to the component
  result        JSONB NOT NULL,    -- issues, mitigation plan, model outputs
  latency_ms    INTEGER,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fault_assessments_vehicle_created ON fault_assessments (vehicle_id, created_at DESC);
