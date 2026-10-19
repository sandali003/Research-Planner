import type {
  AssessmentListItem, AssessmentResult, AssessmentRow, LatestReadings, User, Vehicle,
} from './types';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3000/api/v1';
const TOKEN_KEY = 'autosense_token';

export const tokenStore = {
  get: () => (typeof window === 'undefined' ? null : window.localStorage.getItem(TOKEN_KEY)),
  set: (t: string) => window.localStorage.setItem(TOKEN_KEY, t),
  clear: () => window.localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running?');
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) tokenStore.clear();
    throw new ApiError(res.status, body?.error ?? `Request failed (${res.status})`, body?.details);
  }
  return body as T;
}

const post = <T>(path: string, data?: unknown) =>
  request<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) });

export const api = {
  login: (email: string, password: string) => post<{ user: User; token: string }>('/auth/login', { email, password }),
  register: (email: string, password: string) => post<{ user: User; token: string }>('/auth/register', { email, password }),

  vehicles: () => request<Vehicle[]>('/vehicles'),
  createVehicle: (v: Partial<Omit<Vehicle, 'id'>>) => post<Vehicle>('/vehicles', v),
  createDevice: (vehicleId: number, name: string) =>
    post<{ id: number; name: string; api_key: string }>(`/vehicles/${vehicleId}/devices`, { name }),

  startSession: (vehicleId: number, condition: 'idle' | 'driving') =>
    post<{ id: number }>('/sessions', { vehicle_id: vehicleId, condition }),
  stopSession: (sessionId: number) => post<{ id: number }>(`/sessions/${sessionId}/stop`),

  latestReadings: (vehicleId: number, limit = 60) =>
    request<LatestReadings>(`/vehicles/${vehicleId}/readings/latest?limit=${limit}`),
  assess: (vehicleId: number, windowSeconds: number) =>
    post<AssessmentResult & { id: number }>(`/vehicles/${vehicleId}/assessments`, { window_seconds: windowSeconds }),
  latestAssessment: (vehicleId: number) => request<AssessmentRow | null>(`/vehicles/${vehicleId}/assessments/latest`),
  assessments: (vehicleId: number) => request<AssessmentListItem[]>(`/vehicles/${vehicleId}/assessments`),
};
