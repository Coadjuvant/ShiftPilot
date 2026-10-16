import { DAYS } from "../constants";

export type ConstraintsState = {
  threeDayWeight: number;
  altSatWeight: number;
  techFourWeight: number;
  rnFourWeight: number;
  postBleachWeight: number;
};

export type BleachState = {
  day: string;
  frequency: string;
  cursor: number;
  rotation: string[];
};

type Props = {
  state: ConstraintsState;
  onChange: (next: ConstraintsState) => void;
  bleachState: BleachState;
  onBleachChange: (next: BleachState) => void;
  staffNameMap: Record<string, string>;
  availableBleachIds: string[];
};

export default function ConstraintsEditor({ state, onChange, bleachState, onBleachChange, staffNameMap, availableBleachIds }: Props) {
  const { threeDayWeight, altSatWeight, techFourWeight, rnFourWeight, postBleachWeight } = state;
  const { day, frequency, cursor, rotation } = bleachState;

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Scheduling rules</h3>
      <p className="muted small-note">
        Set the importance of each constraint. 0 = ignore, 1–9 = soft penalty, 10 = hard stop.
      </p>
      <div className="constraint-stack">
        {([
          ["threeDayWeight", "Maximum three consecutive days", threeDayWeight],
          ["altSatWeight", "Alternate Saturdays", altSatWeight],
          ["techFourWeight", "Tech: maximum four days per week", techFourWeight],
          ["rnFourWeight", "RN: maximum four days per week", rnFourWeight],
          ["postBleachWeight", "Rest day after bleach duty", postBleachWeight]
        ] as const).map(([key, label, weight]) => <div className="constraint-field" key={key}>
          <label htmlFor={`rule-${key}`}>{label}</label>
          <div className="constraint-control">
            <select id={`rule-${key}`} value={weight === 0 ? "off" : weight === 10 ? "required" : "prefer"}
              onChange={e => onChange({ ...state, [key]: e.target.value === "off" ? 0 : e.target.value === "required" ? 10 : 5 })}>
              <option value="off">Off</option><option value="prefer">Prefer</option><option value="required">Required</option>
            </select>
            {weight > 0 && weight < 10 && <label>Preference strength
              <input aria-label={`${label}: preference strength`} type="number" min={1} max={9} value={weight}
                onChange={e => onChange({ ...state, [key]: Math.max(1, Math.min(9, Number(e.target.value) || 1)) })} />
            </label>}
          </div>
        </div>)}
      </div>

      <h3 style={{ marginTop: "2rem" }}>Bleach Planning</h3>
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
            onChange={(e) => onBleachChange({ ...bleachState, day: e.target.value })}
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
            onChange={(e) => onBleachChange({ ...bleachState, frequency: e.target.value })}
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
            onChange={(e) => onBleachChange({ ...bleachState, cursor: Number(e.target.value) })}
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
                onBleachChange({ ...bleachState, rotation: [...rotation, sid] });
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
              onClick={() => onBleachChange({ ...bleachState, rotation: [] })}
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
                  onBleachChange({ ...bleachState, rotation: next });
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
                  onBleachChange({ ...bleachState, rotation: next });
                }}
                disabled={idx === rotation.length - 1}
              >
                Move down
              </button>
              <button
                className="secondary-btn"
                onClick={() => onBleachChange({ ...bleachState, rotation: rotation.filter((_, i) => i !== idx) })}
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
