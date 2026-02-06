import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { getStoredToken } from "../api/client";

const IconRules = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M6 4h12v4H6z" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <path d="M6 10h12v10H6z" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <path d="M9 7h6M9 14h6M9 17h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const IconRotation = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M4 12a8 8 0 0 1 8-8" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    <path d="M12 4h6v6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    <path d="M20 12a8 8 0 0 1-8 8" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    <path d="M12 20H6v-6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
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

const IconBolt = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M13.5 3 6 13h5l-1 8 8-11h-5z" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinejoin="round" />
  </svg>
);

const IconUsers = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <circle cx="8" cy="9" r="3" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="16" cy="9" r="3" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <path d="M3.5 19c0-2.5 2.5-4 4.5-4s4.5 1.5 4.5 4" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <path d="M12 19c0-2.5 2.5-4 4.5-4s4.5 1.5 4.5 4" stroke="currentColor" strokeWidth="1.5" fill="none" />
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

const featureCards = [
  {
    title: "Clinic guardrails",
    body: "Lock chair cadence, RN ratios, weekend rotations, and shift coverage so every run respects your rules.",
    icon: <IconRules />,
  },
  {
    title: "Bleach rotation control",
    body: "Set weekly or quarterly bleach cycles and keep the rotation order synced with your latest run window.",
    icon: <IconRotation />,
  },
  {
    title: "Export-ready handoffs",
    body: "Share clean Excel/CSV outputs and snapshots so floor teams never have to rewrite your schedule.",
    icon: <IconExport />,
  },
  {
    title: "Fast scenario runs",
    body: "Generate 1-12 week blocks, compare outcomes, and call out coverage gaps right away.",
    icon: <IconBolt />,
  },
  {
    title: "Role clarity",
    body: "Separate Tech, RN, and Admin assignments with visibility controls that match what your clinic needs.",
    icon: <IconUsers />,
  },
  {
    title: "Manager-only access",
    body: "Single clinic login, no staff self-serve. Keep authority with the clinic manager.",
    icon: <IconShield />,
  },
];

const tutorialSteps = [
  {
    title: "Staff tab",
    body:
      "Add every Tech, RN, and admin assistant who can appear in the roster. Set open, close, and bleach capabilities so coverage rules apply correctly. Keep names consistent with how the clinic labels them.",
  },
  {
    title: "Demand tab",
    body:
      "Enter patient load and required Tech opener, Pod (mid), and closer counts per day. This snapshot defines what fully staffed means for the run. Update it for each schedule window.",
  },
  {
    title: "Availability tab",
    body:
      "Toggle which days each person can work. Availability is enforced before preferences or constraints. Use it for fixed days off, rotating weekends, or limited schedules.",
  },
  {
    title: "PTO tab",
    body:
      "Add PTO ranges for each staff member. The scheduler skips those dates and flags coverage gaps if needed. Use it for vacations, training, and planned absences.",
  },
  {
    title: "Constraints tab",
    body:
      "Set constraint weights (0 to ignore, 1-9 for soft penalties, 10 to never break), then configure bleach day, frequency, and rotation order. The cursor shows who is next in line and advances after each bleach assignment.",
  },
  {
    title: "Prefs tab",
    body:
      "Use the sliders to nudge who prefers open, Pod, or close on MWF vs TTS. Lower values avoid the shift (0), higher values prefer it (10), and 5 is neutral. Keep weights light if coverage is tight.",
  },
  {
    title: "Run tab",
    body:
      "Set the schedule window, clinic name, timezone, trials, and export roles. Run the schedule and review the matrix with Pod labels and shift totals. Export Excel or CSV when ready.",
  },
  {
    title: "Admin tab",
    body:
      "Manage user accounts, view audit logs with IP tracking, and create invite keys for new clinic managers. All administrative functions are contained here.",
  },
];

