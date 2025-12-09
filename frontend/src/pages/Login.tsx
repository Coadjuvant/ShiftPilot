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
    <main className="app-shell auth-grid">
      <section className="auth-copy">
        <div className="eyebrow-pill">Access your planner</div>
        <h1>Log in to ShiftPilot</h1>
        <p className="hero-sub">
          Use your clinic manager credentials to open schedules, run updates, and export clean handoffs for floor teams and leadership.
        </p>
        <ul className="hero-checklist">
          <li>RN/Tech/Admin guardrails intact</li>
          <li>Keep fixed assignments locked</li>
          <li>Exports ready for Excel/PDF</li>
        </ul>
      </section>

      <section className="auth-card">
        <h3>Sign in</h3>
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
        </form>
        {status && <p className="status">{status}</p>}
        <p className="muted small-note">Need access? Ask your admin to share the clinic credentials.</p>
      </section>
    </main>
  );
}
