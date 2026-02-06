import { StaffRow } from "../types";
import { DAYS } from "../constants";

type Props = {
  rows: StaffRow[];
  onChange: (next: StaffRow[]) => void;
};

export default function StaffEditor({ rows, onChange }: Props) {
  const genId = () => {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    return Math.random().toString(36).slice(2, 10);
  };

  const defaultAvailability = DAYS.reduce<Record<string, boolean>>((acc, day) => {
    acc[day] = true;
    return acc;
  }, {});

  const addRow = () =>
    onChange([
      ...rows,
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
    onChange(rows.length > 1 ? rows.filter((_, i) => i !== index) : rows);

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Staff Management</h3>
      {rows.length === 0 ? (
        <p className="muted">No staff members yet. Add your first staff member to begin.</p>
      ) : (
        <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
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
            {rows.map((row, index) => (
            <tr key={index}>
                <td>
                  <input
                    id={`staff-name-${index}`}
                    name={`staff-name-${index}`}
                    placeholder="Staff name"
                    value={row.name}
                    onChange={(e) =>
                      onChange(rows.map((r, i) => (i === index ? { ...r, name: e.target.value } : r)))
                    }
                  />
                </td>
                <td>
                  <select
                    id={`staff-role-${index}`}
                    name={`staff-role-${index}`}
                    value={row.role}
                    onChange={(e) =>
                      onChange(rows.map((r, i) => (i === index ? { ...r, role: e.target.value } : r)))
                    }
                  >
                    <option value="Tech">Tech</option>
                    <option value="RN">RN</option>
                    <option value="Admin">Admin</option>
                  </select>
                </td>
                <td>
                  <input
                    type="checkbox"
                    id={`staff-can-open-${index}`}
                    name={`staff-can-open-${index}`}
                    checked={row.can_open ?? false}
                    onChange={(e) =>
                      onChange(rows.map((r, i) => (i === index ? { ...r, can_open: e.target.checked } : r)))
                    }
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    id={`staff-can-close-${index}`}
                    name={`staff-can-close-${index}`}
                    checked={row.can_close ?? false}
                    onChange={(e) =>
                      onChange(rows.map((r, i) => (i === index ? { ...r, can_close: e.target.checked } : r)))
                    }
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    id={`staff-can-bleach-${index}`}
                    name={`staff-can-bleach-${index}`}
                    checked={row.can_bleach ?? false}
                    onChange={(e) =>
                      onChange(rows.map((r, i) =>
                        i === index
                          ? {
                              ...r,
                              can_bleach: e.target.checked,
                              can_close: e.target.checked ? true : r.can_close
                            }
                          : r
                      ))
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
        </div>
      )}
      <button style={{ marginTop: "1rem" }} onClick={addRow}>
        Add Staff Member
      </button>
    </div>
  );
}
