import { StaffRow } from "../types";

type Props = {
  rows: StaffRow[];
  onChange: (next: StaffRow[]) => void;
};

export default function PrefsEditor({ rows, onChange }: Props) {
  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Preference Weights</h3>
      <p className="muted">Lower values avoid (0), higher values prefer (10), 5 is neutral. Set separately for MWF vs TTS.</p>
      {rows.length === 0 ? (
        <p className="muted">Add staff members in the Staff tab to set preferences.</p>
      ) : (
        rows.map((row, idx) => (
        <div
          key={idx}
          style={{
            border: "1px solid #e2e8f0",
            borderRadius: "10px",
            padding: "0.75rem",
            marginBottom: "1.25rem",
            background: "rgba(255,255,255,0.02)"
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
              <label key={item.key} className="constraint-field">
                {item.label}
                <div className="constraint-control">
                  <input
                    type="range"
                    id={`pref-${item.key}-${idx}-range`}
                    name={`pref-${item.key}-${idx}-range`}
                    min={0}
                    max={10}
                    step={0.25}
                    value={item.value}
                    onChange={(e) => {
                      const next = [...rows];
                      next[idx] = { ...next[idx], [item.key]: Number(e.target.value) || 5 } as any;
                      onChange(next);
                    }}
                  />
                  <span className="constraint-value">{item.value}</span>
                </div>
              </label>
            ))}
          </div>
        </div>
      ))
      )}
    </div>
  );
}
