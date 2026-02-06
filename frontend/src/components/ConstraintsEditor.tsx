export type ConstraintsState = {
  threeDayWeight: number;
  altSatWeight: number;
  techFourWeight: number;
  rnFourWeight: number;
  postBleachWeight: number;
};

type Props = {
  state: ConstraintsState;
  onChange: (next: ConstraintsState) => void;
};

export default function ConstraintsEditor({ state, onChange }: Props) {
  const { threeDayWeight, altSatWeight, techFourWeight, rnFourWeight, postBleachWeight } = state;

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
    </div>
  );
}
