-- Component 3: component-wise assessments (proposal section 4, "Component-wise Deterioration Assessment").
-- deterioration_assessments is now one row per assessment run (the summary):
--   component / component_state = the worst component, observed_score = average over components,
--   deviation = worst deviation, status = overall status.
-- deterioration_components holds one row per inspected component.

ALTER TABLE deterioration_assessments
  ADD COLUMN IF NOT EXISTS km_per_year REAL,
  ADD COLUMN IF NOT EXISTS warnings    JSONB NOT NULL DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS obd         JSONB,   -- OBD-II reading used + anomaly result
  ADD COLUMN IF NOT EXISTS obd_source  TEXT;    -- 'request' | 'session' | NULL

CREATE TABLE IF NOT EXISTS deterioration_components (
  id              SERIAL PRIMARY KEY,
  assessment_id   INTEGER NOT NULL REFERENCES deterioration_assessments(id) ON DELETE CASCADE,
  component       TEXT NOT NULL,
  component_state TEXT NOT NULL CHECK (component_state IN ('Good', 'Fair', 'Poor', 'Critical')),
  expected_score  REAL NOT NULL,
  observed_score  REAL NOT NULL,
  deviation       REAL NOT NULL,
  status          TEXT NOT NULL,
  reasons         JSONB NOT NULL DEFAULT '[]',
  advice          TEXT
);
CREATE INDEX IF NOT EXISTS deterioration_components_assessment ON deterioration_components (assessment_id);

-- 003 runs before this file, so cover the new table here (see 003 for why)
ALTER TABLE deterioration_components ENABLE ROW LEVEL SECURITY;
