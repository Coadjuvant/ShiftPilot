import { Routes, Route, Link, useLocation, Navigate } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import StaffPlanner from "./pages/StaffPlanner";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Features from "./pages/Features";
import Contact from "./pages/Contact";
import { logout, getStoredToken } from "./api/client";

export default function App() {
  const supportEmail = "support@shiftpilot.me";
  const [theme, setTheme] = useState<"light" | "dark">(() => localStorage.getItem("theme") === "light" ? "light" : "dark");
  const [logoutError, setLogoutError] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isAuthed, setIsAuthed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return Boolean(getStoredToken());
  });
  const [authUser, setAuthUser] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("auth_user") || "";
  });
  const [supportCopyLabel, setSupportCopyLabel] = useState("Copy email");
  const location = useLocation();
  const syncAuthState = useCallback(() => {
    if (typeof window === "undefined") return;
    const token = getStoredToken();
    setIsAuthed(Boolean(token));
    setAuthUser(localStorage.getItem("auth_user") || "");
  }, []);

  useEffect(() => {
    document.body.dataset.theme = theme;
    localStorage.setItem("theme", theme);
    const link =
      document.querySelector<HTMLLinkElement>("link[rel='icon']") ||
      document.querySelector<HTMLLinkElement>("link[rel='shortcut icon']") ||
      document.createElement("link");
    link.rel = "icon";
    link.type = "image/svg+xml";
    link.href = "/brand/favicon.svg";
    if (!link.parentNode) document.head.appendChild(link);
    document.title = "ShiftPilot";
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = () => {
      syncAuthState();
    };
    window.addEventListener("storage", handler);
    handler();
    const interval = window.setInterval(syncAuthState, 60_000);
    return () => {
      window.removeEventListener("storage", handler);
      window.clearInterval(interval);
    };
  }, [syncAuthState]);

  useEffect(() => {
    syncAuthState();
  }, [location, syncAuthState]);

  const appBuild = (import.meta as any).env?.VITE_APP_BUILD || "";
  const gitCommit = (import.meta as any).env?.VITE_GIT_COMMIT || "";
  const versionLabel = appBuild || "dev";
  const githubUrl = gitCommit
    ? `https://github.com/Coadjuvant/ShiftPilot/commit/${gitCommit}`
    : null;

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      setLogoutError("Could not end your session. Check your connection and try again.");
      return;
    }
    setIsAuthed(false);
    setAuthUser("");
    window.location.href = "/";
  };

  const handleCopySupportEmail = async () => {
    if (typeof window === "undefined") return;
    const fallbackLabel = "Copy email";
    try {
      await navigator.clipboard.writeText(supportEmail);
      setSupportCopyLabel("Copied");
    } catch (err) {
      console.warn("Failed to copy support email", err);
      setSupportCopyLabel("Copy failed");
    }
    window.setTimeout(() => setSupportCopyLabel(fallbackLabel), 2000);
  };

  return (
    <div className={`page-shell ${theme === "dark" ? "dark" : "light"}`}>
      <div className="hero-wrap">
        <header className="top-nav">
          <div className="nav-trigger">
            <button
              className="menu-toggle"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle menu"
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation"
              onKeyDown={(event) => { if (event.key === "Escape") setMobileOpen(false); }}
            >
              <span className="sr-only">{mobileOpen ? "Close menu" : "Open menu"}</span>
              {mobileOpen ? (
                <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              )}
            </button>
            <nav
              id="mobile-navigation"
              aria-label="Main navigation"
              className={`nav-links nav-links-mobile ${mobileOpen ? "open" : ""}`}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setMobileOpen(false);
                  document.querySelector<HTMLButtonElement>(".menu-toggle")?.focus();
                }
              }}
            >
              <Link to="/" onClick={() => setMobileOpen(false)}>
                Home
              </Link>
              <Link to="/planner" onClick={() => setMobileOpen(false)}>
                Planner
              </Link>
              <Link to="/features" onClick={() => setMobileOpen(false)}>
                Features
              </Link>
              <Link to="/contact" onClick={() => setMobileOpen(false)}>
                Contact
              </Link>
            </nav>
          </div>
          <Link to="/" className="brand-mark brand-link">
            <img src={`/brand/shiftpilot-banner-${theme}.svg`} alt="ShiftPilot" className="brand-logo" width="593" height="120" />
          </Link>
          <div className="nav-right">
            <button className="secondary-link theme-choice" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            <nav className="nav-links nav-links-desktop">
              <Link to="/">Home</Link>
              <Link to="/planner">Planner</Link>
              <Link to="/features">Features</Link>
              <Link to="/contact">Contact</Link>
            </nav>
            {isAuthed ? (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                {authUser ? <span className="pill subtle">Welcome back, {authUser}</span> : null}
                <button className="primary-chip nav-cta" onClick={handleLogout}>
                  Logout
                </button>
              </div>
            ) : (
              <Link className="primary-chip nav-cta" to="/login" onClick={() => setMobileOpen(false)}>
                Login
              </Link>
            )}
          </div>
        </header>

        {logoutError && <p role="alert">{logoutError}</p>}
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/planner" element={isAuthed ? <StaffPlanner /> : <Navigate to="/login" replace />} />
          <Route path="/features" element={<Features />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <footer className="site-footer">
          <div className="site-footer__inner">
            <div className="site-footer__links">
              <span>Support: {supportEmail}</span>
              <button type="button" className="secondary-link" onClick={handleCopySupportEmail}>
                {supportCopyLabel}
              </button>
            </div>
            <div className="site-footer__meta">
              {githubUrl ? (
                <a
                  href={githubUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="pill subtle"
                  style={{ textDecoration: "none", cursor: "pointer" }}
                >
                  Build {versionLabel}
                </a>
              ) : (
                <span className="pill subtle">Build {versionLabel}</span>
              )}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
