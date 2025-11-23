import StaffPlanner from "./pages/StaffPlanner";
import { useEffect, useState } from "react";

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const logoSrc = theme === "light" ? "/logo-light.svg" : "/logo-dark.svg";

  useEffect(() => {
    document.body.dataset.theme = theme;
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
        <button
          className="secondary-btn"
          onClick={() => setTheme(theme === "light" ? "dark" : "light")}
        >
          {theme === "light" ? "Dark mode" : "Light mode"}
        </button>
      </header>
      <StaffPlanner />
    </main>
  );
}
