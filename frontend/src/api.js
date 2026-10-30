const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

// Each visitor gets their own demo state on the server.
let SESSION = "s-" + Math.random().toString(36).slice(2, 12);
try {
  const saved = window.localStorage.getItem("mayl-session");
  if (saved) SESSION = saved; else window.localStorage.setItem("mayl-session", SESSION);
} catch { /* storage unavailable: keep in-memory session */ }

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", "X-Session": SESSION },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

export const assetUrl = (path) => BASE + path;

export const api = {
  products: () => req("/api/products"),
  product: (id) => req(`/api/products/${id}`),
  details: (id) => req(`/api/products/${id}/details`),
  stats: () => req("/api/stats"),
  inbox: (role) => req(`/api/inbox/${role}`),
  propose: (id, body) => req(`/api/products/${id}/proposals`, { method: "POST", body }),
  decide: (cid, body) => req(`/api/proposals/${cid}/decide`, { method: "POST", body }),
  intake: (id) => req(`/api/products/${id}/intake`, { method: "POST" }),
  confirm: (id, answers) => req(`/api/products/${id}/confirm`, { method: "POST", body: { answers } }),
  ask: (id, question, agent) => req(`/api/products/${id}/ask`, { method: "POST", body: { question, agent } }),
  rerun: (cid) => req(`/api/proposals/${cid}/rerun`, { method: "POST" }),
  health: () => req("/api/health"),
  reset: () => req("/api/reset", { method: "POST" }),
};
