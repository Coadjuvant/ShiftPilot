import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api"
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
