export default function Contact() {
  return (
    <main className="app-shell contact-shell">
      <section className="contact-hero">
        <div>
          <div className="eyebrow-pill muted-pill">Support</div>
          <h1>We are here to help</h1>
          <p className="hero-sub">
            For scheduling questions, access issues, or feedback, reach out and we will get back to you quickly.
          </p>
          <div className="contact-actions">
            <a className="primary-chip" href="mailto:support@shiftpilot.me?subject=ShiftPilot%20Support">
              Email support
            </a>
            <a className="secondary-link" href="mailto:support@shiftpilot.me?subject=ShiftPilot%20Feedback">
              Share feedback
            </a>
          </div>
          <div className="contact-meta">
            <span className="pill subtle">Response time: 1 business day</span>
            <span className="pill subtle">Clinic manager only</span>
          </div>
        </div>
        <div className="contact-card">
          <h3>Contact details</h3>
          <div className="contact-row">
            <span className="muted">Email</span>
            <a href="mailto:support@shiftpilot.me">support@shiftpilot.me</a>
          </div>
          <div className="contact-row">
            <span className="muted">Coverage</span>
            <span>Mon-Fri, 8am-6pm</span>
          </div>
          <div className="contact-row">
            <span className="muted">Best for</span>
            <span>Login help, scheduling questions, export issues</span>
          </div>
          <p className="muted small-note">
            Please avoid sending patient-specific information by email.
          </p>
        </div>
      </section>
    </main>
  );
}
