import { ConfigPayload, ScheduleRequest } from "../api/client";
import { DAYS } from "../constants";
import { DemandRow, PTORow, StaffRow } from "../types";
import { coercePrefWeight, genId, parseLocalYmd, toLocalYmd } from "./planner";

type PlannerConfigArgs = {
  configName: string;
  timezone: string;
  startDate: string;
  weeks: number;
  bleachFrequency: string;
  patientsPerTech: number;
  patientsPerRn: number;
  techsPerRn: number;
  threeDayWeight: number;
  postBleachWeight: number;
  altSatWeight: number;
  techFourWeight: number;
  rnFourWeight: number;
  bleachDay: string;
  bleachRotation: string[];
  bleachCursor: number;
  trials: number;
  exportRoles: string[];
  staffRows: StaffRow[];
  demandRows: DemandRow[];
  ptoRows: PTORow[];
};

type ScheduleRequestArgs = PlannerConfigArgs & {
  selectedSeed: number | null;
};

const defaultAvailability = () =>
  DAYS.reduce<Record<string, boolean>>((acc, day) => {
    acc[day] = true;
    return acc;
  }, {});

export const fallbackStaffRow = (): StaffRow => ({
  id: genId(),
  name: "",
  role: "Tech",
  can_bleach: false,
  can_open: false,
  can_close: false,
  availability: defaultAvailability(),
  pref_open_mwf: 5,
  pref_open_tts: 5,
  pref_mid_mwf: 5,
  pref_mid_tts: 5,
  pref_close_mwf: 5,
  pref_close_tts: 5
});

export const normalizeStaffRows = (rows: ConfigPayload["staff"] | undefined): StaffRow[] => {
  if (!Array.isArray(rows)) return [];
  const normalized = rows.map((row: any) => ({
    id: String(row.id ?? genId()),
    name: String(row.name ?? ""),
    role: String(row.role ?? "Tech") || "Tech",
    can_bleach: Boolean(row.can_bleach ?? false),
    can_open: Boolean(row.can_open ?? false),
    can_close: Boolean(row.can_close ?? false),
    availability: DAYS.reduce<Record<string, boolean>>((acc, day) => {
      acc[day] = Boolean(row[day] ?? row?.availability?.[day] ?? true);
      return acc;
    }, {}),
    pref_open_mwf: coercePrefWeight(row.pref_open_mwf ?? row.open_mwf, 5),
    pref_open_tts: coercePrefWeight(row.pref_open_tts ?? row.open_tts, 5),
    pref_mid_mwf: coercePrefWeight(row.pref_mid_mwf ?? row.mid_mwf, 5),
    pref_mid_tts: coercePrefWeight(row.pref_mid_tts ?? row.mid_tts, 5),
    pref_close_mwf: coercePrefWeight(row.pref_close_mwf ?? row.close_mwf, 5),
    pref_close_tts: coercePrefWeight(row.pref_close_tts ?? row.close_tts, 5)
  }));
  return normalized.length ? normalized : [fallbackStaffRow()];
};

export const normalizeDemandRows = (rows: ConfigPayload["demand"] | undefined): DemandRow[] => {
  if (!Array.isArray(rows)) return [];
  return rows.map((row: any) => ({
    Day: String(row.Day ?? row.day ?? ""),
    Patients: Number(row.Patients ?? 0),
    Tech_Open: Number(row.Tech_Open ?? 0),
    Tech_Mid: Number(row.Tech_Mid ?? 0),
    Tech_Close: Number(row.Tech_Close ?? 0),
    RN_Count: Number(row.RN_Count ?? 0),
    Admin_Count: Number(row.Admin_Count ?? 0)
  }));
};

export const normalizePtoRows = (rows: ConfigPayload["pto"] | undefined): PTORow[] => {
  if (!Array.isArray(rows)) return [];
  return rows.map((row: any) => ({
    staff_id: String(row.staff_id ?? ""),
    start_date: String(row.start_date ?? row.date ?? ""),
    end_date: String(row.end_date ?? row.start_date ?? row.date ?? "")
  }));
};

