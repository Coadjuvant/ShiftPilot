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
      <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
      <table cellPadding={6} style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem" }}>
        <thead>
          <tr>
            <th rowSpan={2}>Day</th>
            <th rowSpan={2}>Patients</th>
            <th colSpan={3} style={{ borderLeft: "2px solid rgba(12, 75, 223, 0.2)", borderRight: "2px solid rgba(12, 75, 223, 0.2)", textAlign: "center" }}>Tech Shifts</th>
            <th rowSpan={2}>RN Count</th>
            <th rowSpan={2}>Admin Count</th>
          </tr>
          <tr>
            <th style={{ borderLeft: "2px solid rgba(12, 75, 223, 0.2)" }}>Open</th>
            <th>Mid</th>
            <th style={{ borderRight: "2px solid rgba(12, 75, 223, 0.2)" }}>Close</th>
          </tr>
        </thead>
        <tbody>
          {normalized.map((row, idx) => (
            <tr key={row.Day}>
              <td><strong>{row.Day}</strong></td>
              <td>
                <input
                  type="number"
                  id={`demand-${row.Day}-patients`}
                  name={`demand-${row.Day}-patients`}
                  placeholder="0"
                  value={row.Patients}
                  onChange={(e) => update(idx, "Patients", e.target.value)}
                  min={0}
                />
              </td>
              <td style={{ borderLeft: "2px solid rgba(12, 75, 223, 0.2)" }}>
                <input
                  type="number"
                  id={`demand-${row.Day}-tech-open`}
                  name={`demand-${row.Day}-tech-open`}
                  placeholder="0"
                  value={row.Tech_Open}
                  onChange={(e) => update(idx, "Tech_Open", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  id={`demand-${row.Day}-tech-mid`}
                  name={`demand-${row.Day}-tech-mid`}
                  placeholder="0"
                  value={row.Tech_Mid}
                  onChange={(e) => update(idx, "Tech_Mid", e.target.value)}
                  min={0}
                />
              </td>
              <td style={{ borderRight: "2px solid rgba(12, 75, 223, 0.2)" }}>
                <input
                  type="number"
                  id={`demand-${row.Day}-tech-close`}
                  name={`demand-${row.Day}-tech-close`}
                  placeholder="0"
                  value={row.Tech_Close}
                  onChange={(e) => update(idx, "Tech_Close", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  id={`demand-${row.Day}-rn-count`}
                  name={`demand-${row.Day}-rn-count`}
                  placeholder="0"
                  value={row.RN_Count}
                  onChange={(e) => update(idx, "RN_Count", e.target.value)}
                  min={0}
                />
              </td>
              <td>
                <input
                  type="number"
                  id={`demand-${row.Day}-admin-count`}
                  name={`demand-${row.Day}-admin-count`}
                  placeholder="0"
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
    </div>
  );
}
