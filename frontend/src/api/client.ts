import axios from "axios";

const api = axios.create({
  baseURL: (import.meta as any).env?.VITE_API_URL ?? "/api"
});

// Optional API key header (set VITE_API_KEY in your frontend env)
const apiKey = (import.meta as any).env?.VITE_API_KEY;
if (apiKey) {
  api.defaults.headers.common["x-api-key"] = apiKey;
}

export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
};

// Apply token from localStorage on load (browser only)
if (typeof window !== "undefined") {
  const stored = window.localStorage.getItem("auth_token");
  if (stored) {
    setAuthToken(stored);
  }
}

// Always attach the latest token from localStorage on each request so we
// don't rely solely on the default header state.
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem("auth_token");
    if (stored) {
      config.headers = config.headers ?? {};
      config.headers["Authorization"] = `Bearer ${stored}`;
    }
  }
  return config;
});

export interface HealthResponse {
  status: string;
}

export interface ConfigSummary {
  name: string;
}

export interface ConfigPayload {
  clinic: { name: string; timezone: string };
  schedule: { start: string; weeks: number };
  ratios: { patients_per_tech: number; patients_per_rn: number; techs_per_rn: number };
  constraints: Record<string, boolean>;
  bleach: { day: string; rotation: string[]; cursor: number };
  tournament: { trials: number; last_seed: number };
  staff: Array<Record<string, unknown>>;
  demand: Array<Record<string, unknown>>;
  pto: Array<Record<string, unknown>>;
}

export interface SaveConfigRequest {
  payload: ConfigPayload;
  filename?: string;
}

export interface InviteRequest {
  username: string;
  license_key: string;
  role?: string;
}

export interface UserSummary {
  id: number;
  public_id?: string;
  username: string;
  status: string;
  role: string;
  license_key?: string;
  created_at?: string;
  last_login?: string;
  invite_expires_at?: string;
  invite_created_by?: number | null;
  last_invite_token?: string | null;
}

export interface AuditEntry {
  id: number;
  user_id: number | null;
  event: string;
  detail: string;
  ip: string;
  user_agent: string;
  created_at: string;
}

export interface ScheduleRequest {
  staff: Array<Record<string, unknown>>;
  requirements: Array<Record<string, unknown>>;
  config: {
    clinic_name: string;
    timezone: string;
    start_date: string;
    weeks: number;
    bleach_day: string;
    bleach_rotation: string[];
    bleach_cursor: number;
    patients_per_tech: number;
    patients_per_rn: number;
    techs_per_rn: number;
    toggles: Record<string, boolean>;
  };
  pto: Array<Record<string, unknown>>;
  tournament_trials: number;
  base_seed?: number | null;
  export_roles?: string[];
}

export interface ScheduleResponse {
  bleach_cursor: number;
  winning_seed: number | null;
  assignments: Array<{
    date: string;
    day_name: string;
    role: string;
    duty: string;
    staff_id: string | null;
    notes: string[];
    slot_index: number;
    is_bleach: boolean;
  }>;
  total_penalty: number;
  stats: Record<string, number>;
  excel?: string;
}

export const fetchHealth = async (): Promise<HealthResponse> => {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
};

export const listConfigs = async (): Promise<string[]> => {
  const { data } = await api.get<string[]>("/configs");
  return data;
};

export const loadConfig = async (filename: string): Promise<ConfigPayload> => {
  const { data } = await api.get<ConfigPayload>(`/configs/${filename}`);
  return data;
};

export const saveConfig = async (req: SaveConfigRequest): Promise<{ status: string; filename: string }> => {
  const { data } = await api.post("/configs/save", req);
  return data;
};

export const runSchedule = async (req: ScheduleRequest): Promise<ScheduleResponse> => {
  const { data } = await api.post<ScheduleResponse>("/schedule/run", req);
  return data;
};

export default api;

export const login = async (username: string, password: string): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>("/auth/login", { username, password });
  return data;
};

export const setupUser = async (invite_token: string, password: string): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>("/auth/setup", { invite_token, password });
  return data;
};

export const createInvite = async (req: InviteRequest): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>("/auth/invite", req);
  return data;
};

export const listUsers = async (): Promise<UserSummary[]> => {
  const { data } = await api.get<UserSummary[]>("/auth/users");
  return data;
};

export const deleteUser = async (userId: number): Promise<{ status: string; id: number }> => {
  const { data } = await api.delete<{ status: string; id: number }>(`/auth/users/${userId}`);
  return data;
};

export const revokeInvite = async (req: InviteRequest): Promise<{ status: string; username: string }> => {
  const { data } = await api.post<{ status: string; username: string }>("/auth/invite/revoke", req);
  return data;
};

export const listAudit = async (limit = 50): Promise<AuditEntry[]> => {
  const { data } = await api.get<AuditEntry[]>(`/auth/audit?limit=${limit}`);
  return data;
};

export const updateUserRole = async (userId: number, role: string): Promise<{ status: string; id: number; role: string }> => {
  const { data } = await api.post<{ status: string; id: number; role: string }>(`/auth/users/${userId}/role`, { role });
  return data;
};

export const resetUserInvite = async (userId: number): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>(`/auth/users/${userId}/reset`);
  return data;
};