export const buildConfigPayload = (args: PlannerConfigArgs): ConfigPayload => ({
  clinic: { name: args.configName || "Demo Clinic", timezone: args.timezone },
  schedule: { start: args.startDate || "", weeks: args.weeks, bleach_frequency: args.bleachFrequency },
  ratios: {
    patients_per_tech: args.patientsPerTech,
    patients_per_rn: args.patientsPerRn,
    techs_per_rn: args.techsPerRn
  },
  constraints: {
    enforce_three_day_cap: args.threeDayWeight,
    enforce_post_bleach_rest: args.postBleachWeight,
    enforce_alt_saturdays: args.altSatWeight,
    limit_tech_four_days: args.techFourWeight,
    limit_rn_four_days: args.rnFourWeight
  },
  bleach: {
    day: args.bleachDay,
    rotation: args.bleachRotation,
    cursor: args.bleachCursor,
    frequency: args.bleachFrequency
  },
  tournament: { trials: args.trials, last_seed: 0 },
  export_roles: args.exportRoles,
  staff: args.staffRows.map((staff) => ({
    ...staff,
    pref_open_mwf: coercePrefWeight(staff.pref_open_mwf, 5),
    pref_open_tts: coercePrefWeight(staff.pref_open_tts, 5),
    pref_mid_mwf: coercePrefWeight(staff.pref_mid_mwf, 5),
    pref_mid_tts: coercePrefWeight(staff.pref_mid_tts, 5),
    pref_close_mwf: coercePrefWeight(staff.pref_close_mwf, 5),
    pref_close_tts: coercePrefWeight(staff.pref_close_tts, 5)
  })),
  demand: args.demandRows,
  pto: args.ptoRows
});

export const expandPtoRows = (rows: PTORow[]): Array<{ staff_id: string; date: string }> => {
  const entries: Array<{ staff_id: string; date: string }> = [];
  for (const row of rows) {
    if (!row.staff_id || !row.start_date) continue;
    const start = parseLocalYmd(row.start_date);
    const end = parseLocalYmd(row.end_date || row.start_date);
    if (!start || !end) continue;
    const [first, last] = start <= end ? [start, end] : [end, start];
    for (let dt = new Date(first); dt <= last; dt.setDate(dt.getDate() + 1)) {
      entries.push({ staff_id: row.staff_id, date: toLocalYmd(dt) });
    }
  }
  return entries;
};

export const buildScheduleRequest = (args: ScheduleRequestArgs): ScheduleRequest => ({
  staff: args.staffRows.map((staff) => ({
    id: staff.id,
    name: staff.name,
    role: staff.role,
    can_open: staff.can_open ?? false,
    can_close: staff.can_close ?? false,
    can_bleach: staff.can_bleach ?? false,
    availability: DAYS.reduce<Record<string, boolean>>((acc, day) => {
      acc[day] = staff.availability?.[day] ?? true;
      return acc;
    }, {}),
    preferences: {
      open_mwf: coercePrefWeight(staff.pref_open_mwf, 5),
      open_tts: coercePrefWeight(staff.pref_open_tts, 5),
      mid_mwf: coercePrefWeight(staff.pref_mid_mwf, 5),
      mid_tts: coercePrefWeight(staff.pref_mid_tts, 5),
      close_mwf: coercePrefWeight(staff.pref_close_mwf, 5),
      close_tts: coercePrefWeight(staff.pref_close_tts, 5)
    }
  })),
  requirements: args.demandRows.map((row) => ({
    day_name: row.Day,
    patient_count: row.Patients,
    tech_openers: row.Tech_Open,
    tech_mids: row.Tech_Mid,
    tech_closers: row.Tech_Close,
    rn_count: row.RN_Count,
    admin_count: row.Admin_Count
  })),
  config: {
    clinic_name: args.configName || "Demo Clinic",
    timezone: args.timezone,
    start_date: args.startDate,
    weeks: args.weeks,
    bleach_day: args.bleachDay,
    bleach_rotation: args.bleachRotation,
    bleach_cursor: args.bleachCursor,
    bleach_frequency: args.bleachFrequency,
    patients_per_tech: args.patientsPerTech,
    patients_per_rn: args.patientsPerRn,
    techs_per_rn: args.techsPerRn,
    toggles: {
      enforce_three_day_cap: args.threeDayWeight,
      enforce_post_bleach_rest: args.postBleachWeight,
      enforce_alt_saturdays: args.altSatWeight,
      limit_tech_four_days: args.techFourWeight,
      limit_rn_four_days: args.rnFourWeight
    }
  },
  pto: expandPtoRows(args.ptoRows),
  tournament_trials: args.trials,
  base_seed: args.selectedSeed,
  export_roles: args.exportRoles
});
