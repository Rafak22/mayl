import { useState } from "react";
import { HashRouter, NavLink, Navigate, Route, Routes, useNavigate } from "react-router";
import { AGENTS, ROLES } from "./agents";
import { LogoMark } from "./icons";
import { MaylProvider, useMayl } from "./state";
import Agents from "./pages/Agents";
import Chat from "./pages/Chat";
import Overview from "./pages/Overview";
import Project from "./pages/Project";
import Projects from "./pages/Projects";
import "./App.css";

// Hash routes work on any static host and from a QR code link, with no server rewrites.
export default function App() {
  return (
    <HashRouter>
      <MaylProvider>
        <Shell />
      </MaylProvider>
    </HashRouter>
  );
}

function Shell() {
  const { error } = useMayl();
  return (
    <div className="app">
      <Header />
      {error && <div className="banner">{error}</div>}
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:pid" element={<Project />} />
        <Route path="/projects/:pid/:tab" element={<Project />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

const NAV = [["/", "Overview"], ["/projects", "Projects"], ["/agents", "Agents"], ["/chat", "Chat"]];

function Header() {
  const { role, setRole, mode, restart } = useMayl();
  const [restarting, setRestarting] = useState(false);
  const navigate = useNavigate();
  const onRestart = async () => {
    setRestarting(true);
    try { await restart(); navigate("/"); } finally { setRestarting(false); }
  };
  return (
    <header className="topbar">
      <NavLink to="/" className="brand" aria-label="Mayl home">
        <LogoMark />
        <span className="brand-name">Mayl</span>
        <span className="brand-sep" />
        <span className="brand-ar" lang="ar">مَيْل</span>
      </NavLink>
      <nav className="nav" aria-label="Sections">
        {NAV.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}
      </nav>
      {mode && (
        <span className={`live-pill${mode === "live" ? "" : " demo"}`}><i />{mode === "live" ? "4 agents live" : "Demo agents"}</span>
      )}
      <div className="roles" role="group" aria-label="View as">
        {ROLES.map((r) => (
          <button key={r.id} className={role === r.id ? "on" : ""} aria-pressed={role === r.id}
            style={role === r.id ? { color: AGENTS[r.id].ink } : undefined} onClick={() => setRole(r.id)}>{r.name}</button>
        ))}
      </div>
      <button className="link-btn" onClick={onRestart} disabled={restarting}>{restarting ? "Restarting…" : "Restart demo"}</button>
    </header>
  );
}
