import { useEffect, useState } from "react";
import {
  fetchHealth,
  listConfigs,
  loadConfig,
  saveConfig,
  ConfigPayload,
  SaveConfigRequest,
  runSchedule,
  login,
  setAuthToken
} from "../api/client";
import DemandEditor from "../components/DemandEditor";
import PTOEditor from "../components/PTOEditor";
import { DemandRow, PTORow, StaffRow } from "../types";
import { DAYS } from "../constants";

export default function StaffPlanner() {
  const [status, setStatus] = useState<string>("Checking API...");
  const [activeTab, setActiveTab] = useState<"staff" | "avail" | "prefs" | "demand" | "pto" | "run">("staff");
  const defaultAvailability = DAYS.reduce<Record<string, boolean>>((acc, day) => {
    acc[day] = true;
    return acc;
  }, {});
  const [staffRows, setStaffRows] = useState<StaffRow[]>([
    {
      id: "",
      name: "",
      role: "Tech",
      can_bleach: false,
      can_open: false,
      can_close: false,
      availability: { ...defaultAvailability },
      pref_open_mwf: 0,
      pref_open_tts: 0,
      pref_mid_mwf: 0,
      pref_mid_tts: 0,
      pref_close_mwf: 0,
      pref_close_tts: 0
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
  const [authToken, setAuthTokenState] = useState<string | null>(null);
  const [loginUser, setLoginUser] = useState<string>("admin");
  const [loginPass, setLoginPass] = useState<string>("admin");
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
  const [trials, setTrials] = useState<number>(20);
  const [exportRoles, setExportRoles] = useState<string[]>(["Tech", "RN", "Admin"]);
  const [enforceThree, setEnforceThree] = useState<boolean>(true);
  const [enforcePostBleach, setEnforcePostBleach] = useState<boolean>(true);
  const [enforceAltSat, setEnforceAltSat] = useState<boolean>(true);
  const [limitTechFour, setLimitTechFour] = useState<boolean>(true);
  const [limitRnFour, setLimitRnFour] = useState<boolean>(true);
  const isAuthed = Boolean(authToken && authToken.length > 0);
  const uniqueStaffIds = Array.from(
    new Set(staffRows.filter((s) => s.can_bleach).map((s) => s.id).filter((v) => v && v.trim().length > 0))
  );
  const staffNameMap = staffRows.reduce<Record<string, string>>((acc, row) => {
    if (row.id) acc[row.id] = row.name || row.id;
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
  useEffect(() => {
    if (authToken) {
      setAuthToken(authToken);
    }
  }, [authToken]);
  useEffect(() => {
    if (!isAuthed) return;
    listConfigs()
      .then((names) => setConfigs(names))
      .catch((err) => {
        setConfigs([]);
        setStatus(`Failed to load configs: ${err?.message ?? err}`);
      });
  }, [isAuthed]);
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
        id: "",
        name: "",
        role: "Tech",
        can_bleach: false,
        can_open: false,
        can_close: false,
        availability: { ...defaultAvailability },
        pref_open_mwf: 0,
        pref_open_tts: 0,
        pref_mid_mwf: 0,
        pref_mid_tts: 0,
        pref_close_mwf: 0,
        pref_close_tts: 0
      }
    ]);

  const removeRow = (index: number) =>
    setStaffRows((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev));

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

  const handleLoadConfig = async () => {
    if (!selectedConfig) return;
    try {
      const cfg: ConfigPayload = await loadConfig(selectedConfig);
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
          id: String(row.id ?? ""),
          name: String(row.name ?? ""),
          role: String(row.role ?? "Tech") || "Tech",
          can_bleach: Boolean(row.can_bleach ?? false),
          can_open: Boolean(row.can_open ?? false),
          can_close: Boolean(row.can_close ?? false),
          availability: DAYS.reduce<Record<string, boolean>>((acc, day) => {
            acc[day] = Boolean(row[day] ?? row?.availability?.[day] ?? true);
            return acc;
          }, {}),
          pref_open_mwf: Number(row.pref_open_mwf ?? row.open_mwf ?? 0),
          pref_open_tts: Number(row.pref_open_tts ?? row.open_tts ?? 0),
          pref_mid_mwf: Number(row.pref_mid_mwf ?? row.mid_mwf ?? 0),
          pref_mid_tts: Number(row.pref_mid_tts ?? row.mid_tts ?? 0),
          pref_close_mwf: Number(row.pref_close_mwf ?? row.close_mwf ?? 0),
          pref_close_tts: Number(row.pref_close_tts ?? row.close_tts ?? 0)
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
      setStatus(`Loaded config: ${selectedConfig}`);
    } catch (err: any) {
      setStatus(`Failed to load: ${err?.message ?? err}`);
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
      staff: staffRows,
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
      setStatus(`Failed to save: ${err?.message ?? err}`);
    }
  };

  const handleLogin = async () => {
    try {
      const res = await login(loginUser, loginPass);
      setAuthTokenState(res.token);
      setAuthToken(res.token);
      setLoginError("");
      setStatus("Logged in.");
    } catch (err: any) {
      setAuthTokenState(null);
      setAuthToken(null);
      setLoginError(err?.message ?? "Login failed");
      setStatus("Login failed");
    }
  };

  const handleLogout = () => {
    setAuthTokenState(null);
    setAuthToken(null);
    setStatus("Logged out.");
    setConfigs([]);
  };

  if (!isAuthed) {
    return (
      <section className="card">
        <h2>Staff Planner (React prototype)</h2>
        <p>{status}</p>
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h4>Login</h4>
          <div className="stack">
            <label>
              Username
              <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} />
            </label>
            <label>
              Password
              <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} />
            </label>
          </div>
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
            <button onClick={handleLogin}>Login</button>
          </div>
          {loginError && <p style={{ color: "#b45309" }}>{loginError}</p>}
          {!isAuthed && <p style={{ color: "#b45309" }}>Login required to edit and run.</p>}
        </div>
      </section>
    );
  }

  return (
    <section className="card">
      <h2>Staff Planner (React prototype)</h2>
      <p>{status}</p>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.75rem", gap: "0.5rem" }}>
        <span className="muted">{authToken ? "Authenticated" : "Not authenticated"}</span>
        {authToken && (
          <button className="secondary-btn" onClick={handleLogout}>
            Logout
          </button>
        )}
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
        <button onClick={handleLoadConfig} disabled={!selectedConfig}>
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
      <div className="tabs">
        {[
          { key: "staff", label: "Staff" },
          { key: "avail", label: "Availability" },
          { key: "prefs", label: "Prefs" },
          { key: "demand", label: "Demand" },
          { key: "pto", label: "PTO" },
          { key: "run", label: "Run" }
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
          {staffWarnings.length > 0 && (
            <ul style={{ color: "#b45309" }}>
              {staffWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
          <table cellPadding={8} style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">ID</th>
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
                    <input value={row.id} onChange={(e) => updateRow(index, "id", e.target.value)} />
                  </td>
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
        </>
      )}

      {activeTab === "prefs" && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>Preference Weights</h3>
          <p className="muted">Lower = prefers, higher = dislikes. Separate values for MWF vs TTS. Range -5 to 5, step 0.25.</p>
          {staffRows.map((row, idx) => (
            <div key={idx} style={{ borderBottom: "1px solid #e2e8f0", paddingBottom: "0.75rem", marginBottom: "0.75rem" }}>
              <strong>{row.name || row.id || `Staff ${idx + 1}`}</strong> ({row.role || "Tech"})
              <div className="stack">
                <label>
                  Open MWF
                  <input
                    type="number"
                    min={-5}
                    max={5}
                    step={0.25}
                    value={row.pref_open_mwf ?? 1}
                    onChange={(e) =>
                      setStaffRows((prev) => {
                        const next = [...prev];
                        next[idx] = { ...next[idx], pref_open_mwf: Number(e.target.value) || 0 };
                        return next;
                      })
                    }
                  />
                </label>
                <label>
                  Open TTS
                  <input
                    type="number"
                    min={-5}
                    max={5}
                    step={0.25}
                    value={row.pref_open_tts ?? 0}
                    onChange={(e) =>
                      setStaffRows((prev) => {
                        const next = [...prev];
                        next[idx] = { ...next[idx], pref_open_tts: Number(e.target.value) || 0 };
                        return next;
                      })
                    }
                  />
                </label>
                <label>
                  Mid MWF
                  <input
                    type="number"
                    min={-5}
                    max={5}
                    step={0.25}
                    value={row.pref_mid_mwf ?? 0}
                    onChange={(e) =>
                      setStaffRows((prev) => {
                        const next = [...prev];
                        next[idx] = { ...next[idx], pref_mid_mwf: Number(e.target.value) || 0 };
                        return next;
                      })
                    }
                  />
                </label>
                <label>
                  Mid TTS
                  <input
                    type="number"
                    min={-5}
                    max={5}
                    step={0.25}
                    value={row.pref_mid_tts ?? 0}
                    onChange={(e) =>
                      setStaffRows((prev) => {
                        const next = [...prev];
                        next[idx] = { ...next[idx], pref_mid_tts: Number(e.target.value) || 0 };
                        return next;
                      })
                    }
                  />
                </label>
                <label>
                  Close MWF
                  <input
                    type="number"
                    min={-5}
                    max={5}
                    step={0.25}
                    value={row.pref_close_mwf ?? 0}
                    onChange={(e) =>
                      setStaffRows((prev) => {
                        const next = [...prev];
                        next[idx] = { ...next[idx], pref_close_mwf: Number(e.target.value) || 0 };
                        return next;
                      })
                    }
                  />
                </label>
                <label>
                  Close TTS
                  <input
                    type="number"
                    min={-5}
                    max={5}
                    step={0.25}
                    value={row.pref_close_tts ?? 0}
                    onChange={(e) =>
                      setStaffRows((prev) => {
                        const next = [...prev];
                        next[idx] = { ...next[idx], pref_close_tts: Number(e.target.value) || 0 };
                        return next;
                      })
                    }
                  />
                </label>
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
                  <td>{row.name || row.id || `Staff ${idx + 1}`}</td>
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
        </div>
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
            staffOptions={staffRows.filter((s) => s.id.trim()).map((s) => ({ id: s.id, name: s.name || s.id }))}
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
                return;
              }
              try {
                setIsRunning(true);
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
                    open_mwf: s.pref_open_mwf ?? 0,
                    open_tts: s.pref_open_tts ?? 0,
                    mid_mwf: s.pref_mid_mwf ?? 0,
                    mid_tts: s.pref_mid_tts ?? 0,
                    close_mwf: s.pref_close_mwf ?? 0,
                    close_tts: s.pref_close_tts ?? 0
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
                setStatus(`Run failed: ${err?.message ?? err}`);
                setRunResult("");
              } finally {
                setIsRunning(false);
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
      </div>
    </section>
  );
}
