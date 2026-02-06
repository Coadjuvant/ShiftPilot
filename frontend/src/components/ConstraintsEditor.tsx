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
      <h3>Scheduling Constraints</h3>
      <p className="muted small-note">
        Set the importance of each constraint. 0 = ignore, 1–9 = soft penalty, 10 = hard stop.
      </p>
      <div className="constraint-stack">
        <label className="constraint-field">
          3-day streak cap
          <div className="constraint-control">
            <input
              id="constraint-three-day"
              name="constraint-three-day"
              type="range"
              min={0}
              max={10}
              step={1}
              value={threeDayWeight}
              onChange={(e) => onChange({ ...state, threeDayWeight: Number(e.target.value) })}
            />
            <span className="constraint-value">{threeDayWeight}</span>
          </div>
        </label>
        <label className="constraint-field">
          No consecutive Saturdays
          <div className="constraint-control">
            <input
              id="constraint-alt-sat"
              name="constraint-alt-sat"
              type="range"
              min={0}
              max={10}
              step={1}
              value={altSatWeight}
              onChange={(e) => onChange({ ...state, altSatWeight: Number(e.target.value) })}
            />
            <span className="constraint-value">{altSatWeight}</span>
          </div>
        </label>
        <label className="constraint-field">
          Tech 4-day cap
          <div className="constraint-control">
            <input
              id="constraint-tech-four"
              name="constraint-tech-four"
              type="range"
              min={0}
              max={10}
              step={1}
              value={techFourWeight}
              onChange={(e) => onChange({ ...state, techFourWeight: Number(e.target.value) })}
            />
            <span className="constraint-value">{techFourWeight}</span>
          </div>
        </label>
        <label className="constraint-field">
          RN 4-day cap
          <div className="constraint-control">
            <input
              id="constraint-rn-four"
              name="constraint-rn-four"
              type="range"
              min={0}
              max={10}
              step={1}
              value={rnFourWeight}
              onChange={(e) => onChange({ ...state, rnFourWeight: Number(e.target.value) })}
            />
            <span className="constraint-value">{rnFourWeight}</span>
          </div>
        </label>
        <label className="constraint-field">
          Post-bleach rest day
          <div className="constraint-control">
            <input
              id="constraint-post-bleach"
              name="constraint-post-bleach"
              type="range"
              min={0}
              max={10}
              step={1}
              value={postBleachWeight}
              onChange={(e) => onChange({ ...state, postBleachWeight: Number(e.target.value) })}
            />
            <span className="constraint-value">{postBleachWeight}</span>
          </div>
        </label>
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
