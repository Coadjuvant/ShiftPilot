type Props = { title: string };

export default function PlaceholderPage({ title }: Props) {
  return (
    <main className="app-shell placeholder">
      <section className="placeholder-hero">
        <div className="eyebrow-pill muted-pill">Coming soon</div>
        <h1>{title}</h1>
        <p className="hero-sub">
          This area is on the roadmap. We're keeping schedules, exports, and admin controls stable while we build out the next set of tools.
        </p>
        <div className="placeholder-actions">
          <a className="secondary-link" href="/planner">
            Back to planner
          </a>
          <a className="secondary-link" href="/contact">
            Contact support
          </a>
        </div>
      </section>
      <section className="placeholder-card">
        <h3>What's planned</h3>
        <ul className="placeholder-list">
          <li>Deeper exports and sharing</li>
          <li>Admin-friendly tweaks</li>
          <li>More scheduling guardrails</li>
        </ul>
      </section>
    </main>
  );
}
