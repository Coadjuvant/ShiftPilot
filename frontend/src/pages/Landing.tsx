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
  const [isAuthed, setIsAuthed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return Boolean(localStorage.getItem("auth_token"));
  });
  const [latestSchedule, setLatestSchedule] = useState<SavedSchedule | null>(null);
  const [weekIndex, setWeekIndex] = useState(0);
  const [scheduleError, setScheduleError] = useState<string>("");
  const [expandedDay, setExpandedDay] = useState<string | null>(null);
  const [scheduleTick, setScheduleTick] = useState(0);
  const plannerRoute = isAuthed ? "/planner" : "/login";

  const parseISODate = (value: string) => {
    const parts = value.split("-").map(Number);
    if (parts.length >= 3 && parts.every((n) => Number.isFinite(n))) {
      return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    }
    return new Date(value);
  };

  const addDaysUTC = (date: Date, days: number) => {
    return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() + days));
  };

  const formatScheduleDate = (date: Date) =>
    date.toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });

  const formatGeneratedAt = (value?: string) => {
    if (!value) return "";
    const hasTimeZone = /([zZ]|[+-]\d{2}:\d{2})$/.test(value);
    const date = new Date(hasTimeZone ? value : `${value}Z`);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = () => {
      setIsAuthed(Boolean(localStorage.getItem("auth_token")));
      setScheduleTick((tick) => tick + 1);
    };
    window.addEventListener("storage", handler);
    handler();
    return () => window.removeEventListener("storage", handler);
  }, []);

  useEffect(() => {
    if (!isAuthed) {
      setLatestSchedule(null);
      setExpandedDay(null);
      return;
    }
    fetchLatestSchedule()
      .then((data) => {
        if (data && (data as any).status === "none") {
          setLatestSchedule(null);
          setScheduleError("No saved schedule yet");
          setExpandedDay(null);
          return;
        }
        setLatestSchedule(data);
        setScheduleError("");
        setWeekIndex(0);
        setExpandedDay(null);
      })
      .catch(() => {
        setLatestSchedule(null);
        setScheduleError("Unable to load latest schedule");
        setExpandedDay(null);
      });
  }, [isAuthed, scheduleTick]);

  const weeksData = useMemo(() => {
    if (!latestSchedule) return [];
    const reqs = latestSchedule.requirements || [];
    if (!reqs.length) return [];
    const allowedRoles = new Set(
      latestSchedule.export_roles && Array.isArray(latestSchedule.export_roles) ? latestSchedule.export_roles : ["Tech", "RN", "Admin"]
    );
    const totalDays = (latestSchedule.weeks || 0) * reqs.length;
    const start = parseISODate(latestSchedule.start_date);
    const staffMap = new Map((latestSchedule.staff || []).map((s) => [s.id, s]));
    const addDays = (d: Date, n: number) => {
      return addDaysUTC(d, n);
    };
    const weeks: any[][] = [];
    for (let i = 0; i < totalDays; i++) {
      const dayPos = i % reqs.length;
      const weekIdx = Math.floor(i / reqs.length);
      const req = reqs[dayPos];
      const date = addDays(start, weekIdx * 7 + dayPos);
      const dateStr = date.toISOString().slice(0, 10);
      const dayAssignments = (latestSchedule.assignments || [])
        .filter((a) => a.date === dateStr)
        .filter((a) => allowedRoles.has((a.role || "").toString()));
      const techReq = allowedRoles.has("Tech") ? (req.tech_openers || 0) + (req.tech_mids || 0) + (req.tech_closers || 0) : 0;
      const rnReq = allowedRoles.has("RN") ? req.rn_count || 0 : 0;
      const adminReq = allowedRoles.has("Admin") ? req.admin_count || 0 : 0;
      const isFilled = (assignment: { staff_id?: string | null }) =>
        Boolean(assignment.staff_id) && assignment.staff_id !== "OPEN";
      const techFilled = dayAssignments.filter((a) => a.role?.toLowerCase() === "tech" && isFilled(a)).length;
      const rnFilled = dayAssignments.filter((a) => a.role?.toLowerCase() === "rn" && isFilled(a)).length;
      const adminFilled = dayAssignments.filter((a) => a.role?.toLowerCase() === "admin" && isFilled(a)).length;
      const techMissing = Math.max(techReq - techFilled, 0);
      const rnMissing = Math.max(rnReq - rnFilled, 0);
      const adminMissing = Math.max(adminReq - adminFilled, 0);
      const deficits: string[] = [];
      if (techMissing) deficits.push(`Needs ${techMissing} Tech${techMissing > 1 ? "s" : ""}`);
      if (rnMissing) deficits.push(`Needs ${rnMissing} RN${rnMissing > 1 ? "s" : ""}`);
      if (adminMissing) deficits.push(`Needs ${adminMissing} Admin${adminMissing > 1 ? "s" : ""}`);
      const details: { label: string; value: string }[] = [];
      const pushSlots = (labelBase: string, count: number, assignments: typeof dayAssignments, useIndex = false) => {
        const totalSlots = Math.max(count, assignments.length);
        if (!totalSlots) return;
        for (let idx = 0; idx < totalSlots; idx++) {
            const assignment = assignments[idx];
            const staffName =
              assignment?.staff_id && assignment.staff_id !== "OPEN" ? staffMap.get(assignment.staff_id)?.name : null;
            const label = useIndex && totalSlots > 1 ? `${labelBase} ${idx + 1}` : labelBase;
            details.push({ label, value: staffName || "--" });
          }
        };
      if (allowedRoles.has("Tech")) {
        const techAssignments = dayAssignments.filter((a) => a.role?.toLowerCase() === "tech");
        const techOpen = techAssignments.filter((a) => a.duty === "open");
        const techMid = techAssignments.filter((a) => a.duty === "mid").sort((a, b) => (a.slot_index ?? 0) - (b.slot_index ?? 0));
        const techClose = techAssignments.filter((a) => a.duty === "close");
        const techBleach = techAssignments.filter((a) => a.duty === "bleach" || a.is_bleach);
        pushSlots("Open", req.tech_openers || 0, techOpen);
        pushSlots("Mid", req.tech_mids || 0, techMid, true);
        pushSlots("Close", req.tech_closers || 0, techClose);
        if (techBleach.length) pushSlots("Bleach", techBleach.length, techBleach);
      }
      if (allowedRoles.has("RN")) {
        const rnAssignments = dayAssignments.filter((a) => a.role?.toLowerCase() === "rn");
        pushSlots("RN", rnReq, rnAssignments, true);
      }
      if (allowedRoles.has("Admin")) {
        const adminAssignments = dayAssignments.filter((a) => a.role?.toLowerCase() === "admin");
        pushSlots("Admin", adminReq, adminAssignments, true);
      }
      weeks[weekIdx] = weeks[weekIdx] || [];
      weeks[weekIdx].push({
        date,
        dateStr,
        req,
        deficits,
        details,
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
  useEffect(() => {
    if (weekIndex > weeksData.length - 1) {
      setWeekIndex(Math.max(weeksData.length - 1, 0));
    }
  }, [weeksData.length]);

  const weekLabel = useMemo(() => {
    if (!latestSchedule || !weeksData.length) return "Week 1";
    const start = parseISODate(latestSchedule.start_date);
    const dt = addDaysUTC(start, weekIndex * 7);
    return `Week of ${formatScheduleDate(dt)}`;
  }, [latestSchedule, weekIndex, weeksData.length]);

  const scheduleStatus = useMemo(() => {
    if (!currentWeek.length) return "No data";
    const hasDeficit = currentWeek.some((d) => d.deficits.length);
    return hasDeficit ? "Needs attention" : "Fully staffed";
  }, [currentWeek]);

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
            <Link className="primary-chip" to={plannerRoute}>
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
          {isAuthed ? (
            <div className="schedule-card">
              <div className="schedule-card__head">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                  <span className="pill small-pill">{weekLabel}</span>
                  <h4 style={{ margin: 0 }}>Dialysis coverage</h4>
                  <div className="pill muted-pill">{scheduleStatus}</div>
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
                <div className="schedule-list">
                  <div className="schedule-row">
                    <div>
                      <div className="row-title">No schedule saved</div>
                                      <div className="row-sub">
                        <Link className="secondary-link" to={plannerRoute}>
                          Head to Planner to make one.
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              ) : !currentWeek.length ? (
                <div className="schedule-list">
                  <div className="schedule-row">
                    <div>
                      <div className="row-title">{scheduleError || "No schedule data yet"}</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="schedule-list">
              {currentWeek.map((day) => {
                const isOpen = expandedDay === day.dateStr;
                return (
                  <div
                    className={`schedule-row ${isOpen ? "open" : ""}`}
                        key={day.dateStr}
                        role="button"
                        tabIndex={0}
                        aria-expanded={isOpen}
                        onClick={() => setExpandedDay(isOpen ? null : day.dateStr)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setExpandedDay(isOpen ? null : day.dateStr);
                          }
                        }}
                      >
                        <span className={`dot ${day.deficits.length ? "dot-amber" : "dot-blue"}`} />
                        <div>
                          <div className="row-title">
                            {day.req.day_name} - {formatScheduleDate(day.date)}
                          </div>
                          <div className="row-sub">
                            RN ({day.summary.rnFilled}/{day.summary.rnReq}) | Tech ({day.summary.techFilled}/{day.summary.techReq}) | Admin (
                            {day.summary.adminFilled}/{day.summary.adminReq})
                          </div>
                        </div>
                        <span className={`tag ${day.deficits.length ? "tag-warn" : ""}`}>
                          {day.deficits.length ? day.deficits.join(", ") : "Fully staffed"}
                        </span>
                        {isOpen && day.details?.length ? (
                          <div className="schedule-row-details">
                            {day.details.map((detail: { label: string; value: string }, idx: number) => (
                              <div className="schedule-detail" key={`${day.dateStr}-${detail.label}-${idx}`}>
                                <span className="schedule-detail-role">{detail.label}:</span> {detail.value}
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                );
              })}
            </div>
          )}
              {latestSchedule?.generated_at ? (
                <div className="schedule-meta">Generated {formatGeneratedAt(latestSchedule.generated_at)}</div>
              ) : null}
              <div className="schedule-foot">
                <div className="pill muted-pill">Soft constraints honored</div>
                <div className="pill muted-pill">Exports: Excel / PDF</div>
              </div>
            </div>
          ) : (
            <div className="schedule-card">
              <div className="schedule-card__head">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                  <span className="pill small-pill">Week of Jun 10</span>
                  <h4 style={{ margin: 0 }}>Dialysis coverage</h4>
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
          )}
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
              <p>Stay in control with one clinic login - designed to reduce manual scheduling time without staff-facing portals.</p>
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

      </main>
    </>
  );
}
