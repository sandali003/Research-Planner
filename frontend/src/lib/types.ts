export interface User { id: number; email: string; role: string }

export interface Vehicle {
  id: number; vin: string | null; make: string | null; model: string | null; year: number | null;
}

export interface Factor {
  component: string; label: string; score: number; impact: number; reason: string;
  status: 'Normal' | 'Watch' | 'Abnormal';
}

export interface AssessmentResult {
  overall: number;
  condition: 'Good' | 'Fair' | 'Poor' | 'Critical';
  base: number;
  potential: number;
  components: Record<string, number>;
  factors: Factor[];
  explanation: string;
  model_version?: string;
}

export interface AssessmentRow {
  id: number; vehicle_id: number; session_id: number | null;
  overall_score: number; condition: AssessmentResult['condition'];
  features: Record<string, number | string | null>;
  result: AssessmentResult;
  model_version: string | null; latency_ms: number | null; created_at: string;
}

export interface AssessmentListItem {
  id: number; session_id: number | null; overall_score: number; condition: AssessmentResult['condition'];
  latency_ms: number | null; created_at: string;
}

/** Readings typed in by hand for a health assessment. */
export interface ManualAssessmentInputs {
  ds18b20_temp_c: number; battery_voltage_v: number; vibration_rms_g: number; vibration_peak_g: number;
  engine_rpm?: number; engine_load_pct?: number; dtc_codes?: string[];
}

export interface SensorRow {
  ts: string; accel_x: number | null; accel_y: number | null; accel_z: number | null;
  temp_c: number | null; voltage_v: number | null;
}

export interface ObdRow {
  ts: string; rpm: number | null; engine_load: number | null; coolant_temp: number | null;
  intake_temp: number | null; speed: number | null; dtc_codes: string[];
}

export interface LatestReadings {
  session: { id: number; condition: string; started_at: string; ended_at: string | null } | null;
  sensor: SensorRow[];
  obd: ObdRow[];
}

// ---- Component 2: Hidden Fault Prediction and Mitigation ----
export type Severity = 'None' | 'Low' | 'Medium' | 'High';

export interface FaultIssue {
  fault: string;
  display_name: string;
  sources: string[];
  confidence: number | null;
  severity: Severity;
  timeframe: string;
  message: string;
  reasons: string[];
  immediate_actions: string[];
  longevity_tips: string[];
  notes: string[];
  targeted_actions?: string[];
  key_factors?: ShapFactor[];
}

export interface ShapFactor { feature: string; label: string; value: number; impact: number }

export interface ShapExplanation { method: string; target: string; base_value: number; factors: ShapFactor[] }

export interface FaultInputs {
  engine_rpm?: number | null;
  engine_load_pct?: number | null;
  coolant_temp_c?: number | null;
  engine_temp_c?: number | null;
  ds18b20_temp_c?: number | null;
  battery_voltage_v?: number | null;
  vibration_x_g?: number | null;
  vibration_y_g?: number | null;
  vibration_z_g?: number | null;
  vibration_magnitude_g?: number | null;
  vehicle_model?: string | null;
  dtc_codes?: string[];
}

export interface FaultResult {
  status: 'Normal' | 'Fault detected';
  primary_fault: string;
  overall_severity: Severity;
  timeframe: string;
  issues: FaultIssue[];
  longevity_tips: string[];
  notes: string[];
  classifier: { prediction: string; confidence: number; probabilities: Record<string, number> } | null;
  anomaly: { score: number; threshold: number; is_anomaly: boolean } | null;
  rule_findings: { fault: string; severity: string; reason: string }[];
  explanations?: { classifier: ShapExplanation | null; anomaly: ShapExplanation | null };
  reasoning?: { rule: string; because: string }[];
  engine?: { name: string; rules_fired: number };
  models_used: string[];
  inputs: FaultInputs;
  latency_ms: number;
}

/** Response of a new check (result fields at the top level). */
export interface FaultCheck extends FaultResult {
  id: number;
  source: 'iot' | 'manual';
  created_at: string;
  features: FaultInputs;
}

/** Stored row (result nested), from /hidden-faults/latest and /hidden-faults/:id. */
export interface FaultCheckRow {
  id: number; vehicle_id: number; session_id: number | null; source: 'iot' | 'manual';
  status: string; primary_fault: string; severity: Severity;
  features: FaultInputs; result: FaultResult; latency_ms: number | null; created_at: string;
}

export interface FaultCheckListItem {
  id: number; source: 'iot' | 'manual'; status: string; primary_fault: string;
  severity: Severity; latency_ms: number | null; created_at: string;
}

// ---- Component 3: Age- and Mileage-Adjusted Deterioration ----
export type DeteriorationStatus = 'Normal' | 'Slightly high' | 'High';
export type ComponentState = 'Good' | 'Fair' | 'Poor' | 'Critical';

export interface ComponentCheck { component: string; component_state: ComponentState }

export interface ObdReading { engine_rpm: number; engine_load: number; coolant_temp: number }

export interface DeteriorationInput {
  odometer_km: number;
  components: ComponentCheck[];
  age_years?: number;
  vehicle_model?: string;
  obd?: ObdReading;
}

export interface DeteriorationComponent extends ComponentCheck {
  expected_score: number;
  observed_score: number;
  deviation: number;
  status: DeteriorationStatus;
  reasons: string[];
  advice: string | null;
}

export interface DeteriorationAssessment {
  id: number;
  vehicle_id: number;
  created_at: string;
  status: DeteriorationStatus;
  vehicle_model: string;
  age_years: number;
  odometer_km: number;
  km_per_year: number | null;
  component: string;            // worst component
  component_state: ComponentState;
  expected_score: number;
  observed_score: number;       // average over components
  deviation: number;            // worst deviation
  warnings: string[];
  obd: (Partial<{ reading: ObdReading; anomaly: boolean; anomaly_score: number }>) | null;
  obd_source: 'request' | 'session' | null;
  model_version: string | null;
  latency_ms: number | null;
  components: DeteriorationComponent[];
}

export interface DeteriorationListItem {
  id: number; created_at: string; status: DeteriorationStatus; vehicle_model: string;
  age_years: number; odometer_km: number; km_per_year: number | null;
  expected_score: number; observed_score: number; deviation: number;
  worst_component: string; obd_source: 'request' | 'session' | null;
}

export interface DeteriorationContext {
  curve: { age_years: number; expected: number }[];
  trained_range: { age_years: [number, number]; odometer_km: [number, number] };
  typical_km_per_year: number;
  points: { age_years: number; odometer_km: number; inspection_score: number; status: DeteriorationStatus }[];
}
