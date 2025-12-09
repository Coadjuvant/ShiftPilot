import { Routes, Route, Link, useLocation, Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import StaffPlanner from "./pages/StaffPlanner";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import PlaceholderPage from "./pages/Placeholder";

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    document.body.dataset.theme = theme;
    const link =
      document.querySelector<HTMLLinkElement>("link[rel='icon']") ||
      document.querySelector<HTMLLinkElement>("link[rel='shortcut icon']") ||
      document.createElement("link");
    link.rel = "icon";
    link.type = "image/x-icon";
    link.href = theme === "dark" ? "/favicon-dark.ico" : "/favicon-light.ico";
    if (!link.parentNode) document.head.appendChild(link);
    document.title = "Clinic Scheduler";
  }, [theme]);

  return (
    <div className={`page-shell ${theme === "dark" ? "dark" : "light"}`}>
      <button
        className="theme-fab"
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        aria-label="Toggle theme"
        title="Toggle theme"
      >
        <span className={`theme-icon ${theme === "dark" ? "dark" : "light"}`} aria-hidden="true" />
      </button>
      <div className="hero-wrap">
        <header className="top-nav">
          <div className="nav-trigger">
            <button className="menu-toggle" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Toggle menu">
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
            <nav className={`nav-links nav-links-mobile ${mobileOpen ? "open" : ""}`}>
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
            <img src={theme === "dark" ? "/logo-dark.png" : "/logo-light.png"} alt="ShiftPilot logo" className="brand-logo" />
            <span className="brand-name">ShiftPilot</span>
          </Link>
          <div className="nav-right">
            <nav className="nav-links nav-links-desktop">
              <Link to="/">Home</Link>
              <Link to="/planner">Planner</Link>
              <Link to="/features">Features</Link>
              <Link to="/contact">Contact</Link>
            </nav>
            <Link
              className="primary-chip nav-cta"
              to={location.pathname === "/planner" ? "/" : "/planner"}
              onClick={() => setMobileOpen(false)}
            >
              {location.pathname === "/planner" ? "Back to Home" : "Launch Planner"}
            </Link>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/planner" element={<StaffPlanner />} />
          <Route path="/features" element={<PlaceholderPage title="Features" />} />
          <Route path="/contact" element={<PlaceholderPage title="Contact" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}
