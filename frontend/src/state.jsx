import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { byUrgency } from "./format";

const Ctx = createContext(null);

function savedRole() {
  try { return window.localStorage.getItem("mayl-role") || "lead"; } catch { return "lead"; }
}

// Session-wide data every page reads: products, my inbox, stats and the agent mode.
// `tick` changes after every refresh so pages with their own fetches reload too.
export function MaylProvider({ children }) {
  const [role, setRoleState] = useState(savedRole);
  const [products, setProducts] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [stats, setStats] = useState(null);
  const [mode, setMode] = useState(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);

  const setRole = (r) => {
    setRoleState(r);
    try { window.localStorage.setItem("mayl-role", r); } catch { /* per-visitor convenience only */ }
  };

  const refresh = useCallback(async () => {
    try {
      const [ps, ib, st] = await Promise.all([api.products(), api.inbox(role), api.stats()]);
      setProducts(ps); setInbox([...ib].sort(byUrgency)); setStats(st); setError("");
    } catch {
      setError("Can't reach the API. If it's just waking up, wait about 30 seconds and refresh.");
    }
    setTick((t) => t + 1);
  }, [role]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { api.health().then((h) => setMode(h.mode)).catch(() => {}); }, []);

  const restart = async () => {
    await api.reset();
    try {
      Object.keys(window.sessionStorage).filter((k) => k.startsWith("mayl-chat:")).forEach((k) => window.sessionStorage.removeItem(k));
    } catch { /* nothing stored */ }
    await refresh();
  };

  return (
    <Ctx.Provider value={{ role, setRole, products, inbox, stats, mode, error, tick, refresh, restart }}>
      {children}
    </Ctx.Provider>
  );
}

export const useMayl = () => useContext(Ctx);

// Fetch something that depends on the session data; reloads after every refresh().
export function useLoad(load, deps) {
  const { tick } = useMayl();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    load().then((d) => { if (live) { setData(d); setFailed(false); } }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [tick, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, failed };
}
