import { useState } from "react";
import { login, setAuthToken } from "../api/client";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setStatus("");
    try {
      const res = await login(username, password);
      setAuthToken(res.token);
      localStorage.setItem("auth_token", res.token);
      setStatus("Logged in");
    } catch {
      setStatus("Login failed. Check credentials.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-hero">
        <div className="auth-copy">
          <div className="eyebrow-pill">Access your planner</div>
          <h1>Log in to ShiftPilot</h1>
          <p className="hero-sub">
            One set of clinic manager credentials—open the planner, run scenarios, and export clean handoffs for floor teams and leadership.
          </p>
          <ul className="hero-checklist">
            <li>Guardrails for Tech / RN / Admin</li>
            <li>Keep fixed assignments locked</li>
            <li>Exports ready for Excel/PDF</li>
          </ul>
          <div className="auth-badges">
            <span className="pill subtle">Single login</span>
            <span className="pill subtle">No staff self-serve</span>
            <span className="pill subtle">HIPAA conscious</span>
          </div>
        </div>

        <div className="auth-card">
          <div className="auth-card-head">
            <p className="muted">Clinic manager sign-in</p>
            <span className="pill success">Secure session</span>
          </div>
          <form className="auth-form" onSubmit={handleLogin}>
            <label className="field">
              <span>Username</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
            </label>
            <label className="field">
              <span>Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </label>
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Log in"}
            </button>
            {status && <p className="status">{status}</p>}
          </form>
          <p className="muted small-note">Need access? Ask your admin to share the clinic credentials.</p>
        </div>
      </section>
    </main>
  );
}
