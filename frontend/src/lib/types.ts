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
  id: number; overall_score: number; condition: AssessmentResult['condition'];
  latency_ms: number | null; created_at: string;
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
