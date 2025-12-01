import { useEffect, useRef, useState } from "react";
import {
  fetchHealth,
  listConfigs,
  loadConfig,
  saveConfig,
  ConfigPayload,
  SaveConfigRequest,
  runSchedule,
  login,
  setAuthToken,
  setupUser,
  createInvite,
  listUsers,
  deleteUser,
  revokeInvite,
  listAudit,
  updateUserRole,
  resetUserInvite,
  UserSummary,
  AuditEntry
} from "../api/client";
import DemandEditor from "../components/DemandEditor";
import PTOEditor from "../components/PTOEditor";
import { DemandRow, PTORow, StaffRow } from "../types";
import { DAYS } from "../constants";

export default function StaffPlanner() {
  const genId = () => {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    return Math.random().toString(36).slice(2, 10);
  };
  const copyText = async (text: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setInviteResult("Copied to clipboard");
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        setInviteResult("Copied to clipboard");
      }
    } catch {
      setInviteResult("Copy failed");
    }
  };
  const friendlyError = (err: any, fallback: string) => {
    const status = err?.response?.status;
    if (status === 401) return "Session expired. Please log in again.";
    if (status === 422) return "Validation failed. Please check your inputs.";
    if (status === 400 && err?.response?.data?.detail) return String(err.response.data.detail);
    if (status === 409) return "Conflict: value already in use.";
    return err?.message ?? fallback;
  };
  const [status, setStatus] = useState<string>("Checking API...");
  const [activeTab, setActiveTab] = useState<"staff" | "avail" | "prefs" | "demand" | "pto" | "run" | "admin">("staff");
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
    return localStorage.getItem("auth_token");
  });
  const [loginMode, setLoginMode] = useState<"login" | "setup">("login");
  const [loginUser, setLoginUser] = useState<string>("");
  const [loginPass, setLoginPass] = useState<string>("");
  const [inviteToken, setInviteToken] = useState<string>("");
  const [loginError, setLoginError] = useState<string>("");
  const [meLoaded, setMeLoaded] = useState<boolean>(false);
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
  const [trials, setTrials] = useState<number>(20);
  const [exportRoles, setExportRoles] = useState<string[]>(["Tech", "RN", "Admin"]);
  const [enforceThree, setEnforceThree] = useState<boolean>(true);
  const [enforcePostBleach, setEnforcePostBleach] = useState<boolean>(true);
  const [enforceAltSat, setEnforceAltSat] = useState<boolean>(true);
  const [limitTechFour, setLimitTechFour] = useState<boolean>(true);
  const [limitRnFour, setLimitRnFour] = useState<boolean>(true);
  const [inviteUsername, setInviteUsername] = useState<string>("");
  const [inviteLicense, setInviteLicense] = useState<string>("DEMO");
  const [inviteRole, setInviteRole] = useState<string>("user");
  const [inviteResult, setInviteResult] = useState<string>("");
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [currentUser, setCurrentUser] = useState<string>("");
  const [auditFeed, setAuditFeed] = useState<AuditEntry[]>([]);
  const [lastError, setLastError] = useState<string>("");
  const progressRef = useRef<NodeJS.Timeout | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [autoLoadedConfig, setAutoLoadedConfig] = useState<boolean>(false);
  const isAuthed = Boolean(authToken && authToken.length > 0);
  const uniqueStaffIds = Array.from(
    new Set(staffRows.filter((s) => s.can_bleach).map((s) => s.id).filter((v) => v && v.trim().length > 0))
  );
  const staffNameMap = staffRows.reduce<Record<string, string>>((acc, row) => {
    if (row.id) acc[row.id] = row.name?.trim() ? row.name : "(no name set)";
    return acc;
  }, {});
  const availableBleachIds = uniqueStaffIds.filter((sid) => !bleachRotation.includes(sid));
  const scheduleEnd = (() => {
    const start = startDate ? new Date(startDate) : null;
    if (!start || Number.isNaN(start.getTime())) return "";
    const end = new Date(start);
    end.setDate(end.getDate() + weeks * 7 - 1);
    return end.toISOString().slice(0, 10);
  })();

  useEffect(() => {
    fetchHealth()
      .then((res) => setStatus(`API status: ${res.status}`))
      .catch((err) => setStatus(`API unreachable: ${err.message}`));
  }, []);
  // Fetch current user info to set admin flag
  useEffect(() => {
    if (!isAuthed) {
      setIsAdmin(false);
      setMeLoaded(false);
      setCurrentUser("");
      return;
    }
    fetch("/api/auth/me", { headers: { Authorization: `Bearer ${authToken}` } })
      .then((r) => r.json())
      .then((data) => {
        setIsAdmin((data?.role || "").toLowerCase() === "admin");
        setCurrentUser(data?.username || "");
        setMeLoaded(true);
      })
      .catch(() => {
        setIsAdmin(false);
        setMeLoaded(false);
        setCurrentUser("");
      });
  }, [isAuthed, authToken]);
  useEffect(() => {
    if (isAuthed && isAdmin && activeTab === "admin") {
      loadUsers();
      loadAudit();
    }
  }, [isAuthed, isAdmin, activeTab]);
  // Autoload config: if only one available or a last used exists
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
  // Prune bleach rotation entries that no longer exist in staff list
  useEffect(() => {
    const validIds = new Set(staffRows.map((s) => s.id).filter(Boolean));
    setBleachRotation((prev) => prev.filter((sid) => validIds.has(sid)));
  }, [staffRows]);
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
        setStatus(`Failed to load configs: ${err?.message ?? err}`);
      });
  }, [isAuthed]);

  const loadUsers = async () => {
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err: any) {
      // ignore for now
    }
  };
  const loadAudit = async () => {
    try {
      const data = await listAudit(50);
      setAuditFeed(data);
    } catch {
      /* ignore */
    }
  };
  const updateRow = (index: number, key: "id" | "name" | "role", value: string) => {
    setStaffRows((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [key]: value };
      return next;
    });
  };

  const addRow = () =>
    setStaffRows((prev) => [
      ...prev,
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

  const removeRow = (index: number) =>
    setStaffRows((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev));

  const staffWarnings: string[] = [];
  staffRows.forEach((row, idx) => {
    if (!row.id?.trim()) {
      staffWarnings.push(`Staff row ${idx + 1}: missing ID`);
    }
    if (!row.name?.trim()) {
      staffWarnings.push(`Staff row ${idx + 1}: missing name`);
    }
    if (!row.role?.trim()) {
      staffWarnings.push(`Staff row ${idx + 1}: missing role`);
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

  const fmtDateTime = (value?: string | null) => {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString(undefined, {
      month: "2-digit",
      day: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  };

  const WarningList = ({ title, items }: { title: string; items: string[] }) => {
    if (!items.length) return null;
    return (
      <div
        style={{
          background: "rgba(227, 110, 26, 0.12)",
          border: "1px solid rgba(227, 110, 26, 0.4)",
          color: "#b45309",
          padding: "0.5rem 0.75rem",
          borderRadius: "8px",
          marginBottom: "0.75rem"
        }}
      >
        <strong>{title}</strong>
        <ul style={{ margin: "0.35rem 0 0 1rem" }}>
          {items.map((msg, i) => (
            <li key={`${msg}-${i}`}>{msg}</li>
          ))}
        </ul>
      </div>
    );
  };

  const getWarningsForTab = () => {
    switch (activeTab) {
      case "staff":
      case "avail":
      case "prefs":
        return staffWarnings;
      case "demand":
        return demandWarnings;
      case "pto":
        return ptoWarnings;
      default:
        return [];
    }
  };

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
      setTrials(Number(cfg.tournament?.trials ?? trials));
      setEnforceThree(Boolean(cfg.constraints?.enforce_three_day_cap ?? enforceThree));
      setEnforcePostBleach(Boolean(cfg.constraints?.enforce_post_bleach_rest ?? enforcePostBleach));
      setEnforceAltSat(Boolean(cfg.constraints?.enforce_alt_saturdays ?? enforceAltSat));
      setLimitTechFour(Boolean(cfg.constraints?.limit_tech_four_days ?? limitTechFour));
      setLimitRnFour(Boolean(cfg.constraints?.limit_rn_four_days ?? limitRnFour));
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
      setStatus(friendlyError(err, "Failed to load config."));
    }
  };

  const handleSaveConfig = async () => {
    if (hasErrors) {
      setStatus("Fix validation errors before saving.");
      return;
    }
    const payload: ConfigPayload = {
      clinic: { name: configName || "Demo Clinic", timezone },
      schedule: { start: startDate, weeks },
      ratios: {
        patients_per_tech: patientsPerTech,
        patients_per_rn: patientsPerRn,
        techs_per_rn: techsPerRn
      },
      constraints: {
        enforce_three_day_cap: enforceThree,
        enforce_post_bleach_rest: enforcePostBleach,
        enforce_alt_saturdays: enforceAltSat,
        limit_tech_four_days: limitTechFour,
        limit_rn_four_days: limitRnFour
      },
      bleach: { day: bleachDay, rotation: bleachRotation, cursor: bleachCursor },
      tournament: { trials, last_seed: 0 },
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
      setStatus(friendlyError(err, "Failed to save config."));
    }
  };

  const handleLogin = async () => {
    try {
      const res = await login(loginUser, loginPass);
      // Persist and apply token immediately
      localStorage.setItem("auth_token", res.token);
      setAuthTokenState(res.token);
      setAuthToken(res.token);
      setLoginError("");
      setStatus("Logged in.");
      try {
        const names = await listConfigs();
        setConfigs(names);
      } catch {
        /* ignore – useEffect will retry */
      }
    } catch (err: any) {
      setAuthTokenState(null);
      setAuthToken(null);
      const msg =
        err?.response?.status === 401
          ? "Incorrect username or password"
          : err?.response?.status === 409
          ? "Username already taken"
          : err?.message ?? "Login failed";
      setLoginError(msg);
      // Keep only the inline login error, don't mirror in status
      // setStatus(msg);
    }
  };

  const handleSetup = async () => {
    try {
      if (!inviteToken.trim()) {
        setLoginError("Invite token required");
        return;
      }
      if (!loginUser.trim()) {
        setLoginError("Username required");
        return;
      }
      const res = await setupUser(inviteToken.trim(), loginUser.trim(), loginPass);
      localStorage.setItem("auth_token", res.token);
      setAuthTokenState(res.token);
      setAuthToken(res.token);
      setLoginError("");
      setStatus("Account activated.");
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
      setLoginError(err?.message ?? "Setup failed");
      setStatus("Setup failed");
    }
  };

  const handleLogout = () => {
    setAuthTokenState(null);
    setAuthToken(null);
    setStatus("Logged out.");
    setConfigs([]);
    setAssignments([]);
    setCurrentUser("");
    setUsers([]);
    setIsAdmin(false);
  };

  const isApiStatus = status.toLowerCase().startsWith("api status");
  if (!isAuthed) {
      return (
        <section className="card">
          <h2>Staff Planner (React prototype)</h2>
          {!isApiStatus ? <p>{status}</p> : null}
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h4>{loginMode === "login" ? "Existing user login" : "New user setup"}</h4>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "0.5rem" }}>
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
              className="stack"
              style={{ gap: "0.75rem" }}
              onSubmit={(e) => {
                e.preventDefault();
                handleLogin();
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: "0.75rem",
                  alignItems: "end"
                }}
              >
                <label style={{ flex: "1 1 200px" }}>
                  Username
                  <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} />
                </label>
                <label style={{ flex: "1 1 200px" }}>
                  Password
                  <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} />
                </label>
                <div style={{ display: "flex", justifyContent: "flex-start", alignItems: "center" }}>
                  <button type="submit" className="primary-btn" style={{ height: "42px" }}>
                    Login
                  </button>
                </div>
              </div>
            </form>
          ) : (
            <form
              className="stack"
              style={{ gap: "0.75rem" }}
              onSubmit={(e) => {
                e.preventDefault();
                handleSetup();
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: "0.75rem",
                  alignItems: "end"
                }}
              >
                <label style={{ flex: "1 1 180px" }}>
                  Invite token
                  <input value={inviteToken} onChange={(e) => setInviteToken(e.target.value)} />
                </label>
                <label style={{ flex: "1 1 180px" }}>
                  Choose username
                  <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} />
                </label>
                <label style={{ flex: "1 1 180px" }}>
                  Set password
                  <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} />
                </label>
                <div style={{ display: "flex", justifyContent: "flex-start", alignItems: "center" }}>
                  <button type="submit" className="primary-btn" style={{ height: "42px" }}>
                    Activate account
                  </button>
                </div>
              </div>
            </form>
          )}
          {loginError && <p style={{ color: "#b45309" }}>{loginError}</p>}
        </div>
      </section>
    );
  }

  return (
    <section className="card">
      <h2>Staff Planner (React prototype)</h2>
      {isAdmin || !status.toLowerCase().startsWith("api status") ? <p>{status}</p> : null}
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem", gap: "0.5rem", alignItems: "center" }}>
            <div>
              <strong>User tools</strong>
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem", alignItems: "center" }}>
                <input
                  placeholder="License key"
                  value={inviteLicense}
                  onChange={(e) => setInviteLicense(e.target.value)}
                  style={{ maxWidth: "120px" }}
                  disabled={!isAuthed}
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              style={{ maxWidth: "120px" }}
              disabled={!isAuthed}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <button
              className="secondary-btn"
              onClick={async () => {
                try {
                  const generatedUser =
                    inviteUsername.trim() ||
                    (typeof crypto !== "undefined" && crypto.randomUUID ? `user-${crypto.randomUUID().slice(0, 8)}` : `user-${Math.random().toString(36).slice(2, 8)}`);
                const res = await createInvite({
                  username: generatedUser,
                  license_key: inviteLicense,
                  role: inviteRole
                });
                setInviteResult(`Invite token: ${res.token}`);
              } catch (err: any) {
                setInviteResult(friendlyError(err, "Failed to create invite"));
              }
            }}
            disabled={!isAuthed}
          >
            Create invite
            </button>
          </div>
          {inviteResult && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.35rem", flexWrap: "wrap" }}>
              <p className="muted" style={{ margin: 0 }}>
                {inviteResult}
              </p>
              {inviteResult.toLowerCase().includes("token:") && (
                <button
                  className="secondary-btn"
                  onClick={() => {
                    const token = inviteResult.split(":").pop()?.trim() ?? "";
                    if (token) copyText(token);
                  }}
                >
                  Copy
                </button>
              )}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <span className="muted">{authToken ? `Logged in as ${currentUser || "user"}` : "Not authenticated"}</span>
          {authToken && (
            <button className="secondary-btn" onClick={handleLogout}>
              Logout
            </button>
          )}
        </div>
        {lastError && <p style={{ color: "#b45309", marginTop: "0.35rem" }}>{lastError}</p>}
      </div>
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
        <input
          placeholder="Save as..."
          value={configName}
          onChange={(e) => setConfigName(e.target.value)}
          style={{ maxWidth: "180px" }}
        />
        <button onClick={handleSaveConfig}>Save</button>
      </div>
      {isAuthed && <WarningList title="Issues on this tab" items={getWarningsForTab()} />}
      <div className="tabs">
        {[
          { key: "staff", label: "Staff" },
          { key: "avail", label: "Availability" },
          { key: "prefs", label: "Prefs" },
          { key: "demand", label: "Demand" },
          { key: "pto", label: "PTO" },
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
        <>
          <table cellPadding={8} style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Name</th>
                <th align="left">Role</th>
                <th align="left">Can Open</th>
                <th align="left">Can Close</th>
                <th align="left">Can Bleach</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {staffRows.map((row, index) => (
                <tr key={index}>
                  <td>
                    <input value={row.name} onChange={(e) => updateRow(index, "name", e.target.value)} />
                  </td>
                  <td>
                    <select value={row.role} onChange={(e) => updateRow(index, "role", e.target.value)}>
                      <option value="Tech">Tech</option>
                      <option value="RN">RN</option>
                      <option value="Admin">Admin</option>
                    </select>
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={row.can_open ?? false}
                      onChange={(e) =>
                        setStaffRows((prev) => {
                          const next = [...prev];
                          next[index] = { ...next[index], can_open: e.target.checked };
                          return next;
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={row.can_close ?? false}
                      onChange={(e) =>
                        setStaffRows((prev) => {
                          const next = [...prev];
                          next[index] = { ...next[index], can_close: e.target.checked };
                          return next;
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={row.can_bleach ?? false}
                      onChange={(e) =>
                        setStaffRows((prev) => {
                          const next = [...prev];
                          next[index] = {
                            ...next[index],
                            can_bleach: e.target.checked,
                            can_close: e.target.checked ? true : next[index].can_close
                          };
                          return next;
                        })
                      }
                    />
                  </td>
                  <td>
                    <button className="secondary-btn" onClick={() => removeRow(index)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button style={{ marginTop: "1rem" }} onClick={addRow}>
            Add Row
          </button>
          <WarningList title="Staff issues" items={staffWarnings} />
        </>
      )}

      {activeTab === "prefs" && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>Preference Weights</h3>
          <p className="muted">
            0 = "Avoid", 10 = "Prefer". Separate values for MWF vs TTS. Range 0 to 10 (5 is neutral), step 0.25.
          </p>
          {staffRows.map((row, idx) => (
            <div
              key={idx}
              style={{
                borderBottom: "1px solid rgba(255,255,255,0.08)",
                paddingBottom: "1.25rem",
                marginBottom: "1.25rem",
                background: "rgba(255,255,255,0.02)",
                borderRadius: "8px",
                padding: "1rem"
              }}
            >
              <strong>{row.name?.trim() ? row.name : "(no name set)"}</strong> ({row.role || "Tech"})
              <div
                style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "0.75rem",
                alignItems: "center",
                marginTop: "0.5rem"
                }}
              >
                {[
                  { key: "pref_open_mwf" as const, label: "Open MWF", value: row.pref_open_mwf ?? 5 },
                  { key: "pref_open_tts" as const, label: "Open TTS", value: row.pref_open_tts ?? 5 },
                  { key: "pref_close_mwf" as const, label: "Close MWF", value: row.pref_close_mwf ?? 5 },
                  { key: "pref_close_tts" as const, label: "Close TTS", value: row.pref_close_tts ?? 5 }
                ].map((item) => (
                  <div key={item.key} style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", alignItems: "center" }}>
                      <span>{item.label}</span>
                      <input
                        type="number"
                        min={0}
                        max={10}
                        step={0.25}
                        value={item.value}
                        onChange={(e) =>
                          setStaffRows((prev) => {
                            const next = [...prev];
                            next[idx] = { ...next[idx], [item.key]: Number(e.target.value) || 5 } as any;
                            return next;
                          })
                        }
                        style={{ width: "72px", fontVariantNumeric: "tabular-nums" }}
                      />
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={10}
                      step={0.25}
                      value={item.value}
                      onChange={(e) =>
                        setStaffRows((prev) => {
                          const next = [...prev];
                          next[idx] = { ...next[idx], [item.key]: Number(e.target.value) || 5 } as any;
                          return next;
                        })
                      }
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === "avail" && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>Availability</h3>
          <p className="muted">Toggle the days each staffer can work.</p>
          <table cellPadding={6} style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th>Staff</th>
                {DAYS.map((d) => (
                  <th key={d}>{d}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {staffRows.map((row, idx) => (
                <tr key={idx}>
                  <td title={row.id || ""}>
                    {row.name?.trim() ? row.name : "(no name set)"}
                  </td>
                  {DAYS.map((day) => (
                    <td key={day} style={{ textAlign: "center" }}>
                      <input
                        type="checkbox"
                        checked={row.availability?.[day] ?? true}
                        onChange={(e) =>
                          setStaffRows((prev) => {
                            const next = [...prev];
                            const avail = { ...(next[idx].availability ?? defaultAvailability) };
                            avail[day] = e.target.checked;
                            next[idx] = { ...next[idx], availability: avail };
                            return next;
                          })
                        }
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <WarningList title="Demand issues" items={demandWarnings} />
        </div>
      )}

      {activeTab === "demand" && <DemandEditor rows={demandRows} onChange={setDemandRows} />}
      {activeTab === "demand" && <WarningList title="Demand issues" items={demandWarnings} />}

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
          <WarningList title="PTO issues" items={ptoWarnings} />
        </>
      )}

      {activeTab === "run" && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>Run Scheduler</h3>
          <div className="stack">
            <label>
              Clinic
              <input value={configName} onChange={(e) => setConfigName(e.target.value)} />
            </label>
            <label>
              Timezone
              <input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
            </label>
          </div>
          <div className="stack">
            <label>
              Start date
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </label>
            <label>
              Weeks
              <input
                type="number"
                min={1}
                max={6}
                value={weeks}
                onChange={(e) => setWeeks(Number(e.target.value))}
              />
            </label>
            <label>
              Bleach day
              <select value={bleachDay} onChange={(e) => setBleachDay(e.target.value)}>
                {DAYS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Bleach cursor
              <input
                type="number"
                min={0}
                value={bleachCursor}
                onChange={(e) => setBleachCursor(Number(e.target.value))}
              />
            </label>
          </div>
          <div className="stack" style={{ alignItems: "flex-start" }}>
            <div style={{ minWidth: "280px" }}>
              <p style={{ margin: "0 0 4px 0" }}>Bleach rotation (ordered)</p>
              <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
                <select
                  value=""
                  onChange={(e) => {
                    const sid = e.target.value;
                    if (!sid) return;
                    setBleachRotation((prev) => [...prev, sid]);
                  }}
                >
                  <option value="">Add bleacher...</option>
                  {availableBleachIds.map((sid) => (
                    <option key={sid} value={sid}>
                      {staffNameMap[sid] || sid}
                    </option>
                  ))}
                </select>
                <button
                  className="secondary-btn"
                  onClick={() => setBleachRotation([])}
                  disabled={bleachRotation.length === 0}
                >
                  Clear
                </button>
              </div>
              {bleachRotation.length === 0 && <p className="muted">No bleach rotation set.</p>}
              {bleachRotation.map((sid, idx) => (
                <div
                  key={`${sid}-${idx}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    marginBottom: "0.25rem"
                  }}
                >
                  <span style={{ minWidth: 24, textAlign: "right" }}>{idx + 1}.</span>
                  <span style={{ flex: 1 }}>{staffNameMap[sid] || sid}</span>
                  <button
                    className="secondary-btn"
                    onClick={() =>
                      setBleachRotation((prev) => {
                        const next = [...prev];
                        if (idx > 0) [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
                        return next;
                      })
                    }
                    disabled={idx === 0}
                  >
                    ↑
                  </button>
                  <button
                    className="secondary-btn"
                    onClick={() =>
                      setBleachRotation((prev) => {
                        const next = [...prev];
                        if (idx < next.length - 1) [next[idx + 1], next[idx]] = [next[idx], next[idx + 1]];
                        return next;
                      })
                    }
                    disabled={idx === bleachRotation.length - 1}
                  >
                    ↓
                  </button>
                  <button
                    className="secondary-btn"
                    onClick={() => setBleachRotation((prev) => prev.filter((_, i) => i !== idx))}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
          <div className="stack">
            <label>
              Enforce 2-day max
              <input type="checkbox" checked={enforceThree} onChange={(e) => setEnforceThree(e.target.checked)} />
            </label>
            <label>
              No post-bleach day
              <input
                type="checkbox"
                checked={enforcePostBleach}
                onChange={(e) => setEnforcePostBleach(e.target.checked)}
              />
            </label>
            <label>
              No consecutive Saturdays
              <input type="checkbox" checked={enforceAltSat} onChange={(e) => setEnforceAltSat(e.target.checked)} />
            </label>
            <label>
              Tech 4-day cap
              <input type="checkbox" checked={limitTechFour} onChange={(e) => setLimitTechFour(e.target.checked)} />
            </label>
            <label>
              RN 4-day cap
              <input type="checkbox" checked={limitRnFour} onChange={(e) => setLimitRnFour(e.target.checked)} />
            </label>
          </div>
          <div className="stack">
            <label>
              Patients/Tech
              <input
                type="number"
                min={1}
                value={patientsPerTech}
                onChange={(e) => setPatientsPerTech(Number(e.target.value))}
              />
            </label>
            <label>
              Patients/RN
              <input
                type="number"
                min={1}
                value={patientsPerRn}
                onChange={(e) => setPatientsPerRn(Number(e.target.value))}
              />
            </label>
            <label>
              Techs/RN
              <input
                type="number"
                min={1}
                value={techsPerRn}
                onChange={(e) => setTechsPerRn(Number(e.target.value))}
              />
            </label>
            <label>
              Trials
              <input type="number" min={1} value={trials} onChange={(e) => setTrials(Number(e.target.value))} />
            </label>
            <label>
              Seed (0 = random)
              <input type="number" min={0} value={baseSeed} onChange={(e) => setBaseSeed(Number(e.target.value))} />
            </label>
            <label style={{ alignItems: "center" }}>
              <input
                type="checkbox"
                checked={usePrevSeed}
                onChange={(e) => setUsePrevSeed(e.target.checked)}
                style={{ marginRight: "6px" }}
              />
              Use previous best seed
            </label>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span>Export roles</span>
              <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.25rem" }}>
                {["Tech", "RN", "Admin"].map((role) => (
                  <label key={role} style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                    <input
                      type="checkbox"
                      checked={exportRoles.includes(role)}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setExportRoles((prev) => {
                          if (checked) return Array.from(new Set([...prev, role]));
                          return prev.filter((r) => r !== role);
                        });
                      }}
                    />
                    {role}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <button
            disabled={hasErrors}
            onClick={async () => {
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
                    patients_per_tech: patientsPerTech,
                    patients_per_rn: patientsPerRn,
                    techs_per_rn: techsPerRn,
                    toggles: {
                      enforce_three_day_cap: enforceThree,
                      enforce_post_bleach_rest: enforcePostBleach,
                      enforce_alt_saturdays: enforceAltSat,
                      limit_tech_four_days: limitTechFour,
                    limit_rn_four_days: limitRnFour
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
                  } | Next bleach cursor: ${res.bleach_cursor} | Assignments: ${res.assignments.length}`
                );
                setStatus("Schedule generated.");
              } catch (err: any) {
      setStatus(friendlyError(err, "Run failed. Please check inputs and try again."));
      setRunResult("");
                setProgress(0);
              } finally {
                setIsRunning(false);
                if (progressRef.current) {
                  clearInterval(progressRef.current);
                  progressRef.current = null;
                }
              }
            }}
          >
            Run Schedule
          </button>
          {isRunning && (
            <div style={{ marginTop: "0.5rem" }}>
              <div className="muted" style={{ marginBottom: "0.25rem" }}>
                Running trials...
              </div>
              <div
                style={{
                  height: "6px",
                  background: "var(--slate-200)",
                  borderRadius: "999px",
                  overflow: "hidden"
                }}
              >
                <div
                  style={{
                    width: "40%",
                    height: "100%",
                    background: "var(--indigo-600)",
                    animation: "progressPulse 1.2s ease-in-out infinite"
                  }}
                />
              </div>
            </div>
          )}
          {isRunning || progress > 0 ? (
            <div style={{ marginTop: "0.75rem" }}>
              <div className="muted">Running {trials} trials...</div>
              <div
                style={{
                  height: "8px",
                  background: "var(--warm-3)",
                  borderRadius: "999px",
                  overflow: "hidden",
                  marginTop: "0.35rem"
                }}
              >
                <div
                  style={{
                    width: `${Math.min(progress, 100)}%`,
                    height: "100%",
                    background: "var(--brand-blue)",
                    transition: "width 0.2s ease"
                  }}
                />
              </div>
            </div>
          ) : null}
          {runResult && <p style={{ marginTop: "0.75rem" }}>{runResult}</p>}
          {excelUrl && (
            <button
              className="primary-btn"
              style={{ marginTop: "0.75rem" }}
              onClick={() => {
                const link = document.createElement("a");
                link.href = excelUrl;
                link.download = "schedule.xlsx";
                link.click();
              }}
            >
              Download Excel
            </button>
          )}
          {assignments.length > 0 && (
            <div style={{ marginTop: "1rem", overflowX: "auto" }}>
              {(() => {
                const uniqueDates = Array.from(new Set(assignments.map((a) => a.date))).sort();
                const dateDayMap = uniqueDates.reduce<Record<string, string>>((acc, d) => {
                  const found = assignments.find((a) => a.date === d);
                  acc[d] = found?.day_name || "";
                  return acc;
                }, {});
                const dateLabelMap = uniqueDates.reduce<Record<string, string>>((acc, d) => {
                  const day = dateDayMap[d] || "";
                  acc[d] = day ? `${d} (${day})` : d;
                  return acc;
                }, {});
                const staffIdsByRole = ["Tech", "RN", "Admin"].reduce<Record<string, string[]>>((acc, role) => {
                  acc[role] = Array.from(
                    new Set(
                      assignments
                        .filter((a) => a.role === role && a.staff_id)
                        .map((a) => a.staff_id as string)
                    )
                  );
                  return acc;
                }, {});
                const dateMapByStaff = assignments.reduce<Record<string, Set<string>>>((acc, a) => {
                  if (!a.staff_id) return acc;
                  acc[a.staff_id] = acc[a.staff_id] || new Set();
                  acc[a.staff_id].add(a.date);
                  return acc;
                }, {});
                const labelMapByStaff = assignments.reduce<Record<string, Record<string, string>>>((acc, a) => {
                  if (!a.staff_id) return acc;
                  acc[a.staff_id] = acc[a.staff_id] || {};
                  const label =
                    a.duty === "bleach"
                      ? "Bleach"
                      : a.duty === "open"
                      ? "Open"
                      : a.duty === "close"
                      ? "Close"
                      : a.duty === "mid"
                      ? `Mid${a.slot_index > 1 ? a.slot_index : ""}`.trim()
                      : a.duty;
                  acc[a.staff_id][a.date] = label;
                  return acc;
                }, {});
                const hasMatrix = uniqueDates.length > 0;
                const weekBreaks = uniqueDates.reduce<Record<string, boolean>>((acc, d, idx) => {
                  const day = dateDayMap[d];
                  if (idx > 0 && day === "Mon") acc[d] = true;
                  return acc;
                }, {});
                if (!hasMatrix) return null;
                return (
                  <div style={{ marginTop: "1rem" }}>
                    <h4>Schedule Matrix</h4>
                    {["Tech", "RN", "Admin"].map((role) => {
                      const staffIds = staffIdsByRole[role] || [];
                      if (!staffIds.length) return null;
                      return (
                        <div key={role} style={{ marginBottom: "1rem" }}>
                          <h5 style={{ margin: "0 0 0.5rem 0" }}>{role}</h5>
                          <table
                            cellPadding={6}
                            style={{ minWidth: "700px", borderCollapse: "collapse", fontSize: "0.9rem" }}
                          >
                            <thead>
                              <tr>
                                <th>Staff</th>
                                {uniqueDates.map((d) => (
                                  <th
                                    key={d}
                                    style={weekBreaks[d] ? { borderLeft: "2px solid var(--slate-200)" } : undefined}
                                  >
                                    {dateLabelMap[d]}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {staffIds.map((sid) => (
                                <tr key={`${role}-${sid}`}>
                            <td>{staffNameMap[sid] || sid}</td>
                            {uniqueDates.map((d) => (
                              <td
                                key={`${sid}-${d}`}
                                style={{
                                  textAlign: "center",
                                  ...(weekBreaks[d] ? { borderLeft: "2px solid var(--slate-200)" } : undefined)
                                }}
                              >
                                {labelMapByStaff[sid]?.[d] || ""}
                              </td>
                            ))}
                          </tr>
                        ))}
                            </tbody>
                          </table>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          )}
          {stats && Object.keys(stats).length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <h4>Shift Totals</h4>
              <table cellPadding={6} style={{ minWidth: "300px", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr>
                    <th>Staff</th>
                    <th>Shifts</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(stats).map(([k, v]) => (
                    <tr key={k}>
                      <td>{staffNameMap[k] || k}</td>
                      <td>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {activeTab === "admin" && isAdmin && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>Admin</h3>
          <div style={{ marginBottom: "0.5rem", display: "flex", gap: "0.5rem" }}>
            <button className="secondary-btn" onClick={loadUsers}>
              Refresh users
            </button>
          </div>
          <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
            {users.length === 0 ? (
              <p className="muted">No users found.</p>
            ) : (
              <table cellPadding={6} style={{ minWidth: "780px", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr>
                    <th>Public ID</th>
                    <th>Username</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Last Login</th>
                    <th>Invite Expires</th>
                    <th>Invite Token</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td>{u.public_id || u.id}</td>
                      <td>{u.username}</td>
                      <td>
                        <select
                          value={u.role}
                          onChange={async (e) => {
                            const newRole = e.target.value;
                            try {
                          await updateUserRole(u.id, newRole);
                          loadUsers();
                        } catch (err: any) {
                          setInviteResult(friendlyError(err, "Failed to update role"));
                        }
                          }}
                        >
                          <option value="user">User</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td>{u.status}</td>
                      <td>{fmtDateTime(u.last_login) || "—"}</td>
                      <td>
                        {u.status !== "active" && u.invite_expires_at ? fmtDateTime(u.invite_expires_at) : "—"}
                      </td>
                      <td style={{ wordBreak: "break-all" }}>
                        {u.status !== "active" && u.invite_token ? (
                          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap" }}>
                            <span>{u.invite_token}</span>
                            <button className="secondary-btn" onClick={() => copyText(u.invite_token)}>
                              Copy
                            </button>
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td
                        style={{
                          display: "flex",
                          gap: "0.35rem",
                          flexWrap: "nowrap",
                          alignItems: "center",
                          justifyContent: "flex-start"
                        }}
                      >
                        <button
                          className="secondary-btn"
                          onClick={async () => {
                            try {
                              await revokeInvite({ username: u.username, license_key: "" });
                              loadUsers();
                            } catch (err: any) {
                              setInviteResult(friendlyError(err, "Failed to revoke invite"));
                            }
                          }}
                        >
                          Revoke invite
                        </button>
                        <button
                          className="secondary-btn"
                          onClick={async () => {
                            try {
                              await deleteUser(u.id);
                              loadUsers();
                            } catch (err: any) {
                              setInviteResult(friendlyError(err, "Failed to delete user"));
                            }
                          }}
                        >
                          Delete
                        </button>
                        <button
                          className="secondary-btn"
                          onClick={async () => {
                            try {
                              const res = await resetUserInvite(u.id);
                              setInviteResult(`Reset token for ${u.username}: ${res.token}`);
                              loadUsers();
                            } catch (err: any) {
                              setInviteResult(friendlyError(err, "Failed to reset invite"));
                            }
                          }}
                        >
                          Reset password
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div>
            <h4>Recent activity</h4>
            {auditFeed.length === 0 ? (
              <p className="muted">No audit entries.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table cellPadding={6} style={{ minWidth: "720px", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Event</th>
                      <th>User ID</th>
                      <th>Detail</th>
                      <th>IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditFeed.map((a) => (
                      <tr key={a.id}>
                        <td>{fmtDateTime(a.created_at) || "—"}</td>
                        <td>{a.event}</td>
                        <td>{a.user_id ?? "—"}</td>
                        <td>{a.detail || "—"}</td>
                        <td>{a.ip || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
      </div>
    </section>
  );
}
