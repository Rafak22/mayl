import { useEffect, useMemo, useRef } from "react";
import { useSearchParams } from "react-router";
import { CHAT_TARGETS, chatTarget } from "../agents";
import { api } from "../api";
import { Composer, MessageList, introFor, useConversation } from "../components/Chat";
import { AgentAvatar } from "../icons";
import { useLoad, useMayl } from "../state";

// Knowledge scopes each chat target searches (matches rag.AGENT_SCOPES on the server).
const SCOPES = { lead: null, project: null, ds: ["ds", "shared"], engineer: ["engineer", "shared"], domain: ["domain", "shared"] };

export default function Chat() {
  const { products, mode } = useMayl();
  const [params, setParams] = useSearchParams();
  const pid = params.get("project") || products.find((p) => p.state === "bottleneck")?.id || products[0]?.id || "ppe";
  const agent = CHAT_TARGETS.some((t) => t.key === params.get("agent")) ? params.get("agent") : "domain";
  const product = products.find((p) => p.id === pid);
  const target = chatTarget(agent);
  const { messages, ask, busy } = useConversation(pid, agent);
  const { data: details } = useLoad(() => api.details(pid), [pid]);

  const titles = useMemo(() => Object.fromEntries((details?.documents || []).map((d) => [d.file, d.title])), [details]);
  // Suggested questions: section headings from the documents this agent can read.
  const suggestions = useMemo(() => {
    const docs = (details?.documents || []).filter((d) => !SCOPES[agent] || SCOPES[agent].includes(d.scope));
    const own = docs.filter((d) => d.scope !== "shared");
    return [...own, ...docs.filter((d) => d.scope === "shared")].flatMap((d) => d.sections.map((s) => s.heading)).slice(0, 3);
  }, [details, agent]);

  const choose = (next) => setParams({ project: pid, agent: next });
  // On phones the agent list is a sideways strip: keep the selected agent in view.
  const strip = useRef(null);
  useEffect(() => { strip.current?.querySelector(".on")?.scrollIntoView({ inline: "center", block: "nearest" }); }, [agent]);
  const description = agent === "domain" && product
    ? `Answers from ${product.expert}'s rules · sends anything new to the real expert`
    : target.chatHint;

  return (
    <div className="chat-page">
      <aside className="chat-side" aria-label="Agents">
        <label htmlFor="chat-project" className="eyebrow">Project</label>
        <select id="chat-project" value={pid} onChange={(e) => setParams({ project: e.target.value, agent })}>
          {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <span className="eyebrow pad-top">Talk to</span>
        <div className="chat-targets" ref={strip}>
          {CHAT_TARGETS.map((t) => (
            <button key={t.key} className={agent === t.key ? "on" : ""} aria-pressed={agent === t.key} onClick={() => choose(t.key)}
              style={agent === t.key ? { background: t.soft, boxShadow: `inset 0 0 0 1.5px ${t.key === "project" ? "#C9D1E6" : t.color}` } : undefined}>
              <AgentAvatar agent={t.key} size={36} />
              <span className="stack-0"><b>{t.name}</b>
                <span className="small muted">{t.key === "domain" && product ? `Speaks for ${product.expert}` : t.chatHint}</span></span>
            </button>
          ))}
        </div>
      </aside>

      <main className="chat-main">
        <div className="chat-h">
          <AgentAvatar agent={agent} size={40} />
          <span className="stack-0"><b className="title-sm">{target.name}</b><span className="small muted">{description}</span></span>
          {mode && <span className={`pill push ${mode === "live" ? "t-good" : "t-neutral"}`}>{mode === "live" ? "Live" : "Demo"}</span>}
        </div>
        <MessageList messages={messages} busy={busy} agent={agent} titles={titles} intro={introFor(agent, product)} />
        <div className="chat-foot">
          {suggestions.length > 0 && (
            <div className="suggestions">
              {suggestions.map((s) => <button key={s} disabled={busy} onClick={() => ask(s)}>{s}</button>)}
            </div>
          )}
          <Composer onSend={ask} busy={busy} placeholder={`Message the ${target.name}, in Arabic or English…`} />
        </div>
      </main>
    </div>
  );
}
