import { useEffect, useRef, useState } from "react";
import { chatTarget } from "../agents";
import { api } from "../api";
import { textDir } from "../format";
import { AgentAvatar, Icon } from "../icons";

const storeKey = (pid, agent) => `mayl-chat:${pid}:${agent}`;

function load(pid, agent) {
  try { return JSON.parse(window.sessionStorage.getItem(storeKey(pid, agent))) || []; } catch { return []; }
}

// One conversation per project + agent, kept for this browser session.
export function useConversation(pid, agent) {
  const [state, setState] = useState(() => ({ key: storeKey(pid, agent), messages: load(pid, agent) }));
  const [busy, setBusy] = useState(false);
  const key = storeKey(pid, agent);
  const messages = state.key === key ? state.messages : load(pid, agent);

  const save = (next) => {
    setState({ key, messages: next });
    try { window.sessionStorage.setItem(key, JSON.stringify(next)); } catch { /* kept in memory only */ }
  };

  const ask = async (question) => {
    const q = question.trim();
    if (!q || busy) return;
    const withQ = [...messages, { from: "you", text: q }];
    save(withQ);
    setBusy(true);
    try {
      const a = await api.ask(pid, q, agent);
      save([...withQ, { from: agent, text: a.answer, sources: a.sources.map((s) => s.source), escalated: a.escalated, mode: a.mode }]);
    } catch (e) {
      save([...withQ, { from: agent, text: e.message || "I couldn't answer just now. Try again.", error: true }]);
    } finally { setBusy(false); }
  };
  return { messages, ask, busy };
}

export function sourceLabel(source, titles) {
  const [file, section] = source.split(" › ");
  const title = titles?.[file];
  return title ? `${title} › ${section}` : source;
}

export function Message({ m, titles }) {
  if (m.from === "you") return <div className="bubble you" {...textDir(m.text)}>{m.text}</div>;
  const a = chatTarget(m.from);
  return (
    <div className="answer-row">
      <AgentAvatar agent={m.from} size={30} />
      <div className={`bubble agent${m.escalated ? " escalated" : ""}${m.error ? " failed" : ""}`} style={{ borderLeftColor: m.escalated ? "#E7A548" : a.color === "#E6EAF3" ? "#C9D1E6" : a.color }}>
        <span {...textDir(m.text)}>{m.text}</span>
        {m.sources?.length > 0 && (
          <div className="cites">{m.sources.map((s, i) => <span key={i} className="cite" style={{ color: a.ink, background: a.soft }}>{sourceLabel(s, titles)}</span>)}</div>
        )}
        {m.escalated && <span className="pill t-warn">Escalated to the Domain Expert</span>}
      </div>
    </div>
  );
}

export function Composer({ onSend, busy, placeholder, compact = false }) {
  const [text, setText] = useState("");
  return (
    <form className={`composer${compact ? " compact" : ""}`} onSubmit={(e) => { e.preventDefault(); onSend(text); setText(""); }}>
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} aria-label={placeholder} {...textDir(text)} />
      <button className="send" aria-label="Send" disabled={busy || !text.trim()}><Icon name="send" color="#FFFFFF" size={compact ? 16 : 18} stroke={2.4} /></button>
    </form>
  );
}

export function MessageList({ messages, busy, intro, agent, titles }) {
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [messages.length, busy]);
  return (
    <div className="messages">
      {intro && <Message m={{ from: agent, text: intro }} />}
      {messages.map((m, i) => <Message key={i} m={m} titles={titles} />)}
      {busy && <div className="answer-row"><AgentAvatar agent={agent} size={30} /><div className="bubble agent typing"><span /><span /><span /></div></div>}
      <div ref={end} />
    </div>
  );
}

export function introFor(agent, product) {
  if (!product) return "";
  const expert = product.expert || "the domain expert";
  return {
    lead: `I keep ${product.name} on its priorities and deadline. Ask me what matters most or why we decided something.`,
    ds: `I speak for data science on ${product.name}: data, labels, models and evaluation.`,
    engineer: `I guard the engine for ${product.name}: contracts, latency, hardware and how long past changes took.`,
    domain: `Hi, I speak for ${expert}. Ask me about the rules, in Arabic or English. Anything new goes to the real expert.`,
    project: `Ask anything about ${product.name}'s history: decisions, documents and what the agents did.`,
  }[agent];
}
