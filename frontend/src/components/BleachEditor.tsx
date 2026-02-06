import { DAYS } from "../constants";

export type BleachState = {
  day: string;
  frequency: string;
  cursor: number;
  rotation: string[];
};

type Props = {
  state: BleachState;
  onChange: (next: BleachState) => void;
  staffNameMap: Record<string, string>;
  availableBleachIds: string[];
};

export default function BleachEditor({ state, onChange, staffNameMap, availableBleachIds }: Props) {
  const { day, frequency, cursor, rotation } = state;

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Bleach planning</h3>
      <p className="muted">
        Weekly runs use your chosen bleach day. Quarterly runs schedule bleach on the second week of Feb, May, Aug, and Nov.
      </p>
      <div className="stack">
          <label>
            Bleach day
            <select
              id="bleach-day"
              name="bleach-day"
              value={day}
              onChange={(e) => onChange({ ...state, day: e.target.value })}
            >
            {DAYS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
          <label>
            Bleach frequency
            <select
              id="bleach-frequency"
              name="bleach-frequency"
              value={frequency}
              onChange={(e) => onChange({ ...state, frequency: e.target.value })}
            >
            <option value="weekly">Weekly</option>
            <option value="quarterly">Quarterly</option>
          </select>
        </label>
          <label>
            Bleach rotation position
            <input
              type="number"
              id="bleach-rotation-position"
              name="bleach-rotation-position"
              min={0}
              value={cursor}
              onChange={(e) => onChange({ ...state, cursor: Number(e.target.value) })}
            />
          </label>
      </div>
      <div className="stack" style={{ alignItems: "flex-start" }}>
        <div style={{ minWidth: "280px" }}>
          <p style={{ margin: "0 0 4px 0" }}>Bleach rotation (ordered)</p>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <select
                id="bleach-rotation-add"
                name="bleach-rotation-add"
                value=""
                onChange={(e) => {
                  const sid = e.target.value;
                  if (!sid) return;
                onChange({ ...state, rotation: [...rotation, sid] });
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
              onClick={() => onChange({ ...state, rotation: [] })}
              disabled={rotation.length === 0}
            >
              Clear
            </button>
          </div>
          {rotation.length === 0 && <p className="muted">No bleach rotation set.</p>}
          {rotation.map((sid, idx) => (
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
                onClick={() => {
                  const next = [...rotation];
                  if (idx > 0) [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
                  onChange({ ...state, rotation: next });
                }}
                disabled={idx === 0}
              >
                Move up
              </button>
              <button
                className="secondary-btn"
                onClick={() => {
                  const next = [...rotation];
                  if (idx < next.length - 1) [next[idx + 1], next[idx]] = [next[idx], next[idx + 1]];
                  onChange({ ...state, rotation: next });
                }}
                disabled={idx === rotation.length - 1}
              >
                Move down
              </button>
              <button
                className="secondary-btn"
                onClick={() => onChange({ ...state, rotation: rotation.filter((_, i) => i !== idx) })}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>
      <p className="muted">Cursor advances after a bleach assignment; PTO will skip to the next person.</p>
    </div>
  );
}
