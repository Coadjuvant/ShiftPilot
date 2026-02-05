import { useEffect, useRef, useState } from "react";
import api, {
  ConfigPayload,
  SaveConfigRequest,
  SavedSchedule,
  deleteConfig,
  exportScheduleCsv,
  exportScheduleExcel,
  fetchHealth,
  fetchLatestSchedule,
  getStoredToken,
  listConfigs,
  loadConfig,
  login,
  runSchedule,
  saveConfig,
  setAuthToken,
  setupUser
} from "../api/client";
import StaffEditor from "../components/StaffEditor";
import AvailabilityEditor from "../components/AvailabilityEditor";
import PrefsEditor from "../components/PrefsEditor";
import DemandEditor from "../components/DemandEditor";
import PTOEditor from "../components/PTOEditor";
import BleachEditor, { BleachState } from "../components/BleachEditor";
import RunPanel, { RunConfig } from "../components/RunPanel";
import AdminPanel from "../components/AdminPanel";
import { DemandRow, PTORow, StaffRow } from "../types";
import { DAYS } from "../constants";

type UserInfo = {
  sub: string;
  username: string;
  role: string;
};

export default function StaffPlanner() {
  const genId = () => {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    return Math.random().toString(36).slice(2, 10);
  };

  const friendlyError = (err: any, fallback: string) => {
    const status = err?.response?.status;
    if (status === 401) return "Invalid username or password";
    if (status === 422) return "Validation failed. Please check your inputs.";
    if (status === 409 && err?.response?.data?.detail) return String(err.response.data.detail);
    if (status === 409) return "Conflict: value already in use.";
    return err?.message ?? fallback;
  };
  const formatDateTime = (value?: string | null) => {
    if (!value) return "";
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return dt.toLocaleString(undefined, {
      year: "2-digit",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  };
  const formatDateYmd = (value: string) => {
    const parts = value.split("-").map(Number);
    if (parts.length >= 3 && parts.every((n) => Number.isFinite(n))) {
      return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])).toISOString().slice(0, 10);
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toISOString().slice(0, 10);
  };
  const coerceConstraintWeight = (value: unknown, fallback = 10) => {
    if (typeof value === "boolean") return value ? 10 : 0;
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.min(10, Math.max(0, parsed));
  };
  const buildScheduleFilename = (meta: SavedSchedule | null, ext: "xlsx" | "csv") => {
    const base = (meta?.clinic_name || configName || "schedule").trim().replace(/\s+/g, "-").toLowerCase();
    if (!meta?.start_date || typeof meta.weeks !== "number") {
      return `${base || "schedule"}.${ext}`;
    }
    const start = formatDateYmd(meta.start_date);
    const startDt = new Date(`${start}T00:00:00Z`);
    const endDt = new Date(startDt);
    endDt.setUTCDate(endDt.getUTCDate() + meta.weeks * 7 - 2);
    const end = endDt.toISOString().slice(0, 10);
    return `${base || "schedule"}-${start}_to_${end}.${ext}`;
  };
  const downloadSavedSchedule = async () => {
    try {
      const meta = await fetchLatestSchedule();
      if ((meta as any)?.status === "none" || !meta?.assignments?.length) {
        setStatus("No saved schedule to download.");
        return;
      }
      const blob = await exportScheduleExcel();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = buildScheduleFilename(meta, "xlsx");
      link.click();
      URL.revokeObjectURL(url);
      setStatus("Download started.");
    } catch (err: any) {
      const st = err?.response?.status;
      setStatus(st === 404 ? "No saved schedule to download." : friendlyError(err, "Download failed."));
    }
  };
  const downloadSavedScheduleCsv = async () => {
    try {
      const meta = await fetchLatestSchedule();
      if ((meta as any)?.status === "none" || !meta?.assignments?.length) {
        setStatus("No saved schedule to download.");
        return;
      }
      const blob = await exportScheduleCsv();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = buildScheduleFilename(meta, "csv");
      link.click();
      URL.revokeObjectURL(url);
      setStatus("CSV download started.");
    } catch (err: any) {
      const st = err?.response?.status;
      setStatus(st === 404 ? "No saved schedule to download." : friendlyError(err, "Download failed."));
    }
  };
  const loadLatestSavedSchedule = async () => {
    try {
      const data = await fetchLatestSchedule();
      if ((data as any)?.status === "none" || !data?.assignments?.length) {
        setStatus("No saved schedule found.");
        return;
      }
      setAssignments(data.assignments);
      setStats(data.stats || {});
      if (Array.isArray(data.export_roles) && data.export_roles.length) {
        setExportRoles(data.export_roles);
      }
      if (Array.isArray(data.staff) && data.staff.length) {
        const map = data.staff.reduce<Record<string, string>>((acc, staff) => {
          if (staff.id) acc[staff.id] = staff.name || staff.id;
          return acc;
        }, {});
        setScheduleStaffMap(map);
      } else {
        setScheduleStaffMap(null);
      }
      if (data.generated_at) {
        setRunResult(`Loaded saved schedule (Generated ${formatDateTime(data.generated_at)})`);
      } else {
        setRunResult("Loaded saved schedule.");
      }
      setStatus("Loaded latest saved schedule.");
    } catch (err: any) {
      setStatus(friendlyError(err, "Failed to load latest schedule."));
    }
  };

  const [status, setStatus] = useState<string>("Checking API...");
  const [activeTab, setActiveTab] = useState<"staff" | "avail" | "prefs" | "demand" | "pto" | "run" | "bleach" | "admin">("staff");
  const defaultAvailability = DAYS.reduce<Record<string, boolean>>((acc, day) => {
    acc[day] = true;
    return acc;
  }, {});
  const [staffRows, setStaffRows] = useState<StaffRow[]>([
    {
      id: genId(),
      name: "",
      role: "Tech",
      can_bleach: false,
      can_open: false,
      can_close: false,
      availability: { ...defaultAvailability },
      pref_open_mwf: 5,
      pref_open_tts: 5,
      pref_mid_mwf: 5,
      pref_mid_tts: 5,
      pref_close_mwf: 5,
      pref_close_tts: 5
    }
  ]);
  const [demandRows, setDemandRows] = useState<DemandRow[]>(
    DAYS.map((day) => ({
      Day: day,
      Patients: 0,
      Tech_Open: 0,
      Tech_Mid: 0,
      Tech_Close: 0,
      RN_Count: 0,
      Admin_Count: 0
    }))
  );
  const [ptoRows, setPtoRows] = useState<PTORow[]>([]);
  const [configs, setConfigs] = useState<string[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<string>("");
  const [configName, setConfigName] = useState<string>("Demo Clinic");
  const [timezone, setTimezone] = useState<string>("UTC");
  const [runResult, setRunResult] = useState<string>("");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [assignments, setAssignments] = useState<
    Array<{
      date: string;
      day_name: string;
      role: string;
      duty: string;
      staff_id: string | null;
      notes: string[];
      slot_index: number;
      is_bleach: boolean;
    }>
  >([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [excelUrl, setExcelUrl] = useState<string | null>(null);
  const [winningSeed, setWinningSeed] = useState<number | null>(null);
  const [winningScore, setWinningScore] = useState<number | null>(null);
  const [authToken, setAuthTokenState] = useState<string | null>(() => {
    return getStoredToken();
  });
  const [loginMode, setLoginMode] = useState<"login" | "setup">("login");
  const [loginUser, setLoginUser] = useState<string>("");
  const [loginPass, setLoginPass] = useState<string>("");
  const [inviteToken, setInviteToken] = useState<string>("");
  const [loginError, setLoginError] = useState<string>("");
  const [startDate, setStartDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [weeks, setWeeks] = useState<number>(1);
  const [patientsPerTech, setPatientsPerTech] = useState<number>(4);
  const [patientsPerRn, setPatientsPerRn] = useState<number>(12);
  const [techsPerRn, setTechsPerRn] = useState<number>(4);
  const [baseSeed, setBaseSeed] = useState<number>(0);
  const [usePrevSeed, setUsePrevSeed] = useState<boolean>(false);
  const [bleachDay, setBleachDay] = useState<string>("Thu");
  const [bleachCursor, setBleachCursor] = useState<number>(0);
  const [bleachRotation, setBleachRotation] = useState<string[]>([]);
  const [bleachFrequency, setBleachFrequency] = useState<string>("weekly");
  const [trials, setTrials] = useState<number>(20);
  const [exportRoles, setExportRoles] = useState<string[]>(["Tech", "RN", "Admin"]);
  const [threeDayWeight, setThreeDayWeight] = useState<number>(10);
  const [postBleachWeight, setPostBleachWeight] = useState<number>(10);
  const [altSatWeight, setAltSatWeight] = useState<number>(10);
  const [techFourWeight, setTechFourWeight] = useState<number>(10);
  const [rnFourWeight, setRnFourWeight] = useState<number>(10);
  const [lastError, setLastError] = useState<string>("");
  const [scheduleStaffMap, setScheduleStaffMap] = useState<Record<string, string> | null>(null);
  const [latestScheduleMeta, setLatestScheduleMeta] = useState<SavedSchedule | null>(null);
  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [autoLoadedConfig, setAutoLoadedConfig] = useState<boolean>(false);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const isAuthed = Boolean(authToken && authToken.length > 0);

  // --- Computed values ---
  const staffNameMap = staffRows.reduce<Record<string, string>>((acc, row) => {
    if (row.id) acc[row.id] = row.name?.trim() ? row.name : "(no name set)";
    return acc;
  }, {});
  const displayStaffMap = {
    ...staffNameMap,
    ...(scheduleStaffMap || {})
  };
  const uniqueStaffIds = Array.from(
    new Set(staffRows.filter((s) => s.can_bleach).map((s) => s.id).filter((v) => v && v.trim().length > 0))
  );
  const availableBleachIds = uniqueStaffIds.filter((sid) => !bleachRotation.includes(sid));
  const scheduleEnd = (() => {
    const start = startDate ? new Date(startDate) : null;
    if (!start || Number.isNaN(start.getTime())) return "";
    const end = new Date(start);
    end.setDate(end.getDate() + weeks * 7 - 1);
    return end.toISOString().slice(0, 10);
  })();

  const formatGeneratedAt = (value?: string) => {
    if (!value) return "";
    const hasTimeZone = /([zZ]|[+-]\d{2}:\d{2})$/.test(value);
    const date = new Date(hasTimeZone ? value : `${value}Z`);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  };

  const refreshLatestMeta = async () => {
    try {
      const meta = await fetchLatestSchedule();
      if ((meta as any)?.status === "none") {
        setLatestScheduleMeta(null);
        return;
      }
      setLatestScheduleMeta(meta);
    } catch {
      setLatestScheduleMeta(null);
    }
  };

  const resetWorkspaceState = (message?: string) => {
    setStaffRows([
      {
        id: genId(),
        name: "",
        role: "Tech",
        can_bleach: false,
        can_open: false,
        can_close: false,
        availability: { ...defaultAvailability },
        pref_open_mwf: 5,
        pref_open_tts: 5,
        pref_mid_mwf: 5,
        pref_mid_tts: 5,
        pref_close_mwf: 5,
        pref_close_tts: 5
      }
    ]);
    setDemandRows(
      DAYS.map((day) => ({
        Day: day,
        Patients: 0,
        Tech_Open: 0,
        Tech_Mid: 0,
        Tech_Close: 0,
        RN_Count: 0,
        Admin_Count: 0
      }))
    );
    setPtoRows([]);
    setConfigName("Demo Clinic");
    setTimezone("UTC");
    setStartDate(new Date().toISOString().slice(0, 10));
    setWeeks(1);
    setPatientsPerTech(4);
    setPatientsPerRn(12);
    setTechsPerRn(4);
    setBleachDay("Thu");
    setBleachCursor(0);
    setBleachRotation([]);
    setBleachFrequency("weekly");
    setScheduleStaffMap(null);
    setTrials(20);
    setExportRoles(["Tech", "RN", "Admin"]);
    setThreeDayWeight(10);
    setPostBleachWeight(10);
    setAltSatWeight(10);
    setTechFourWeight(10);
    setRnFourWeight(10);
    setBaseSeed(0);
    setUsePrevSeed(false);
    setAssignments([]);
    setStats({});
    setRunResult("");
    setExcelUrl(null);
    setWinningSeed(null);
    setWinningScore(null);
    setProgress(0);
    setSelectedConfig("");
    setConfigs([]);
    setAutoLoadedConfig(false);
    setLastError("");
    setLoginUser("");
    setLoginPass("");
    setInviteToken("");
    if (message) setStatus(message);
    localStorage.removeItem("last_config");
  };

  // --- Validation ---
  const staffWarnings: string[] = [];
  staffRows.forEach((row, idx) => {
    if (!row.id?.trim()) {
      staffWarnings.push(`Row ${idx + 1} is missing ID`);
    }
    if (!row.role?.trim()) {
      staffWarnings.push(`Row ${idx + 1} is missing role`);
    }
  });
  const demandWarnings: string[] = demandRows
    .map((row) => {
      if (!row.Day) return "Demand row missing day";
      const numericKeys: (keyof DemandRow)[] = ["Patients", "Tech_Open", "Tech_Mid", "Tech_Close", "RN_Count", "Admin_Count"];
      for (const key of numericKeys) {
        const val = Number(row[key] ?? 0);
        if (Number.isNaN(val) || val < 0) return `Demand for ${row.Day} has invalid ${key}`;
      }
      return "";
    })
    .filter(Boolean);
  const ptoWarnings: string[] = ptoRows
    .map((row, idx) => {
      const who = staffNameMap[row.staff_id] || row.staff_id || `PTO row ${idx + 1}`;
      if (!row.staff_id) return `${who}: missing staff`;
      if (!row.start_date) return `${who}: missing start date`;
      const start = new Date(row.start_date);
      if (Number.isNaN(start.getTime())) return `${who}: invalid start date`;
      const endVal = row.end_date || row.start_date;
      const end = new Date(endVal);
      if (Number.isNaN(end.getTime())) return `${who}: invalid end date`;
      if (end < start) return `${who}: end before start`;
      if (scheduleEnd) {
        const schedStart = new Date(startDate);
        const schedEnd = new Date(scheduleEnd);
        if (start < schedStart || end > schedEnd) return `${who}: outside schedule window`;
      }
      return "";
    })
    .filter(Boolean);
  const hasErrors = staffWarnings.length > 0 || demandWarnings.length > 0 || ptoWarnings.length > 0;

  // --- useEffects ---
  useEffect(() => {
    fetchHealth()
      .then((res) => setStatus(`API status: ${res.status}`))
      .catch((err) => setStatus(`API unreachable: ${err.message}`));
  }, []);
  useEffect(() => {
    const idSet = new Set(staffRows.map((s) => s.id).filter((v) => v && v.trim().length > 0));
    setBleachRotation((prev) => prev.filter((id) => idSet.has(id)));
    setPtoRows((prev) => prev.filter((row) => !row.staff_id || idSet.has(row.staff_id)));
  }, [staffRows]);
  useEffect(() => {
    if (!isAuthed) {
      setIsAdmin(false);
      return;
    }
    api
      .get<UserInfo>("auth/me")
      .then((r) => {
        const data = r.data;
        setIsAdmin((data?.role || "").toLowerCase() === "admin");
        if (data?.username) {
          localStorage.setItem("auth_user", data.username);
          window.dispatchEvent(new Event("storage"));
        }
      })
      .catch(() => {
        setIsAdmin(false);
      });
  }, [isAuthed, authToken]);
  useEffect(() => {
    if (!isAuthed) {
      setLatestScheduleMeta(null);
      return;
    }
    refreshLatestMeta();
  }, [isAuthed]);
  useEffect(() => {
    if (!isAuthed || autoLoadedConfig) return;
    const last = localStorage.getItem("last_config") || "";
    if (configs.length === 1) {
      const target = configs[0];
      setSelectedConfig(target);
      setAutoLoadedConfig(true);
      handleLoadConfig(target);
    } else if (last && configs.includes(last)) {
      setSelectedConfig(last);
      setAutoLoadedConfig(true);
      handleLoadConfig(last);
    }
  }, [configs, isAuthed, autoLoadedConfig]);
  useEffect(() => {
    if (authToken) {
      setAuthToken(authToken);
      localStorage.setItem("auth_token", authToken);
    } else {
      localStorage.removeItem("auth_token");
    }
  }, [authToken]);
  useEffect(() => {
    if (!isAuthed) return;
    listConfigs()
      .then((names) => setConfigs(names))
      .catch((err) => {
        if (err?.response?.status === 401) {
          setAuthTokenState(null);
          setAuthToken(null);
          setConfigs([]);
          setStatus("Session expired. Please log in again.");
          return;
        }
        setConfigs([]);
        const msg = friendlyError(err, "Failed to load configs");
        setStatus(msg);
        setLastError(msg);
      });
  }, [isAuthed]);

  // --- Config handlers ---
  const handleLoadConfig = async (name?: string) => {
    const cfgName = name ?? selectedConfig;
    if (!cfgName) return;
    setSelectedConfig(cfgName);
    try {
      const cfg: ConfigPayload = await loadConfig(cfgName);
      setConfigName(cfg.clinic?.name ?? "Clinic");
      setTimezone(cfg.clinic?.timezone ?? "UTC");
      setStartDate(cfg.schedule?.start ?? startDate);
      setWeeks(Number(cfg.schedule?.weeks ?? weeks));
      setPatientsPerTech(Number(cfg.ratios?.patients_per_tech ?? patientsPerTech));
      setPatientsPerRn(Number(cfg.ratios?.patients_per_rn ?? patientsPerRn));
      setTechsPerRn(Number(cfg.ratios?.techs_per_rn ?? techsPerRn));
      setBleachDay(cfg.bleach?.day ?? bleachDay);
      setBleachCursor(Number(cfg.bleach?.cursor ?? bleachCursor));
      setBleachRotation(Array.isArray(cfg.bleach?.rotation) ? cfg.bleach.rotation.map(String) : []);
      setBleachFrequency(cfg.schedule?.bleach_frequency || (cfg as any)?.bleach?.frequency || "weekly");
      setTrials(Number(cfg.tournament?.trials ?? trials));
      setThreeDayWeight(
        coerceConstraintWeight(cfg.constraints?.enforce_three_day_cap, threeDayWeight)
      );
      setPostBleachWeight(
        coerceConstraintWeight(cfg.constraints?.enforce_post_bleach_rest, postBleachWeight)
      );
      setAltSatWeight(
        coerceConstraintWeight(cfg.constraints?.enforce_alt_saturdays, altSatWeight)
      );
      setTechFourWeight(
        coerceConstraintWeight(cfg.constraints?.limit_tech_four_days, techFourWeight)
      );
      setRnFourWeight(
        coerceConstraintWeight(cfg.constraints?.limit_rn_four_days, rnFourWeight)
      );
      if (Array.isArray(cfg.export_roles)) {
        setExportRoles(cfg.export_roles as string[]);
      }
      if (cfg.staff && Array.isArray(cfg.staff)) {
        const normalized = cfg.staff.map((row: any) => ({
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
          pref_open_mwf: 5 - Number(row.pref_open_mwf ?? row.open_mwf ?? 0),
          pref_open_tts: 5 - Number(row.pref_open_tts ?? row.open_tts ?? 0),
          pref_mid_mwf: 5 - Number(row.pref_mid_mwf ?? row.mid_mwf ?? 0),
          pref_mid_tts: 5 - Number(row.pref_mid_tts ?? row.mid_tts ?? 0),
          pref_close_mwf: 5 - Number(row.pref_close_mwf ?? row.close_mwf ?? 0),
          pref_close_tts: 5 - Number(row.pref_close_tts ?? row.close_tts ?? 0)
        }));
        setStaffRows(normalized.length ? normalized : [{ id: "", name: "", role: "Tech" }]);
      }
      if (cfg.demand && Array.isArray(cfg.demand)) {
        setDemandRows(
          cfg.demand.map((row: any) => ({
            Day: String(row.Day ?? row.day ?? ""),
            Patients: Number(row.Patients ?? 0),
            Tech_Open: Number(row.Tech_Open ?? 0),
            Tech_Mid: Number(row.Tech_Mid ?? 0),
            Tech_Close: Number(row.Tech_Close ?? 0),
            RN_Count: Number(row.RN_Count ?? 0),
            Admin_Count: Number(row.Admin_Count ?? 0)
          }))
        );
      }
      if (cfg.pto && Array.isArray(cfg.pto)) {
        setPtoRows(
          cfg.pto.map((row: any) => ({
            staff_id: String(row.staff_id ?? ""),
            start_date: row.start_date ?? "",
            end_date: row.end_date ?? row.start_date ?? ""
          }))
        );
      } else {
        setPtoRows([]);
      }
      setStatus(`Loaded config: ${cfgName}`);
      localStorage.setItem("last_config", cfgName);
    } catch (err: any) {
      const msg = friendlyError(err, "Failed to load config");
      setStatus(msg);
      setLastError(msg);
    }
  };

  const handleSaveConfig = async () => {
    if (hasErrors) {
      setStatus("Fix validation errors before saving.");
      return;
    }
    const scheduleStart = startDate || "";

    const payload: ConfigPayload = {
      clinic: { name: configName || "Demo Clinic", timezone },
      schedule: { start: scheduleStart, weeks, bleach_frequency: bleachFrequency },
      ratios: {
        patients_per_tech: patientsPerTech,
        patients_per_rn: patientsPerRn,
        techs_per_rn: techsPerRn
      },
      constraints: {
        enforce_three_day_cap: threeDayWeight,
        enforce_post_bleach_rest: postBleachWeight,
        enforce_alt_saturdays: altSatWeight,
        limit_tech_four_days: techFourWeight,
        limit_rn_four_days: rnFourWeight
      },
      bleach: { day: bleachDay, rotation: bleachRotation, cursor: bleachCursor, frequency: bleachFrequency },
      tournament: { trials, last_seed: 0 },
      export_roles: exportRoles,
      staff: staffRows.map((s) => ({
        ...s,
        pref_open_mwf: 5 - (s.pref_open_mwf ?? 5),
        pref_open_tts: 5 - (s.pref_open_tts ?? 5),
        pref_mid_mwf: 5 - (s.pref_mid_mwf ?? 5),
        pref_mid_tts: 5 - (s.pref_mid_tts ?? 5),
        pref_close_mwf: 5 - (s.pref_close_mwf ?? 5),
        pref_close_tts: 5 - (s.pref_close_tts ?? 5)
      })),
      demand: demandRows,
      pto: ptoRows
    };
    const req: SaveConfigRequest = { payload, filename: configName ? `${configName}.json` : undefined };
    try {
      const res = await saveConfig(req);
      setStatus(`Saved: ${res.filename}`);
      const names = await listConfigs();
      setConfigs(names);
    } catch (err: any) {
      const backendDetail =
        err?.response?.data?.detail && Array.isArray(err.response.data.detail)
          ? String(err.response.data.detail[0]?.msg || err.response.data.detail[0])
          : err?.response?.data?.detail || "";
      const msg = backendDetail ? `Save failed: ${backendDetail}` : friendlyError(err, "Failed to save config");
      setStatus(msg);
      setLastError(msg);
    }
  };

  const handleDeleteConfig = async () => {
    if (!selectedConfig) {
      setStatus("No config selected to delete.");
      return;
    }
    if (!confirm(`Delete config "${selectedConfig}"?`)) {
      return;
    }
    try {
      await deleteConfig(selectedConfig);
      setStatus(`Deleted: ${selectedConfig}`);
      const names = await listConfigs();
      setConfigs(names);
      setSelectedConfig("");
    } catch (err: any) {
      const msg = friendlyError(err, "Failed to delete config");
      setStatus(msg);
      setLastError(msg);
    }
  };

  // --- Auth handlers ---
  const handleLogin = async () => {
    try {
      const res = await login(loginUser, loginPass);
      localStorage.setItem("auth_token", res.token);
      setAuthTokenState(res.token);
      setAuthToken(res.token);
      setLoginError("");
      resetWorkspaceState("Logged in.");
      try {
        const names = await listConfigs();
        setConfigs(names);
      } catch {
        /* ignore - useEffect will retry */
      }
    } catch (err: any) {
      setAuthTokenState(null);
      setAuthToken(null);
      const msg =
        err?.response?.status === 401 ? "Invalid username or password" : friendlyError(err, "Incorrect username or password");
      setLoginError(msg);
      setStatus(msg);
    }
  };

  const handleSetup = async () => {
    try {
      if (!inviteToken.trim()) {
        setLoginError("Invite token required");
        return;
      }
      const res = await setupUser(inviteToken.trim(), loginUser, loginPass);
      localStorage.setItem("auth_token", res.token);
      setAuthTokenState(res.token);
      setAuthToken(res.token);
      setLoginError("");
      resetWorkspaceState("Account activated.");
      setLoginMode("login");
      try {
        const names = await listConfigs();
        setConfigs(names);
      } catch {
        /* ignore */
      }
    } catch (err: any) {
      setAuthTokenState(null);
      setAuthToken(null);
      const msg = friendlyError(err, "Activation failed. Please verify your token and try again.");
      setLoginError(msg);
      setStatus(msg);
    }
  };

  const handleLogout = () => {
    setAuthTokenState(null);
    setAuthToken(null);
    setIsAdmin(false);
    resetWorkspaceState("Logged out.");
  };

  // --- Run handler (stays in parent — touches shared state) ---
  const handleRun = async () => {
    if (hasErrors) {
      setStatus("Fix validation errors before running.");
      setLastError(
        [
          staffWarnings[0] ? `Staff: ${staffWarnings[0]}` : "",
          demandWarnings[0] ? `Demand: ${demandWarnings[0]}` : "",
          ptoWarnings[0] ? `PTO: ${ptoWarnings[0]}` : ""
        ]
          .filter(Boolean)
          .join(" | ")
      );
      return;
    }
    try {
      setIsRunning(true);
      setProgress(0);
      if (progressRef.current) clearInterval(progressRef.current);
      progressRef.current = setInterval(() => {
        setProgress((p) => (p < 90 ? p + 5 : p));
      }, 200);
      setStatus("Running schedule...");
      const staffPayload = staffRows.map((s) => ({
        id: s.id,
        name: s.name,
        role: s.role,
        can_open: s.can_open ?? false,
        can_close: s.can_close ?? false,
        can_bleach: s.can_bleach ?? false,
        availability: DAYS.reduce<Record<string, boolean>>((acc, day) => {
          acc[day] = s.availability?.[day] ?? true;
          return acc;
        }, {}),
        preferences: {
          open_mwf: 5 - (s.pref_open_mwf ?? 5),
          open_tts: 5 - (s.pref_open_tts ?? 5),
          mid_mwf: 5 - (s.pref_mid_mwf ?? 5),
          mid_tts: 5 - (s.pref_mid_tts ?? 5),
          close_mwf: 5 - (s.pref_close_mwf ?? 5),
          close_tts: 5 - (s.pref_close_tts ?? 5)
        }
      }));
      const requirements = demandRows.map((row) => ({
        day_name: row.Day,
        patient_count: row.Patients,
        tech_openers: row.Tech_Open,
        tech_mids: row.Tech_Mid,
        tech_closers: row.Tech_Close,
        rn_count: row.RN_Count,
        admin_count: row.Admin_Count
      }));
      const expandPTO = (): Array<{ staff_id: string; date: string }> => {
        const entries: Array<{ staff_id: string; date: string }> = [];
        for (const row of ptoRows) {
          if (!row.staff_id || !row.start_date) continue;
          const start = new Date(row.start_date);
          const end = new Date(row.end_date || row.start_date);
          if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) continue;
          const [a, b] = start <= end ? [start, end] : [end, start];
          for (let dt = new Date(a); dt <= b; dt.setDate(dt.getDate() + 1)) {
            entries.push({ staff_id: row.staff_id, date: dt.toISOString().slice(0, 10) });
          }
        }
        return entries;
      };
      const selectedSeed =
        usePrevSeed && winningSeed !== null ? winningSeed : baseSeed > 0 ? baseSeed : null;
      const payload = {
        staff: staffPayload,
        requirements,
        config: {
          clinic_name: configName || "Demo Clinic",
          timezone,
          start_date: startDate,
          weeks,
          bleach_day: bleachDay,
          bleach_rotation: bleachRotation,
          bleach_cursor: bleachCursor,
          bleach_frequency: bleachFrequency,
          patients_per_tech: patientsPerTech,
          patients_per_rn: patientsPerRn,
          techs_per_rn: techsPerRn,
          toggles: {
            enforce_three_day_cap: threeDayWeight,
            enforce_post_bleach_rest: postBleachWeight,
            enforce_alt_saturdays: altSatWeight,
            limit_tech_four_days: techFourWeight,
            limit_rn_four_days: rnFourWeight
          }
        },
        pto: expandPTO(),
        tournament_trials: trials,
        base_seed: selectedSeed,
        export_roles: exportRoles
      };
      const res = await runSchedule(payload);
        setAssignments(res.assignments);
        setStats(res.stats);
        setWinningSeed(res.winning_seed ?? null);
        setWinningScore(typeof res.total_penalty === "number" ? res.total_penalty : null);
        setScheduleStaffMap(null);
        if (typeof res.bleach_cursor === "number") {
          setBleachCursor(res.bleach_cursor);
        }
        setProgress(100);
      if (res.excel) {
        const blob = Uint8Array.from(window.atob(res.excel), (c) => c.charCodeAt(0));
        const file = new Blob([blob], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        });
        const url = URL.createObjectURL(file);
        setExcelUrl(url);
      } else {
        setExcelUrl(null);
      }
      setRunResult(
        `Winning seed: ${res.winning_seed ?? "n/a"} | Score: ${
          res.total_penalty?.toFixed ? res.total_penalty.toFixed(2) : res.total_penalty ?? "n/a"
        } | Next bleach in rotation: ${res.bleach_cursor} | Assignments: ${res.assignments.length}`
      );
      setStatus("Schedule generated.");
      refreshLatestMeta();
      try {
        localStorage.setItem("latest_schedule_ts", new Date().toISOString());
        window.dispatchEvent(new Event("storage"));
      } catch {
        /* ignore localStorage errors */
      }
    } catch (err: any) {
      const msg = friendlyError(err, "Failed to generate schedule");
      setStatus(msg);
      setRunResult("");
      setLastError(msg);
      setProgress(0);
    } finally {
      setIsRunning(false);
      if (progressRef.current) {
        clearInterval(progressRef.current);
        progressRef.current = null;
      }
    }
  };

  // --- Grouped state for child components ---
  const bleachState: BleachState = {
    day: bleachDay,
    frequency: bleachFrequency,
    cursor: bleachCursor,
    rotation: bleachRotation,
    postBleachWeight
  };
  const handleBleachChange = (next: BleachState) => {
    setBleachDay(next.day);
    setBleachFrequency(next.frequency);
    setBleachCursor(next.cursor);
    setBleachRotation(next.rotation);
    setPostBleachWeight(next.postBleachWeight);
  };

  const runConfig: RunConfig = {
    configName, timezone, startDate, weeks,
    threeDayWeight, altSatWeight, techFourWeight, rnFourWeight,
    patientsPerTech, patientsPerRn, techsPerRn,
    trials, baseSeed, usePrevSeed, exportRoles
  };
  const handleRunConfigChange = (next: RunConfig) => {
    setConfigName(next.configName);
    setTimezone(next.timezone);
    setStartDate(next.startDate);
    setWeeks(next.weeks);
    setThreeDayWeight(next.threeDayWeight);
    setAltSatWeight(next.altSatWeight);
    setTechFourWeight(next.techFourWeight);
    setRnFourWeight(next.rnFourWeight);
    setPatientsPerTech(next.patientsPerTech);
    setPatientsPerRn(next.patientsPerRn);
    setTechsPerRn(next.techsPerRn);
    setTrials(next.trials);
    setBaseSeed(next.baseSeed);
    setUsePrevSeed(next.usePrevSeed);
    setExportRoles(next.exportRoles);
  };

  // --- Login wall ---
  if (!isAuthed) {
      return (
        <section className="card planner-shell">
          <div className="planner-hero">
            <div>
              <p className="eyebrow-pill">Planner access</p>
              <h2 style={{ margin: "0.25rem 0 0.35rem" }}>Staff Planner (React prototype)</h2>
              <p className="hero-sub" style={{ maxWidth: "700px" }}>
                Sign in with your clinic manager credentials to load configs, run scenarios, and export clean handoffs. One login,
                no staff self-serve.
              </p>
              <div className="auth-badges">
                <span className="pill subtle">Secure session</span>
                <span className="pill subtle">Clinic manager only</span>
                <span className="pill subtle">Exports ready</span>
              </div>
            </div>
            <div className="auth-card">
              <div className="auth-card-head">
                <p className="muted">{loginMode === "login" ? "Existing user login" : "New user setup"}</p>
                <span className="pill success">Online</span>
              </div>
              <div className="auth-switch">
                <button
                  className={loginMode === "login" ? "primary-btn" : "secondary-btn"}
                  onClick={() => {
                    setLoginMode("login");
                    setLoginError("");
                  }}
                >
                  Existing user
                </button>
                <button
                  className={loginMode === "setup" ? "primary-btn" : "secondary-btn"}
                  onClick={() => {
                    setLoginMode("setup");
                    setLoginError("");
                  }}
                >
                  New user (invite)
                </button>
              </div>
              {loginMode === "login" ? (
                <form
                  className="auth-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleLogin();
                  }}
                >
                    <label className="field">
                      <span>Username</span>
                      <input
                        id="planner-login-username"
                        name="planner-login-username"
                        value={loginUser}
                        onChange={(e) => setLoginUser(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>Password</span>
                      <input
                        id="planner-login-password"
                        name="planner-login-password"
                        type="password"
                        value={loginPass}
                        onChange={(e) => setLoginPass(e.target.value)}
                      />
                    </label>
                  <button type="submit">Log in</button>
                </form>
              ) : (
                <form
                  className="auth-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSetup();
                  }}
                >
                    <label className="field">
                      <span>Invite token</span>
                      <input
                        id="planner-invite-token"
                        name="planner-invite-token"
                        value={inviteToken}
                        onChange={(e) => setInviteToken(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>Choose username</span>
                      <input
                        id="planner-setup-username"
                        name="planner-setup-username"
                        value={loginUser}
                        onChange={(e) => setLoginUser(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>Set password</span>
                      <input
                        id="planner-setup-password"
                        name="planner-setup-password"
                        type="password"
                        value={loginPass}
                        onChange={(e) => setLoginPass(e.target.value)}
                      />
                    </label>
                  <button type="submit">Activate account</button>
                </form>
              )}
              {loginError && <p className="status" style={{ color: "#f97316" }}>{loginError}</p>}
            </div>
          </div>
      </section>
    );
  }

  // --- Authenticated planner shell ---
  return (
    <section className="card planner-shell">
      <h2>Staff Planner (React prototype)</h2>
      <div className="planner-meta-row">
        <span className="pill subtle">
          {latestScheduleMeta?.generated_at
            ? `Last run: ${formatGeneratedAt(latestScheduleMeta.generated_at)}`
            : "No saved schedule"}
        </span>
      </div>
      {isAdmin || !status.toLowerCase().startsWith("api status") ? <p>{status}</p> : null}
      {lastError && <p style={{ color: "#b45309", marginTop: "0.35rem" }}>{lastError}</p>}
      <div
        style={{
          pointerEvents: isAuthed ? "auto" : "none",
          opacity: isAuthed ? 1 : 0.4
        }}
      >
        <div className="controls-row">
            <label>
              Load config:
              <select
                id="config-load-select"
                name="config-load-select"
                value={selectedConfig}
                onChange={(e) => setSelectedConfig(e.target.value)}
                style={{ marginLeft: "0.5rem" }}
              >
              <option value="">Select...</option>
              {configs.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => handleLoadConfig(selectedConfig)} disabled={!selectedConfig}>
            Load
          </button>
          <button onClick={handleDeleteConfig} disabled={!selectedConfig} className="secondary-btn">
            Delete
          </button>
            <input
              placeholder="Save as..."
              id="config-save-name"
              name="config-save-name"
              value={configName}
              onChange={(e) => setConfigName(e.target.value)}
              style={{ maxWidth: "180px" }}
            />
          <button onClick={handleSaveConfig}>Save</button>
        </div>
        <div className="tabs">
          {[
            { key: "staff", label: "Staff" },
            { key: "avail", label: "Availability" },
            { key: "prefs", label: "Prefs" },
            { key: "demand", label: "Demand" },
            { key: "pto", label: "PTO" },
            { key: "bleach", label: "Bleach" },
            { key: "run", label: "Run" },
            ...(isAdmin ? [{ key: "admin", label: "Admin" }] : [])
          ].map((tab) => (
            <button
              key={tab.key}
              className={`tab-btn ${activeTab === tab.key ? "active" : ""}`}
              onClick={() => setActiveTab(tab.key as any)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "staff" && (
          <StaffEditor rows={staffRows} onChange={setStaffRows} />
        )}

        {activeTab === "avail" && (
          <AvailabilityEditor rows={staffRows} onChange={setStaffRows} />
        )}

        {activeTab === "prefs" && (
          <PrefsEditor rows={staffRows} onChange={setStaffRows} />
        )}

        {activeTab === "demand" && <DemandEditor rows={demandRows} onChange={setDemandRows} />}
        {activeTab === "demand" && demandWarnings.length > 0 && (
          <ul style={{ color: "#b45309" }}>
            {demandWarnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}

        {activeTab === "pto" && (
          <>
            <p className="muted">
              Schedule window: {startDate || "n/a"} to {scheduleEnd || "n/a"}
            </p>
              <PTOEditor
                rows={ptoRows}
                onChange={setPtoRows}
                staffOptions={staffRows
                  .filter((s) => s.id.trim())
                  .map((s) => ({ id: s.id, name: s.name?.trim() ? s.name : "(no name set)" }))}
                scheduleStart={startDate}
                scheduleEnd={scheduleEnd}
              />
            {ptoWarnings.length > 0 && (
              <ul style={{ color: "#b45309" }}>
                {ptoWarnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </>
        )}

        {activeTab === "bleach" && (
          <BleachEditor
            state={bleachState}
            onChange={handleBleachChange}
            staffNameMap={staffNameMap}
            availableBleachIds={availableBleachIds}
          />
        )}

        {activeTab === "run" && (
          <RunPanel
            config={runConfig}
            onConfigChange={handleRunConfigChange}
            isRunning={isRunning}
            progress={progress}
            runResult={runResult}
            assignments={assignments}
            stats={stats}
            displayStaffMap={displayStaffMap}
            hasErrors={hasErrors}
            isAuthed={isAuthed}
            onRun={handleRun}
            onDownloadExcel={downloadSavedSchedule}
            onDownloadCsv={downloadSavedScheduleCsv}
            onLoadLatest={loadLatestSavedSchedule}
          />
        )}

        {activeTab === "admin" && isAdmin && <AdminPanel />}
      </div>
    </section>
  );
}
