import StaffPlanner from "./pages/StaffPlanner";
import { useEffect, useState } from "react";

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  // Use dark logo on dark background, light logo on light background
  const logoSrc = theme === "dark" ? "/logo-dark-inline.png" : "/logo-light-inline.png";

  useEffect(() => {
    document.body.dataset.theme = theme;
    // Update favicon/title based on theme using brand kit icons
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
    <main className="app-shell">
      <header className="hero app-header-centered">
        <div className="brand-centered">
          <img src={logoSrc} alt="ShiftPilot logo" className="hero-logo" />
          <div className="hero-text">
            {/* <p className="eyebrow">ShiftPilot</p> */}
            <h1>Clinic Scheduler Platform</h1>
            <p className="muted">React + FastAPI rewrite in progress. Edits stay local; APIs power the scheduling.</p>
          </div>
        </div>
        <button className="secondary-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
      </header>
      <StaffPlanner />
    </main>
  );
}
