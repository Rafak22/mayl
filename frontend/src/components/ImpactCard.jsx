import { useEffect, useState } from "react";
import { AGENTS, ROLE_NAME } from "../agents";
import { api } from "../api";
import { REC_LABEL, cap, fmtDays, textDir } from "../format";
import { AgentAvatar, Icon } from "../icons";

// Side drawer on desktop, bottom sheet on phones.
export function Drawer({ title, kicker, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="drawer-wrap" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="drawer-h">
          <div><span className="muted small">{kicker}</span><h3>{title}</h3></div>
          <button className="icon-btn" aria-label="Close" onClick={onClose}><Icon name="close" /></button>
        </div>
        {children}
      </aside>
    </div>
  );
}

export function Thinking({ text = "The DS, Engineer and Domain agents are reviewing in parallel…" }) {
  return <div className="thinking"><span className="spin" />{text}</div>;
}

export function ProposePanel({ node, role, pid, onClose, onCard }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const send = async (body) => {
    setBusy(true); setError("");
    try { onCard(await api.propose(pid, { node_id: node.id, role, ...body })); }
    catch (e) { setError(e.message || "The agents couldn't review this change. Try again."); }
    finally { setBusy(false); }
  };
  return (
    <Drawer title={node.label} kicker={`${node.kind} · owned by ${ROLE_NAME[node.owner]}`} onClose={onClose}>
      <p>{node.description}</p>
      <h4>Propose a change as {ROLE_NAME[role]}</h4>
      {busy && <Thinking />}
      {error && <p className="error">{error}</p>}
      {node.change_options.map((o) => (
        <button key={o.id} disabled={busy} className="option" onClick={() => send({ option_id: o.id })}>
          <b>{o.label}</b><span className="muted">{o.rationale}</span>
        </button>
      ))}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); if (text.trim()) send({ custom_text: text }); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Or describe your own change…" aria-label="Describe your own change" />
        <button className="btn primary" disabled={busy || !text.trim()}>{busy ? "Reviewing…" : "Ask the agents"}</button>
      </form>
    </Drawer>
  );
}

function Delta({ d }) {
  const entries = Object.entries(d || {});
  if (!entries.length) return null;
  const UNITS = [["_ms", " ms"], ["_s", " s"], ["_min", " min"]];
  return (
    <div className="deltas">
      {entries.map(([k, v]) => {
        const [suffix, unit] = UNITS.find(([s]) => k.endsWith(s)) || ["", "%"];
        const lowerIsBetter = k.includes("false") || k.includes("latency") || k.includes("reply");
        const good = lowerIsBetter ? v <= 0 : v >= 0;
        return (
          <span key={k} className={`pill t-${good ? "good" : "bad"}`}>
            {k.slice(0, k.length - suffix.length).replace(/_/g, " ")} {v > 0 ? "+" : ""}{v}{unit}
          </span>
        );
      })}
    </div>
  );
}

const VERDICT = { works: "Works", works_with_changes: "Works, with changes in other teams", conflict: "Conflict found" };

export function ImpactCard({ card, role, live, onClose, onDecided }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const canDecide = card.status === "pending" && (card.approvers.includes(role) || role === "lead");
  const run = async (fn) => {
    setBusy(true); setError("");
    try { onDecided(await fn()); }
    catch (e) { setError(e.message || "Something went wrong. Try again."); }
    finally { setBusy(false); }
  };
  const rec = card.recommendation;
  const btn = (option, fallback = "btn") => (rec === option ? "btn primary recommended" : fallback);
  return (
    <Drawer title={card.title} onClose={onClose}
      kicker={`${card.kind === "handoff" ? "Handoff" : "Change proposal"} from ${card.proposer_name} · ${card.node_label}`}>
      {rec && card.kind !== "handoff" && (
        <div className="rec">
          <AgentAvatar agent="lead" size={28} />
          <div>
            <span className="rec-h"><b>Lead Agent recommends: {REC_LABEL[rec]}</b>
              <span className={`pill ${card.recommendation_mode === "live" ? "t-good" : "t-neutral"}`}>
                {card.recommendation_mode === "live" ? "Live" : "Rule-based"}</span></span>
            <p>{card.recommendation_reason}</p>
          </div>
        </div>
      )}
      <div className="pills">
        <span className={`pill risk-${card.risk}`}>{cap(card.risk)} risk</span>
        <span className={`pill v-${card.verdict}`}>{VERDICT[card.verdict]}</span>
        <span className="pill t-neutral">{cap(card.status.replace(/_/g, " "))}</span>
        {card.kind !== "handoff" && <span className={`pill ${card.mode === "live" ? "t-good" : "t-neutral"}`}>{card.mode === "live" ? "Live agents" : "Demo agents"}</span>}
      </div>
      {card.fallback_reason && <p className="muted small">Live agents were unavailable for this one, so the demo agents answered.</p>}
      {live && card.mode !== "live" && card.status === "pending" && card.kind !== "handoff" && (
        busy ? <Thinking /> : <button className="btn outline" onClick={() => run(() => api.rerun(card.id))}>Re-assess with live agents</button>
      )}
      {error && <p className="error">{error}</p>}
      {card.rationale && <p className="muted">{card.rationale}</p>}
      <Delta d={card.metric_delta} />
      {card.responses.length > 0 && (
        <div className="responses">
          {card.responses.map((r) => (
            <div key={r.team} className="response" style={{ borderLeftColor: AGENTS[r.team].color }}>
              <div className="response-h"><AgentAvatar agent={r.team} size={22} /><b>{AGENTS[r.team].name}</b><span>{r.effort_text}</span></div>
              <p {...textDir(r.message)}>{r.message}</p>
              {(r.tools_used?.length > 0 || r.evidence?.length > 0) && (
                <div className="evidence">
                  {r.tools_used?.length > 0 && <span>Tools: {[...new Set(r.tools_used)].join(", ")}</span>}
                  {r.evidence?.map((e, i) => <span key={i} className="cite">{e}</span>)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {card.alternative && (
        <div className="alt-box">
          <b>Cheaper alternative · {fmtDays(card.alternative.effort_days)}</b>
          <p>{card.alternative.label}</p>
          <Delta d={card.alternative.metric_delta} />
        </div>
      )}
      {card.status === "pending" && <p className="muted small">Waiting on: {card.approvers.map((a) => ROLE_NAME[a]).join(", ")}</p>}
      {canDecide && (
        <div className="actions">
          <button disabled={busy} className={btn("approve", rec ? "btn" : "btn primary")} onClick={() => run(() => api.decide(card.id, { role, decision: "approve" }))}>Approve</button>
          {card.alternative && <button disabled={busy} className={btn("alternative")} onClick={() => run(() => api.decide(card.id, { role, decision: "alternative" }))}>Use cheaper alternative</button>}
          <button disabled={busy} className={btn("reject", "btn ghost")} onClick={() => run(() => api.decide(card.id, { role, decision: "reject" }))}>Reject</button>
        </div>
      )}
    </Drawer>
  );
}
