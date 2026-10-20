-- Component 3, step 3: real-data contextual assessment (UK MOT baseline).
-- The whole result from the Component 3 API is kept as JSON: overall and per-component
-- percentile, condition-equivalent (effective) age, age gap, status, grade distribution,
-- the condition-by-age curve for the chart, and notes. NULL for older assessments and for
-- vehicle models without a real-data baseline.
ALTER TABLE deterioration_assessments
  ADD COLUMN IF NOT EXISTS contextual    JSONB,
  ADD COLUMN IF NOT EXISTS legacy_status TEXT,     -- status of the inspection-data model
  ADD COLUMN IF NOT EXISTS fuel_type     TEXT,
  ADD COLUMN IF NOT EXISTS engine_cc     REAL;
