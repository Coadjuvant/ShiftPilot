import { useEffect, useState } from "react";
import { adjustScheduleVersion, friendlyApiError, loadScheduleVersion, regenerateScheduleVersion, SavedAssignment, SavedSchedule } from "../api/client";

type Props = { current: SavedSchedule | null; onLoad: (schedule: SavedSchedule) => void; onDirty: (dirty: boolean) => void };

export default function AssignmentEditor({ current, onLoad, onDirty }: Props) {
  const [rows, setRows] = useState<SavedAssignment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setRows(current?.assignments || []); setError(""); }, [current]);
  const dirty = JSON.stringify(rows) !== JSON.stringify(current?.assignments || []);
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  if (!current?.version_id || !current.inputs) return null;
  const save = async (regenerate: boolean) => {
    if (regenerate && dirty && !window.confirm("Discard your unsaved assignment edits and regenerate from the saved version?")) return;
    setBusy(true); setError("");
    try {
      const response = regenerate ? await regenerateScheduleVersion(current.version_id!) : await adjustScheduleVersion(current.version_id!, rows);
      onLoad(await loadScheduleVersion(response.version_id));
    } catch (err) { setError(friendlyApiError(err, "Could not save these assignments.")); }
    finally { setBusy(false); }
  };
  return <section className="card assignment-editor" aria-label="Assignment adjustments">
    <h3>Adjust assignments</h3>
    <p className="muted">Edits create a new draft. Availability, time off, staff capabilities, and required rules are checked before saving. Locks are preserved when you regenerate this version.</p>
    <details><summary>Edit staff assignments and locks{dirty ? " · Unsaved edits" : ""}</summary>
      <div className="table-scroll"><table><thead><tr><th>Date</th><th>Role / duty</th><th>Staff member</th><th>Keep when regenerating</th></tr></thead><tbody>
        {rows.map((row, index) => <tr key={`${row.date}-${row.role}-${row.duty}-${row.slot_index}`}>
          <td>{row.date}</td><td>{row.role} · {row.duty} {row.slot_index > 1 ? row.slot_index : ""}</td>
          <td><select aria-label={`${row.date} ${row.role} ${row.duty} ${row.slot_index}: assigned staff`} value={row.staff_id || "FLOAT"}
            onChange={e => setRows(old => old.map((item, i) => i === index ? { ...item, staff_id: e.target.value } : item))}>
            <option value="FLOAT">Needs coverage</option>
            {(current.staff || []).filter(person => person.role === row.role).map(person => <option key={person.id} value={person.id}>{person.name}</option>)}
          </select></td>
          <td><input type="checkbox" aria-label={`Lock ${row.date} ${row.role} ${row.duty} ${row.slot_index}`} checked={Boolean(row.is_locked)}
            onChange={e => setRows(old => old.map((item, i) => i === index ? { ...item, is_locked: e.target.checked } : item))} /></td>
        </tr>)}
      </tbody></table></div>
    </details>
    <div className="controls-row"><button disabled={busy || !dirty} onClick={() => void save(false)}>Save adjustments as draft</button>
      <button disabled={busy} onClick={() => void save(true)}>Regenerate unlocked assignments</button>
      {dirty && <span role="status">Save assignment edits before publishing.</span>}
    </div>
    {error && <p className="status error" role="alert">{error}</p>}
  </section>;
}
