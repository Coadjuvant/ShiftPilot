import React from "react";

export type RunConfig = {
  configName: string;
  timezone: string;
  startDate: string;
  weeks: number;
  patientsPerTech: number;
  patientsPerRn: number;
  techsPerRn: number;
  trials: number;
  baseSeed: number;
  usePrevSeed: boolean;
  exportRoles: string[];
};

type Assignment = {
  date: string;
  day_name: string;
  role: string;
  duty: string;
  staff_id: string | null;
  notes: string[];
  slot_index: number;
  is_bleach: boolean;
};

type Props = {
  config: RunConfig;
  onConfigChange: (next: RunConfig) => void;
  isRunning: boolean;
  progress: number;
  runResult: string;
  assignments: Assignment[];
  stats: Record<string, number>;
  displayStaffMap: Record<string, string>;
  hasErrors: boolean;
  isAuthed: boolean;
  onRun: () => void;
  onDownloadExcel: () => void;
  onDownloadCsv: () => void;
  onLoadLatest: () => void;
};

export default function RunPanel({
  config,
  onConfigChange,
  isRunning,
  progress,
  runResult,
  assignments,
  stats,
  displayStaffMap,
  hasErrors,
  isAuthed,
  onRun,
  onDownloadExcel,
  onDownloadCsv,
  onLoadLatest
}: Props) {
  const { configName, timezone, startDate, weeks, patientsPerTech, patientsPerRn, techsPerRn, trials, baseSeed, usePrevSeed, exportRoles } = config;
  const [collapsedRoles, setCollapsedRoles] = React.useState<Set<string>>(new Set());

  const toggleRoleCollapse = (role: string) => {
    setCollapsedRoles(prev => {
      const next = new Set(prev);
      if (next.has(role)) {
        next.delete(role);
      } else {
        next.add(role);
      }
      return next;
    });
  };

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Run Scheduler</h3>
      <div className="stack">
        <label>
          Clinic
            <input
              id="run-clinic-name"
              name="run-clinic-name"
              placeholder="Clinic name"
              value={configName}
              onChange={(e) => onConfigChange({ ...config, configName: e.target.value })}
            />
        </label>
        <label>
          Timezone
            <input
              id="run-timezone"
              name="run-timezone"
              placeholder="UTC"
              value={timezone}
              onChange={(e) => onConfigChange({ ...config, timezone: e.target.value })}
            />
        </label>
      </div>
      <div className="stack">
        <label>
          Start date
            <input
              id="run-start-date"
              name="run-start-date"
              type="date"
              value={startDate}
              onChange={(e) => onConfigChange({ ...config, startDate: e.target.value })}
            />
        </label>
        <label>
          Weeks
            <input
              id="run-weeks"
              name="run-weeks"
              type="number"
              min={1}
              value={weeks}
              onChange={(e) => onConfigChange({ ...config, weeks: Number(e.target.value) })}
            />
        </label>
      </div>
      <div className="stack">
        <label>
          Patients/Tech
            <input
              id="ratio-patients-tech"
              name="ratio-patients-tech"
              type="number"
              min={1}
              value={patientsPerTech}
              onChange={(e) => onConfigChange({ ...config, patientsPerTech: Number(e.target.value) })}
            />
        </label>
        <label>
          Patients/RN
            <input
              id="ratio-patients-rn"
              name="ratio-patients-rn"
              type="number"
              min={1}
              value={patientsPerRn}
              onChange={(e) => onConfigChange({ ...config, patientsPerRn: Number(e.target.value) })}
            />
        </label>
        <label>
          Techs/RN
            <input
              id="ratio-techs-rn"
              name="ratio-techs-rn"
              type="number"
              min={1}
              value={techsPerRn}
              onChange={(e) => onConfigChange({ ...config, techsPerRn: Number(e.target.value) })}
            />
        </label>
        <label>
          Trials
            <input
              id="run-trials"
              name="run-trials"
              type="number"
              min={1}
              value={trials}
              onChange={(e) => onConfigChange({ ...config, trials: Number(e.target.value) })}
            />
        </label>
        <label>
          Seed (0 = random)
            <input
              id="run-seed"
              name="run-seed"
              type="number"
              min={0}
              value={baseSeed}
              onChange={(e) => onConfigChange({ ...config, baseSeed: Number(e.target.value) })}
            />
        </label>
        <label style={{ alignItems: "center" }}>
          <input
            type="checkbox"
            checked={usePrevSeed}
            onChange={(e) => onConfigChange({ ...config, usePrevSeed: e.target.checked })}
            style={{ marginRight: "6px" }}
            id="use-prev-seed"
            name="use-prev-seed"
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
                    id={`export-role-${role.toLowerCase()}`}
                    name={`export-role-${role.toLowerCase()}`}
                    checked={exportRoles.includes(role)}
                    onChange={(e) => {
                      const checked = e.target.checked;
                    onConfigChange({
                      ...config,
                      exportRoles: checked
                        ? Array.from(new Set([...exportRoles, role]))
                        : exportRoles.filter((r) => r !== role)
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
        onClick={onRun}
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
        {isAuthed && (
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button className="primary-btn" onClick={onDownloadExcel}>
              Download Latest Schedule
            </button>
            <button className="secondary-btn" onClick={onDownloadCsv}>
              Download CSV
            </button>
            <button className="secondary-btn" onClick={onLoadLatest}>
              Load Latest Schedule
            </button>
          </div>
        )}
      {assignments.length > 0 && (
        <div style={{ marginTop: "1rem", overflowX: "auto" }}>
          {(() => {
            const uniqueDates = Array.from(new Set(assignments.map((a) => a.date))).sort();
            const exportRoleSet = new Set(exportRoles.map((role) => role.toLowerCase()));
            const matrixAssignments = assignments.filter((a) => exportRoleSet.has((a.role || "").toLowerCase()));
              const knownStaffIds = new Set(Object.keys(displayStaffMap));
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
              if (!exportRoleSet.has(role.toLowerCase())) {
                acc[role] = [];
                return acc;
              }
              acc[role] = Array.from(
                new Set(
                  matrixAssignments
                    .filter((a) => a.role === role && a.staff_id && knownStaffIds.has(a.staff_id))
                    .map((a) => a.staff_id as string)
                )
              );
              return acc;
            }, {});
            const labelMapByStaff = matrixAssignments.reduce<Record<string, Record<string, string>>>((acc, a) => {
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
                  ? `Pod ${a.slot_index - 1}`
                  : a.duty;
              acc[a.staff_id][a.date] = label;
              return acc;
            }, {});
              const hasMatrix = uniqueDates.length > 0;
              const columns = uniqueDates.reduce<Array<{ key: string; date?: string; label?: string; isSeparator?: boolean }>>((acc, d) => {
                acc.push({ key: d, date: d, label: dateLabelMap[d] });
                const day = dateDayMap[d];
                if (day && day.toLowerCase().startsWith("sat")) {
                  acc.push({ key: `${d}-sep`, isSeparator: true });
                }
                return acc;
              }, []);
              if (!hasMatrix) return null;
              return (
                <div style={{ marginTop: "1rem" }}>
                  <h4>Schedule Matrix</h4>
                {["Tech", "RN", "Admin"].map((role) => {
                  const staffIds = staffIdsByRole[role] || [];
                  if (!staffIds.length) return null;
                  const isCollapsed = collapsedRoles.has(role);
                  return (
                    <div key={role} style={{ marginBottom: "1.5rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
                        <h5 style={{ margin: 0 }}>{role} ({staffIds.length})</h5>
                        <button
                          className="secondary-btn"
                          onClick={() => toggleRoleCollapse(role)}
                          style={{ padding: "0.25rem 0.75rem", fontSize: "0.85rem" }}
                        >
                          {isCollapsed ? "Expand" : "Collapse"}
                        </button>
                      </div>
                      {!isCollapsed && (
                      <table
                        cellPadding={8}
                        className="schedule-matrix"
                        style={{ minWidth: "700px", borderCollapse: "collapse", fontSize: "0.9rem" }}
                      >
                        <thead>
                          <tr>
                            <th>Staff</th>
                            {columns.map((col) =>
                              col.isSeparator ? (
                                <th key={col.key} className="matrix-sep" aria-hidden="true" />
                              ) : (
                                <th key={col.key}>{col.label}</th>
                              )
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {staffIds.map((sid) => (
                            <tr key={`${role}-${sid}`}>
                  <td>{displayStaffMap[sid] || sid}</td>
                        {columns.map((col) =>
                          col.isSeparator ? (
                            <td key={`${sid}-${col.key}`} className="matrix-sep" aria-hidden="true" />
                          ) : (
                            <td key={`${sid}-${col.key}`} style={{ textAlign: "center" }}>
                              {labelMapByStaff[sid]?.[col.date as string] || ""}
                            </td>
                          )
                        )}
                      </tr>
                    ))}
                        </tbody>
                      </table>
                      )}
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
                    <td>{displayStaffMap[k] || k}</td>
                  <td>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
