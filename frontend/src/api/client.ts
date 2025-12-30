import axios from "axios";

// We rely on VITE_API_URL for the backend API location. If it's missing, fall
// back to the same-origin /api path (useful when an nginx proxy is in front).
const envBase = (import.meta as any).env?.VITE_API_URL as string | undefined;
const fallbackBase =
  typeof window !== "undefined" ? `${window.location.origin}/api` : "/api";
const sanitizedBase = (envBase || fallbackBase).replace(/\/$/, "");
if (!envBase && typeof window !== "undefined") {
  // Make it obvious in the console if we had to use the fallback.
  console.warn("VITE_API_URL not set; falling back to", sanitizedBase);
}
const api = axios.create({ baseURL: sanitizedBase });

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

export interface ConfigPayload {
  clinic: { name: string; timezone: string };
  schedule: { start: string; weeks: number; bleach_frequency?: string };
  ratios: { patients_per_tech: number; patients_per_rn: number; techs_per_rn: number };
  constraints: Record<string, boolean>;
  bleach: { day: string; rotation: string[]; cursor: number; frequency?: string };
  tournament: { trials: number; last_seed: number };
  export_roles?: string[];
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
  invite_token?: string | null;
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
    bleach_frequency?: string;
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

export interface SavedRequirement {
  day_name: string;
  patient_count: number;
  tech_openers: number;
  tech_mids: number;
  tech_closers: number;
  rn_count: number;
  admin_count: number;
}

export interface SavedAssignment {
  date: string;
  day_name: string;
  role: string;
  duty: string;
  staff_id: string | null;
  notes: string[];
  slot_index: number;
  is_bleach: boolean;
}

export interface SavedSchedule {
  clinic_name?: string;
  timezone?: string;
  start_date: string;
  weeks: number;
  bleach_frequency?: string;
  requirements: SavedRequirement[];
  assignments: SavedAssignment[];
  staff?: Array<{ id: string; name: string; role: string }>;
  stats?: Record<string, number>;
  total_penalty?: number;
  winning_seed?: number | null;
  bleach_cursor?: number;
  export_roles?: string[];
  tournament_trials?: number;
  generated_at?: string;
}

export const fetchHealth = async (): Promise<HealthResponse> => {
  const { data } = await api.get<HealthResponse>("health");
  return data;
};

export const listConfigs = async (): Promise<string[]> => {
  const { data } = await api.get<string[]>("configs");
  return data;
};

export const loadConfig = async (filename: string): Promise<ConfigPayload> => {
  const { data } = await api.get<ConfigPayload>(`configs/${filename}`);
  return data;
};

export const saveConfig = async (req: SaveConfigRequest): Promise<{ status: string; filename: string }> => {
  const { data } = await api.post("configs/save", req);
  return data;
};

export const runSchedule = async (req: ScheduleRequest): Promise<ScheduleResponse> => {
  const { data } = await api.post<ScheduleResponse>("schedule/run", req);
  return data;
};

export const fetchLatestSchedule = async (): Promise<SavedSchedule> => {
  const { data } = await api.get<SavedSchedule>(`schedule/latest?ts=${Date.now()}`);
  return data;
};

export const exportConfig = async (filename: string) => {
  const { data } = await api.get<{ filename: string; payload: any; encoded: string }>(`configs/export/${filename}`);
  return data;
};

export const importConfig = async (req: SaveConfigRequest & { encoded?: string }) => {
  // allow encoded payload or full payload
  if (req.encoded) {
    const decoded = JSON.parse(atob(req.encoded));
    return api.post("configs/import", { payload: decoded, filename: req.filename || "" });
  }
  return api.post("configs/import", req);
};

export const importScheduleCsv = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<{ status: string; assignments: number }>("schedule/import/csv", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
};
export const exportScheduleCsv = async () => {
  const { data } = await api.get<Blob>("schedule/export/csv", { responseType: "blob" });
  return data;
};

export default api;

export const login = async (username: string, password: string): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>("auth/login", { username, password });
  return data;
};

export const setupUser = async (
  invite_token: string,
  username: string = "",
  password: string = ""
): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>("auth/setup", { invite_token, username, password });
  return data;
};

export const createInvite = async (req: InviteRequest): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>("auth/invite", req);
  return data;
};

export const listUsers = async (): Promise<UserSummary[]> => {
  const { data } = await api.get<UserSummary[]>("auth/users");
  return data;
};

export const deleteUser = async (userId: number): Promise<{ status: string; id: number }> => {
  const { data } = await api.delete<{ status: string; id: number }>(`auth/users/${userId}`);
  return data;
};

export const revokeInvite = async (req: InviteRequest): Promise<{ status: string; username: string }> => {
  const { data } = await api.post<{ status: string; username: string }>("auth/invite/revoke", req);
  return data;
};

export const listAudit = async (limit = 50): Promise<AuditEntry[]> => {
  const { data } = await api.get<AuditEntry[]>(`auth/audit?limit=${limit}`);
  return data;
};

export const updateUserRole = async (userId: number, role: string): Promise<{ status: string; id: number; role: string }> => {
  const { data } = await api.post<{ status: string; id: number; role: string }>(`auth/users/${userId}/role`, { role });
  return data;
};

export const resetUserInvite = async (userId: number): Promise<{ token: string }> => {
  const { data } = await api.post<{ token: string }>(`auth/users/${userId}/reset`);
  return data;
};
