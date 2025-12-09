import { Link } from "react-router-dom";

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
      </main>
    </>
  );
}
