import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { fetchLatestSchedule, SavedSchedule } from "../api/client";

const IconCalendar = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <rect x="4" y="5" width="16" height="15" rx="3" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <path d="M8 3v4M16 3v4M4 10h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <rect x="8" y="12.5" width="3" height="3" rx="0.75" fill="currentColor" />
    <rect x="13" y="12.5" width="3" height="3" rx="0.75" fill="currentColor" opacity="0.65" />
  </svg>
);

const IconShield = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      d="M12 21s7-3.5 7-9.5V6.5L12 3 5 6.5V11.5C5 17.5 12 21 12 21Z"
      stroke="currentColor"
      strokeWidth="1.5"
      fill="none"
      strokeLinejoin="round"
    />
    <path d="M9.5 12.25 11 13.75l3.75-3.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const IconExport = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M7 14.5 12 9l5 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M12 9v11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M5.5 4h13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M5.5 4h13V8.5H5.5z" fill="currentColor" opacity="0.14" />
  </svg>
);

const IconChevronLeft = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M15 19 8 12l7-7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const IconChevronRight = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="m9 5 7 7-7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const steps = [
  {
    title: "Set your guardrails",
    body: "Define shifts, chair coverage, weekend rotations, and PTO rules once. Keep the clinic rules as the source of truth.",
  },
  {
    title: "Import and adjust staff",
    body: "Bring in RN/Tech teams, mark availability and preferences, then lock fixed assignments that should never move.",
  },
  {
    title: "Generate and refine",
    body: "Run the planner, resolve conflicts fast, and export clean schedules for floor teams and leadership.",
  },
];