export default function Features() {
  const [isAuthed, setIsAuthed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return Boolean(getStoredToken());
  });
  const plannerRoute = isAuthed ? "/planner" : "/login";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = () => setIsAuthed(Boolean(getStoredToken()));
    window.addEventListener("storage", handler);
    handler();
    const interval = window.setInterval(handler, 60_000);
    return () => {
      window.removeEventListener("storage", handler);
      window.clearInterval(interval);
    };
  }, []);

  return (
    <main className="app-shell features-shell">
      <section className="features-hero">
        <div className="features-hero-copy">
          <div className="eyebrow-pill muted-pill">Features</div>
          <h1>Everything a clinic manager needs to schedule fast.</h1>
          <p className="hero-sub">
            Capture your rules once, run six-week blocks in minutes, and share clean handoffs without chasing edits.
          </p>
          <div className="features-actions">
            <Link className="primary-chip" to={plannerRoute}>
              {isAuthed ? "Open planner" : "Login"}
            </Link>
            <Link className="secondary-link" to="/planner">
              See planner workflow
            </Link>
          </div>
          <div className="features-pill-row">
            <span className="pill subtle">Single clinic login</span>
            <span className="pill subtle">No staff self-serve</span>
            <span className="pill subtle">HIPAA conscious</span>
          </div>
        </div>

        <div className="features-hero-card">
          <div className="features-hero-card-head">
            <span className="pill small-pill">Planner snapshot</span>
            <span className="pill muted-pill">Ready to run</span>
          </div>
          <div className="features-metric">
            <div>
              <div className="metric-label">Run window</div>
              <div className="metric-value">6 weeks</div>
            </div>
            <span className="pill muted-pill small-pill">Adjustable</span>
          </div>
          <div className="features-metric">
            <div>
              <div className="metric-label">Coverage checks</div>
              <div className="metric-value">Tech / RN / Admin</div>
            </div>
            <span className="pill muted-pill small-pill">Live</span>
          </div>
          <div className="features-metric">
            <div>
              <div className="metric-label">Exports</div>
              <div className="metric-value">Excel + CSV</div>
            </div>
            <span className="pill muted-pill small-pill">Instant</span>
          </div>
          <div className="features-hero-note">Save your latest run and pull it up the next time you log in.</div>
        </div>
      </section>

      <section className="features-section">
        <div className="section-head">
          <div>
            <div className="eyebrow-pill muted-pill">Clinic ready</div>
            <h2>Rules first. Schedules follow.</h2>
            <p className="muted">Keep every requirement inside the planner so manual edits do not sneak back in.</p>
          </div>
        </div>
        <div className="features-grid extended">
          {featureCards.map((feature) => (
            <article className="feature-card" key={feature.title}>
              <span className="feature-icon">{feature.icon}</span>
              <div>
                <h3>{feature.title}</h3>
                <p>{feature.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="tutorial-section">
        <div className="section-head">
          <div>
            <div className="eyebrow-pill muted-pill">Planner walkthrough</div>
            <h2>From setup to schedule in eight steps.</h2>
            <p className="muted">Each tab in the planner has a single job. Follow these in order to run a clean schedule.</p>
          </div>
        </div>
        <div className="tutorial-steps">
          {tutorialSteps.map((step, index) => (
            <article className="tutorial-step" key={step.title}>
              <div className="tutorial-copy">
                <div className="tutorial-label">
                  <span className="step-number">{index + 1}</span>
                  <h3>{step.title}</h3>
                </div>
                <p className="muted">{step.body}</p>
              </div>
              <div className="tutorial-media">
                <div className="tutorial-media-frame">
                  <span>Drop GIF/video here</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="features-split">
        <div className="features-split-card">
          <div className="eyebrow-pill muted-pill">Coverage intelligence</div>
          <h3>Spot gaps before they hit the floor.</h3>
          <p className="muted">
            Every day shows what is staffed, what is open, and what still needs coverage based on the demand snapshot you ran.
          </p>
          <ul className="feature-list">
            <li>Run-week view with day-by-day coverage status.</li>
            <li>Roles stay visible: Tech, RN, Admin.</li>
            <li>Export roles can be toggled per run.</li>
          </ul>
        </div>
        <div className="features-split-card">
          <div className="eyebrow-pill muted-pill">Clean handoffs</div>
          <h3>Share what the team needs in seconds.</h3>
          <p className="muted">
            Export a schedule to CSV, keep a saved snapshot, and hand off the same story to everyone from charge to leadership.
          </p>
          <ul className="feature-list">
            <li>One click Excel or CSV export.</li>
            <li>Config import/export for new clinics.</li>
            <li>Latest schedule ready at login.</li>
          </ul>
        </div>
      </section>

      <section className="features-cta">
        <div>
          <div className="eyebrow-pill muted-pill">Ready to see it?</div>
          <h2>Open the planner and run a scenario.</h2>
          <p className="muted">The fastest way to see the value is to run your next six-week block.</p>
        </div>
        <Link className="primary-chip" to={plannerRoute}>
          {isAuthed ? "Open planner" : "Login"}
        </Link>
      </section>
    </main>
  );
}
