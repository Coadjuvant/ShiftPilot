import { StaffRow } from "../types";
import { DAYS } from "../constants";

type Props = {
  rows: StaffRow[];
  onChange: (next: StaffRow[]) => void;
};

export default function AvailabilityEditor({ rows, onChange }: Props) {
  const defaultAvailability = DAYS.reduce<Record<string, boolean>>((acc, day) => {
    acc[day] = true;
    return acc;
  }, {});

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Availability</h3>
      <p className="muted">Toggle the days each staffer can work.</p>
      {rows.length === 0 ? (
        <p className="muted">Add staff members in the Staff tab to set availability.</p>
      ) : (
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
            {rows.map((row, idx) => (
            <tr key={idx}>
              <td title={row.id || ""}>
                {row.name?.trim() ? row.name : "(no name set)"}
              </td>
              {DAYS.map((day) => (
                <td key={day} style={{ textAlign: "center" }}>
                    <input
                      type="checkbox"
                      id={`avail-${idx}-${day}`}
                      name={`avail-${idx}-${day}`}
                      checked={row.availability?.[day] ?? true}
                      onChange={(e) => {
                        const next = [...rows];
                        const avail = { ...(next[idx].availability ?? defaultAvailability) };
                        avail[day] = e.target.checked;
                        next[idx] = { ...next[idx], availability: avail };
                        onChange(next);
                      }}
                    />
                </td>
              ))}
            </tr>
          ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
