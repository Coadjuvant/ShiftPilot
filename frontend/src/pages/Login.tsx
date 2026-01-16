import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { consumeAuthExpiredFlag, fetchHealth, login, setAuthToken, setupUser } from "../api/client";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [online, setOnline] = useState<"checking" | "ok" | "down">("checking");
  const [loginSuccess, setLoginSuccess] = useState(false);
  const [statusTone, setStatusTone] = useState<"default" | "success" | "error">("default");
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [inviteToken, setInviteToken] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [signupStatus, setSignupStatus] = useState("");
  const [signupTone, setSignupTone] = useState<"default" | "success" | "error">("default");
  const [isCreating, setIsCreating] = useState(false);
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

  const switchMode = (mode: "login" | "signup") => {
    setAuthMode(mode);
    setStatus("");
    setStatusTone("default");
    setSignupStatus("");
    setSignupTone("default");
    setLoginSuccess(false);
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

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    setSignupStatus("");
    setSignupTone("default");
    try {
      const res = await setupUser(inviteToken, newUsername, newPassword);
      setAuthToken(res.token);
      localStorage.setItem("auth_token", res.token);
      localStorage.setItem("auth_user", newUsername || "user");
      setSignupStatus("Account created. Redirecting to home...");
      setSignupTone("success");
      window.dispatchEvent(new Event("storage"));
      setTimeout(() => navigate("/"), 2500);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Account creation failed. Check the key and try again.";
      setSignupStatus(String(msg));
      setSignupTone("error");
    } finally {
      setIsCreating(false);
    }
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
            <li>Exports ready for Excel/CSV</li>
          </ul>
          <div className="auth-badges">
            <span className="pill subtle">Single login</span>
            <span className="pill subtle">No staff self-serve</span>
            <span className="pill subtle">HIPAA conscious</span>
          </div>
        </div>

        <div className="auth-card">
          <div className="auth-card-head">
            <p className="muted">{authMode === "login" ? "Clinic manager sign-in" : "Create your clinic login"}</p>
            <div style={{ display: "flex", gap: "0.35rem", alignItems: "center", flexWrap: "wrap" }}>
              <span className={`pill ${online === "ok" ? "success" : "subtle"}`} title={onlineTitle}>
                {onlineLabel}
              </span>
            </div>
          </div>
          {authMode === "login" ? (
            <>
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
              <div className="auth-switch-row">
                <span className="muted small-note">Need access? Redeem an invite key.</span>
                <button type="button" className="secondary-link" onClick={() => switchMode("signup")}>
                  Register
                </button>
              </div>
            </>
          ) : (
            <>
              <form className="auth-form" onSubmit={handleSignup}>
                <div className="auth-subhead">Make an account</div>
                <p className="muted small-note">Redeem your invite key to create a clinic login.</p>
                <label className="field">
                  <span>Invite key</span>
                  <input
                    id="signup-invite"
                    name="signup-invite"
                    value={inviteToken}
                    onChange={(e) => setInviteToken(e.target.value)}
                    autoComplete="one-time-code"
                    required
                  />
                </label>
                <label className="field">
                  <span>Username</span>
                  <input
                    id="signup-username"
                    name="signup-username"
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    autoComplete="username"
                    required
                  />
                </label>
                <label className="field">
                  <span>Password</span>
                  <input
                    id="signup-password"
                    name="signup-password"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    autoComplete="new-password"
                    required
                  />
                </label>
                <button type="submit" disabled={isCreating}>
                  {isCreating ? "Creating account..." : "Create account"}
                </button>
                {signupStatus && (
                  <p className={`status ${signupTone !== "default" ? signupTone : ""}`}>{signupStatus}</p>
                )}
              </form>
              <div className="auth-switch-row">
                <span className="muted small-note">Already have a login?</span>
                <button type="button" className="secondary-link" onClick={() => switchMode("login")}>
                  Back to login
                </button>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
