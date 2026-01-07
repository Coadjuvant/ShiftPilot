import { PTORow } from "../types";

type Props = {
  rows: PTORow[];
  onChange: (next: PTORow[]) => void;
  staffOptions?: Array<{ id: string; name: string }>;
  scheduleStart?: string;
  scheduleEnd?: string;
};

export default function PTOEditor({ rows, onChange, staffOptions = [], scheduleStart, scheduleEnd }: Props) {
  const addForStaff = (staff_id: string) => {
    const suggestedStart = scheduleStart ?? "";
    onChange([...rows, { staff_id, start_date: suggestedStart, end_date: suggestedStart }]);
  };

  const updateRow = (index: number, key: keyof PTORow, value: string) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  };

  const removeRow = (index: number) => onChange(rows.filter((_, i) => i !== index));

  const knownIds = new Set(staffOptions.map((s) => s.id));
  const grouped = staffOptions.map((s) => ({
    staff: s,
    entries: rows
      .map((row, idx) => ({ ...row, __idx: idx }))
      .filter((r) => r.staff_id === s.id)
  }));

  const unassigned = rows
    .map((row, idx) => ({ ...row, __idx: idx }))
    .filter((r) => !r.staff_id || !knownIds.has(r.staff_id));

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>PTO</h3>
      <p className="muted">Add PTO per staff member. Dates can be single day or ranges.</p>
      {grouped.map(({ staff, entries }) => (
        <div key={staff.id || staff.name} style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <strong>{staff.name || "(no name set)"}</strong>
            {staff.id && (
              <button className="secondary-btn" onClick={() => addForStaff(staff.id)}>
                Add PTO
              </button>
            )}
          </div>
          {entries.length === 0 && <p className="muted">No PTO entries.</p>}
          {entries.length > 0 && (
            <table cellPadding={6} style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem" }}>
              <thead>
                <tr>
                  <th>Start</th>
                  <th>End</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {entries.map((row) => (
                  <tr key={row.__idx}>
                    <td>
                      <input
                        type="date"
                        id={`pto-${row.__idx}-start`}
                        name={`pto-${row.__idx}-start`}
                        min={scheduleStart}
                        max={scheduleEnd}
                        value={row.start_date}
                        onChange={(e) => updateRow(row.__idx!, "start_date", e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        type="date"
                        id={`pto-${row.__idx}-end`}
                        name={`pto-${row.__idx}-end`}
                        min={scheduleStart}
                        max={scheduleEnd}
                        value={row.end_date}
                        onChange={(e) => updateRow(row.__idx!, "end_date", e.target.value)}
                      />
                    </td>
                    <td>
                      <button className="secondary-btn" onClick={() => removeRow(row.__idx!)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
      {unassigned.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <strong>Unassigned PTO</strong>
          </div>
          <table cellPadding={6} style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem" }}>
            <thead>
              <tr>
                <th>Staff</th>
                <th>Start</th>
                <th>End</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {unassigned.map((row) => (
                <tr key={row.__idx}>
                  <td>
                    <select
                      id={`pto-${row.__idx}-staff`}
                      name={`pto-${row.__idx}-staff`}
                      value={row.staff_id}
                      onChange={(e) => updateRow(row.__idx!, "staff_id", e.target.value)}
                    >
                      <option value="">Select staff...</option>
                      {staffOptions.map((opt) => (
                        <option key={opt.id} value={opt.id}>
                          {opt.name || "(no name set)"}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="date"
                      id={`pto-${row.__idx}-start`}
                      name={`pto-${row.__idx}-start`}
                      min={scheduleStart}
                      max={scheduleEnd}
                      value={row.start_date}
                      onChange={(e) => updateRow(row.__idx!, "start_date", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      type="date"
                      id={`pto-${row.__idx}-end`}
                      name={`pto-${row.__idx}-end`}
                      min={scheduleStart}
                      max={scheduleEnd}
                      value={row.end_date}
                      onChange={(e) => updateRow(row.__idx!, "end_date", e.target.value)}
                    />
                  </td>
                  <td>
                    <button className="secondary-btn" onClick={() => removeRow(row.__idx!)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
