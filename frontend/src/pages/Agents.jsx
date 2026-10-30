import { useNavigate } from "react-router";
import { AGENTS, AGENT_ORDER } from "../agents";
import { firstSentence } from "../format";
import { AgentAvatar } from "../icons";
import { useMayl } from "../state";

// Two counts per agent, all computed from this session's activity (see /api/stats).
function statsFor(key, a) {
  if (!a) return [];
  if (key === "lead") {
    const { followed, decided } = a.accepted || {};
    return [[a.recommendations, "Recommendations"],
      [decided ? `${Math.round((followed / decided) * 100)}%` : "–", decided ? "Accepted by humans" : "Accepted (no decisions yet)"]];
  }
  if (key === "domain") return [[a.answers, "Questions answered"], [a.escalations, "Sent to the expert"]];
  return [[a.reviews, "Changes reviewed"], [a.documents, "Knowledge docs"]];
}

export default function Agents() {
  const { stats } = useMayl();
  const navigate = useNavigate();
  return (
    <main className="page">
      <div className="page-h">
        <h1>Your agents</h1>
        <span className="muted">Each team has an agent that speaks for it. They review every change in parallel, cite their sources, and the Lead Agent recommends. You decide.</span>
      </div>

      <div className="agent-cards">
        {AGENT_ORDER.map((k) => {
          const a = AGENTS[k];
          const s = stats?.agents?.[k];
          return (
            <article key={k} className="agent-card" style={{ borderTopColor: a.color }}>
              <div className="row"><AgentAvatar agent={k} size={48} />
                <span className="stack-2"><span className="title-md">{a.name}</span><span className="muted small">{a.subtitle}</span></span></div>
              <p className="quote">“{a.quote}”</p>
              <div className="stack-6"><span className="eyebrow">Owns</span><span className="small">{a.owns}</span></div>
              <div className="skills">{a.skills.map((x) => <span key={x} style={{ background: a.soft, color: a.ink }}>{x}</span>)}</div>
              <div className="agent-stats">
                {statsFor(k, s).map(([v, label]) => <span key={label}><b>{v}</b><small>{label}</small></span>)}
              </div>
              <span className="latest" style={{ color: a.ink }}>
                <i className="dot" style={{ background: a.color }} />
                {s?.latest ? `${firstSentence(s.latest.text)}` : "No activity yet in this session"}
              </span>
              <button className="btn outline" onClick={() => navigate(`/chat?agent=${k}`)}>{k === "domain" ? "Chat with" : "Ask"} {a.name}</button>
            </article>
          );
        })}
      </div>

      <section className="dark-card band">
        <span className="stack-4 grow">
          <span className="h-sm">How they work together</span>
          <span className="dim small">A change comes in → only the affected agents review it, in parallel → the Lead Agent recommends → you decide</span>
        </span>
        <span className="flow">
          <AgentAvatar agent="ds" size={30} /><AgentAvatar agent="engineer" size={30} /><AgentAvatar agent="domain" size={30} />
          <i className="flow-line" /><AgentAvatar agent="lead" size={30} /><i className="flow-line" /><span className="you">You</span>
        </span>
      </section>
    </main>
  );
}
