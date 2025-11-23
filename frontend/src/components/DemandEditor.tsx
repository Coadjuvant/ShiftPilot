import { DemandRow } from "../types";
import { DAYS } from "../constants";

type Props = {
  rows: DemandRow[];
  onChange: (next: DemandRow[]) => void;
};

export default function DemandEditor({ rows, onChange }: Props) {
  const update = (index: number, key: keyof DemandRow, value: number | string) => {
    onChange(
      rows.map((row, i) =>
        i === index
          ? {
              ...row,
              [key]:
                key === "Day" ? (value as string) : Math.max(0, Number.isNaN(Number(value)) ? 0 : Number(value))
            }
          : row
      )
    );
  };

  const ensureRowForDay = (day: string) => {
    const existing = rows.find((r) => r.Day === day);
    return (
      existing || {
        Day: day,
        Patients: 0,
        Tech_Open: 0,
        Tech_Mid: 0,
        Tech_Close: 0,
        RN_Count: 0,
        Admin_Count: 0
      }
    );
  };

  const normalized = DAYS.map((day) => ensureRowForDay(day));

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Demand Editor</h3>
      <table cellPadding={6} style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem" }}>
        <thead>
          <tr>
            <th>Day</th>
            <th>Patients</th>
            <th>Tech Open</th>
            <th>Tech Mid</th>
            <th>Tech Close</th>
            <th>RN Count</th>
            <th>Admin Count</th>
          </tr>
        </thead>
        <tbody>
          {normalized.map((row, idx) => (
            <tr key={row.Day}>
              <td>{row.Day}</td>
              <td>
                <input
                  type="number"
                  value={row.Patients}
                  onChange={(e) => update(idx, "Patients", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={row.Tech_Open}
                  onChange={(e) => update(idx, "Tech_Open", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={row.Tech_Mid}
                  onChange={(e) => update(idx, "Tech_Mid", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={row.Tech_Close}
                  onChange={(e) => update(idx, "Tech_Close", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={row.RN_Count}
                  onChange={(e) => update(idx, "RN_Count", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={row.Admin_Count}
                  onChange={(e) => update(idx, "Admin_Count", e.target.value)}
                  min={0}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