export default function Landing() {
  const [latestSchedule, setLatestSchedule] = useState<SavedSchedule | null>(null);
  const [weekIndex, setWeekIndex] = useState(0);
  const [scheduleError, setScheduleError] = useState<string>("");

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    if (!token) {
      setLatestSchedule(null);
      return;
    }
    fetchLatestSchedule()
      .then((data) => {
        setLatestSchedule(data);
        setScheduleError("");
        setWeekIndex(0);
      })
      .catch((err) => {
        setLatestSchedule(null);
        setScheduleError(err?.response?.status === 404 ? "No saved schedule yet" : "Unable to load latest schedule");
      });
  }, []);

  const weeksData = useMemo(() => {
    if (!latestSchedule) return [];
    const reqs = latestSchedule.requirements || [];
    if (!reqs.length) return [];
    const totalDays = (latestSchedule.weeks || 0) * reqs.length;
    const start = new Date(latestSchedule.start_date);
    const staffMap = new Map((latestSchedule.staff || []).map((s) => [s.id, s]));
    const addDays = (d: Date, n: number) => {
      const dt = new Date(d);
      dt.setDate(dt.getDate() + n);
      return dt;
    };
    const weeks: any[][] = [];
    for (let i = 0; i < totalDays; i++) {
      const req = reqs[i % reqs.length];
      const date = addDays(start, i);
      const dateStr = date.toISOString().slice(0, 10);
      const dayAssignments = (latestSchedule.assignments || []).filter((a) => a.date === dateStr);
      const techReq = (req.tech_openers || 0) + (req.tech_mids || 0) + (req.tech_closers || 0);
      const rnReq = req.rn_count || 0;
      const adminReq = req.admin_count || 0;
      const techFilled = dayAssignments.filter((a) => a.role?.toLowerCase() === "tech" && a.staff_id).length;
      const rnFilled = dayAssignments.filter((a) => a.role?.toLowerCase() === "rn" && a.staff_id).length;
      const adminFilled = dayAssignments.filter((a) => a.role?.toLowerCase() === "admin" && a.staff_id).length;
      const techMissing = Math.max(techReq - techFilled, 0);
      const rnMissing = Math.max(rnReq - rnFilled, 0);
      const adminMissing = Math.max(adminReq - adminFilled, 0);
      const deficits: string[] = [];
      if (techMissing) deficits.push(`Needs ${techMissing} Tech${techMissing > 1 ? "s" : ""}`);
      if (rnMissing) deficits.push(`Needs ${rnMissing} RN${rnMissing > 1 ? "s" : ""}`);
      if (adminMissing) deficits.push(`Needs ${adminMissing} Admin${adminMissing > 1 ? "s" : ""}`);
      const detailList: { label: string; value: string }[] = [];
      const addRoleLines = (role: string, reqCount: number, assignments: typeof dayAssignments) => {
        const roleAss = assignments.filter((a) => a.role?.toLowerCase() === role.toLowerCase());
        for (let idx = 0; idx < Math.max(reqCount, roleAss.length); idx++) {
          const a = roleAss[idx];
          const staff = a && a.staff_id ? staffMap.get(a.staff_id) : null;
          detailList.push({ label: role, value: staff?.name || "Open" });
        }
      };
      addRoleLines("RN", rnReq, dayAssignments);
      addRoleLines("Tech", techReq, dayAssignments);
      addRoleLines("Admin", adminReq, dayAssignments);
      const weekIdx = Math.floor(i / reqs.length);
      weeks[weekIdx] = weeks[weekIdx] || [];
      weeks[weekIdx].push({
        date,
        dateStr,
        req,
        deficits,
        status: deficits.length ? "warn" : "ok",
        detailList,
        summary: {
          techReq,
          rnReq,
          adminReq,
          techFilled,
          rnFilled,
          adminFilled,
        },
      });
    }
    return weeks;
  }, [latestSchedule]);

  const currentWeek = weeksData[weekIndex] || [];

  return (
    <>
      <section className="hero-grid">
        <div className="hero-copy">
          <div className="eyebrow-pill">Built for dialysis teams</div>
          <h1>
            Operational scheduling,
            <br />
            without the scramble
          </h1>
          <p className="hero-sub">
            Keep RN, Tech, and admin assistant coverage balanced across shifts. ShiftPilot gives you guardrails, collaboration, and exports without
            losing override control.
          </p>
          <div className="hero-actions">
            <Link className="primary-chip" to="/planner">
              Launch planner
            </Link>
            <Link className="secondary-link" to="/features">
              See how it works
            </Link>
          </div>
          <ul className="hero-checklist">
            <li>RN/Tech ratios & weekend rotation</li>
            <li>Admin assistants included in coverage</li>
            <li>Fixed assignments stay locked</li>
            <li>Exports for floor teams & leadership</li>
          </ul>
          <div className="trust-row">
            <div className="pill muted-pill">HIPAA-conscious workflows</div>
            <div className="pill muted-pill">Audit-friendly exports</div>
            <div className="pill muted-pill">Built for clinic managers</div>
          </div>
        </div>

        <div className="hero-visual">
          <div className="orb orb-a" aria-hidden="true" />
          <div className="orb orb-b" aria-hidden="true" />
          <div className="schedule-card">
            <div className="schedule-card__head">
              <div>
                <span className="pill small-pill">Week of Jun 10</span>
                <h4>Dialysis coverage</h4>
              </div>
              <div className="pill success-pill">Conflicts resolved</div>
            </div>
            <div className="schedule-list">
              <div className="schedule-row">
                <span className="dot dot-blue" />
                <div>
                  <div className="row-title">Mon - First shift</div>
                  <div className="row-sub">RN (2) | Tech (4) | Admin (1)</div>
                </div>
                <span className="tag">Staffed</span>
              </div>
              <div className="schedule-row">
                <span className="dot dot-teal" />
                <div>
                  <div className="row-title">Tue - Second shift</div>
                  <div className="row-sub">RN (2) | Tech (3) | Admin (1)</div>
                </div>
                <span className="tag">Staffed</span>
              </div>
              <div className="schedule-row">
                <span className="dot dot-amber" />
                <div>
                  <div className="row-title">Wed - First shift</div>
                  <div className="row-sub">RN (2) | Tech (3) | Admin (1)</div>
                </div>
                <span className="tag tag-warn">Needs 1 Tech</span>
              </div>
              <div className="schedule-row">
                <span className="dot dot-slate" />
                <div>
                  <div className="row-title">Weekend rotation</div>
                  <div className="row-sub">A-team off | B-team on</div>
                </div>
                <span className="tag ghost-tag">Locked</span>
              </div>
            </div>
            <div className="schedule-foot">
              <div className="pill muted-pill">Soft constraints honored</div>
              <div className="pill muted-pill">Exports: Excel / PDF</div>
            </div>
          </div>
        </div>
      </section>

      <main className="app-shell">
        <section id="features" className="features-grid">
          <article className="feature-card">
            <span className="feature-icon">
              <IconCalendar />
            </span>
            <div>
              <h3>Clinic-aware scheduling</h3>
              <p>Respect chair cadence, RN/Tech ratios, and weekend rotations while keeping override control in your hands.</p>
            </div>
          </article>
          <article className="feature-card">
            <span className="feature-icon">
              <IconShield />
            </span>
            <div>
              <h3>Manager-run, no self-serve</h3>
              <p>Stay in control with one clinic login—designed to reduce manual scheduling time without staff-facing portals.</p>
            </div>
          </article>
          <article className="feature-card">
            <span className="feature-icon">
              <IconExport />
            </span>
            <div>
              <h3>Export-ready</h3>
              <p>Share clean Excel/PDF outputs for floor teams and leadership in seconds - no manual cleanup required.</p>
            </div>
          </article>
        </section>

        <section className="how-section">
          <div className="section-head">
            <div>
              <div className="eyebrow-pill muted-pill">How it works</div>
              <h2>Go from rules to roster in minutes</h2>
              <p className="muted">Define your clinic guardrails once, then iterate quickly with your team.</p>
            </div>
            <Link className="ghost" to="/planner">
              Open planner -&gt;
            </Link>
          </div>
          <div className="how-grid">
            {steps.map((step, idx) => (
              <article className="step-card" key={step.title}>
                <div className="step-number">{idx + 1}</div>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="latest-schedule">
          <div className="section-head">
            <div>
              <div className="eyebrow-pill muted-pill">Latest schedule</div>
              <h2>Snapshot of your current roster</h2>
              <p className="muted">Saved from your most recent run. Switch weeks to view coverage.</p>
            </div>
            <div className="week-nav">
              <button
                className="secondary-btn"
                disabled={weekIndex <= 0}
                onClick={() => setWeekIndex((w) => Math.max(0, w - 1))}
                aria-label="Previous week"
              >
                <IconChevronLeft />
              </button>
              <span className="pill small-pill">Week {weekIndex + 1}</span>
              <button
                className="secondary-btn"
                disabled={weekIndex >= weeksData.length - 1}
                onClick={() => setWeekIndex((w) => Math.min(weeksData.length - 1, w + 1))}
                aria-label="Next week"
              >
                <IconChevronRight />
              </button>
            </div>
          </div>

          {!latestSchedule ? (
            <div className="card planner-shell">
              <p className="muted">
                {scheduleError || "No schedule saved. "}
                <Link className="secondary-link" to="/planner">
                  Head to Planner to make one.
                </Link>
              </p>
            </div>
          ) : (
            <div className="day-grid">
              {currentWeek.map((day) => (
                <article key={day.dateStr} className="day-card">
                  <div className="day-head">
                    <div>
                      <div className="pill small-pill">{day.date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div>
                      <h4>{day.req.day_name}</h4>
                      <p className="muted">
                        RN {day.summary.rnFilled}/{day.summary.rnReq} · Tech {day.summary.techFilled}/{day.summary.techReq} · Admin{" "}
                        {day.summary.adminFilled}/{day.summary.adminReq}
                      </p>
                    </div>
                    <span className={`tag ${day.deficits.length ? "tag-warn" : ""}`}>
                      {day.deficits.length ? day.deficits.join(", ") : "Fully staffed"}
                    </span>
                  </div>
                  <details>
                    <summary>Details</summary>
                    <ul className="staff-list">
                      {day.detailList.map((d, idx) => (
                        <li key={`${d.label}-${idx}`}>
                          <span className="staff-role">{d.label}:</span> <span className={d.value === "Open" ? "staff-open" : ""}>{d.value}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </>
  );
}
