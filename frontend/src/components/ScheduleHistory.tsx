import { useEffect, useState } from "react";
import { deleteScheduleDraft, friendlyApiError, listScheduleVersions, loadScheduleVersion, publishScheduleVersion, SavedSchedule, ScheduleVersion } from "../api/client";

type Props = {
  current: SavedSchedule | null;
  revision: number;
  onLoad: (schedule: SavedSchedule) => void;
  onPublished: () => void;
  hasEdits: boolean;
  publishedId?: string;
  onDeleted?: (id: string) => void;
};

export default function ScheduleHistory({ current, revision, onLoad, onPublished, hasEdits, publishedId, onDeleted }: Props) {
  const [versions, setVersions] = useState<ScheduleVersion[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");
  const [publishReview, setPublishReview] = useState(false);
  const [deleteReview, setDeleteReview] = useState(false);
  const selectedVersion = versions.find(v => v.id === selected);
  const deleteTarget = selectedVersion
    ? {id: selectedVersion.id, state: selectedVersion.state, clinic_name: selectedVersion.clinic_name, start_date: selectedVersion.start_date}
    : current?.version_id === selected
      ? {id: current.version_id, state: current.schedule_status, clinic_name: current.clinic_name, start_date: current.start_date}
      : null;
  const canDelete = deleteTarget?.state === "draft" && deleteTarget.id !== publishedId;
  const refresh = async () => {
    try { setVersions(await listScheduleVersions()); setError(""); }
    catch (err) { setError(friendlyApiError(err, "Could not load schedule history.")); }
  };
  useEffect(() => { void refresh(); }, [revision]);
  useEffect(() => { setSelected(current?.version_id || ""); setDeleteReview(false); setPublishReview(false); }, [current?.version_id]);
  const deleteDraft = async () => {
    if (!deleteTarget || !canDelete) return;
    const id = deleteTarget.id;
    setBusy(true);
    setError("");
    try {
      await deleteScheduleDraft(id);
      setDeleteReview(false);
      setSelected("");
      onDeleted?.(id);
      await refresh();
    } catch (err) { setError(friendlyApiError(err, "Could not delete this draft.")); }
    finally { setBusy(false); }
  };
  const act = async (publish: boolean, confirmed = false) => {
    const id = publish ? current?.version_id : selected;
    if (!id) return;
    if (!publish && hasEdits && !window.confirm("Discard unsaved assignment edits and open another version?")) return;
    if (publish && !confirmed) { setPublishReview(true); return; }
    setBusy(true);
    try {
      onLoad(publish ? await publishScheduleVersion(id) : await loadScheduleVersion(id));
      if (publish) onPublished();
      setPublishReview(false);
      await refresh();
    } catch (err) { setError(friendlyApiError(err, "Could not update this schedule.")); }
    finally { setBusy(false); }
  };
  return <section className="card schedule-history" aria-label="Schedule history">
    <div className="section-heading"><div><h3>Schedule history</h3><p className="muted">Generation saves a draft. Your published roster changes only when you publish.</p></div>
      {current && <span className={`pill ${current.schedule_status === "published" ? "success" : "subtle"}`}>{current.version_id === publishedId ? "Current published roster" : current.schedule_status === "published" ? "Published previously" : "Draft"}</span>}
    </div>
    <div className="controls-row">
      <label>Saved versions<select aria-label="Saved schedule versions" value={selected} disabled={busy} onChange={e => { setSelected(e.target.value); setDeleteReview(false); }}>
        <option value="">Choose a version…</option>
        {versions.map(v => <option key={v.id} value={v.id}>{v.clinic_name} · {v.start_date} · {new Date(v.created_at).toLocaleString()} · {v.state === "published" ? "Published previously" : "Draft"}</option>)}
      </select></label>
      <button disabled={!selected || busy} onClick={() => void act(false)}>Open version</button>
      <button disabled={!current?.version_id || current.version_id === publishedId || busy || hasEdits} onClick={() => void act(true)}>{current?.schedule_status === "published" ? "Publish this version" : "Publish draft"}</button>
      <button className="secondary-btn" disabled={busy || !canDelete} onClick={() => { setPublishReview(false); setDeleteReview(true); }}>Delete draft</button>
    </div>
    {current && <p>Viewing {current.clinic_name} · {current.start_date} · {current.weeks} week{current.weeks === 1 ? "" : "s"}.</p>}
    {deleteReview && <div className="recovery-notice" role="alert">
      <p>Delete the selected draft for {deleteTarget?.clinic_name}, starting {deleteTarget?.start_date}? This cannot be undone. Your published schedule will stay unchanged.</p>
      {hasEdits && deleteTarget?.id === current?.version_id && <p>Unsaved assignment edits to this draft will also be discarded.</p>}
      <button disabled={busy} onClick={() => void deleteDraft()}>Confirm delete draft</button>
      <button className="secondary-btn" disabled={busy} onClick={() => setDeleteReview(false)}>Cancel</button>
    </div>}
    {publishReview && !deleteReview && <div className="recovery-notice" role="alert">
      <p>Publish the viewed roster for {current?.clinic_name}, starting {current?.start_date}? It will become the current published schedule. Previous versions remain in history.</p>
      <p>{current?.assignments.filter(a => !a.staff_id || ["FLOAT", "OPEN"].includes(a.staff_id.toUpperCase())).length || 0} slots still need coverage.</p>
      <button disabled={busy || hasEdits} onClick={() => void act(true, true)}>Confirm publish</button>
      <button className="secondary-btn" disabled={busy} onClick={() => setPublishReview(false)}>Cancel</button>
    </div>}
    {versions.length === 0 && <p className="muted">No saved versions yet. Generate your first draft below.</p>}
    {error && <p role="alert" className="status error">{error}</p>}
  </section>;
}
