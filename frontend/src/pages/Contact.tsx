import { useState } from "react";

export default function Contact() {
  const supportEmail = "support@shiftpilot.me";
  const [supportCopyLabel, setSupportCopyLabel] = useState("Copy support email");
  const [feedbackCopyLabel, setFeedbackCopyLabel] = useState("Copy feedback email");
  const [detailCopyLabel, setDetailCopyLabel] = useState("Copy");

  const copySupportEmail = async (
    setLabel: (value: string) => void,
    defaultLabel: string,
    successLabel: string
  ) => {
    if (typeof window === "undefined") return;
    try {
      await navigator.clipboard.writeText(supportEmail);
      setLabel(successLabel);
    } catch (err) {
      console.warn("Failed to copy support email", err);
      setLabel("Copy failed");
    }
    window.setTimeout(() => setLabel(defaultLabel), 2000);
  };

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
            <button
              type="button"
              className="primary-chip"
              onClick={() => copySupportEmail(setSupportCopyLabel, "Copy support email", "Support email copied")}
            >
              {supportCopyLabel}
            </button>
            <button
              type="button"
              className="secondary-link"
              onClick={() => copySupportEmail(setFeedbackCopyLabel, "Copy feedback email", "Feedback email copied")}
            >
              {feedbackCopyLabel}
            </button>
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
            <div className="contact-email">
              <span>{supportEmail}</span>
              <button
                type="button"
                className="secondary-link"
                onClick={() => copySupportEmail(setDetailCopyLabel, "Copy", "Copied")}
              >
                {detailCopyLabel}
              </button>
            </div>
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
