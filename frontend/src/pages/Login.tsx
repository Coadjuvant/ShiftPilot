import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { consumeAuthExpiredFlag, fetchHealth, login, setAuthToken } from "../api/client";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [online, setOnline] = useState<"checking" | "ok" | "down">("checking");
  const [loginSuccess, setLoginSuccess] = useState(false);
  const [statusTone, setStatusTone] = useState<"default" | "success" | "error">("default");
  const navigate = useNavigate();

  useEffect(() => {
    fetchHealth()
      .then(() => setOnline("ok"))
      .catch(() => setOnline("down"));
  }, []);

  useEffect(() => {
    if (consumeAuthExpiredFlag()) {
      setStatus("Session expired. Please log in again.");
      setStatusTone("error");
    }
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setStatus("");
    setStatusTone("default");
    try {
      const res = await login(username, password);
      setAuthToken(res.token);
      localStorage.setItem("auth_token", res.token);
      localStorage.setItem("auth_user", username || "user");
      setLoginSuccess(true);
      const message = "Login successful. Redirecting to home...";
      setStatus(message);
      setStatusTone("success");
      window.dispatchEvent(new Event("storage"));
      setTimeout(() => navigate("/"), 2000);
    } catch {
      setStatus("Login failed. Check credentials.");
      setLoginSuccess(false);
      setStatusTone("error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user");
    setLoginSuccess(false);
    setStatus("Logged out");
    setStatusTone("default");
    // Notify other listeners and return home
    window.dispatchEvent(new Event("storage"));
    navigate("/");
  };

  const onlineLabel =
    online === "checking" ? "Checking..." : online === "ok" ? "Online" : "Offline";
  const onlineTitle =
    online === "ok" ? "Backend health: 200 OK" : online === "checking" ? "Checking backend health..." : "Backend health unavailable";

  return (
    <main className="auth-shell">
      <section className="auth-hero">
        <div className="auth-copy">
          <div className="eyebrow-pill">Access your planner</div>
          <h1>Log in to ShiftPilot</h1>
          <p className="hero-sub">
            One set of clinic manager credentials - open the planner, run scenarios, and export clean handoffs for floor teams and leadership.
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
            <div style={{ display: "flex", gap: "0.35rem", alignItems: "center", flexWrap: "wrap" }}>
              <span className={`pill ${online === "ok" ? "success" : "subtle"}`} title={onlineTitle}>
                {onlineLabel}
              </span>
            </div>
          </div>
          <form className="auth-form" onSubmit={handleLogin}>
            <label className="field">
              <span>Username</span>
              <input
                id="login-username"
                name="login-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                id="login-password"
                name="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <button
              type={loginSuccess ? "button" : "submit"}
              onClick={loginSuccess ? handleLogout : undefined}
              disabled={isSubmitting}
            >
              {loginSuccess ? "Logout" : isSubmitting ? "Signing in..." : "Log in"}
            </button>
            {status && <p className={`status ${statusTone !== "default" ? statusTone : ""}`}>{status}</p>}
          </form>
          <p className="muted small-note">Need access? Ask your admin to share the clinic credentials.</p>
        </div>
      </section>
    </main>
  );
}
