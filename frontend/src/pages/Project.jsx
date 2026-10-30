import { useState } from "react";
import { Link, NavLink, useNavigate, useParams, useSearchParams } from "react-router";
import { AGENTS, AGENT_ORDER } from "../agents";
import { api } from "../api";
import { ActivityFeed } from "../components/Activity";
import { Composer, Message, introFor, useConversation } from "../components/Chat";
import { ImpactCard, ProposePanel } from "../components/ImpactCard";
import { InboxCard } from "../components/InboxCard";
import { Intake } from "../components/Intake";
import { MetricCards } from "../components/MetricCard";
import { ProjectMap } from "../components/ProjectMap";
import { STATE, cap, firstSentence, plural } from "../format";
import { AgentAvatar, Icon } from "../icons";
import { useLoad, useMayl } from "../state";
import { DataTab, KnowledgeTab } from "./ProjectData";

const TABS = [["map", "Project map"], ["data", "Data & solution"], ["knowledge", "Knowledge"], ["results", "Results"]];

export default function Project() {
  const { pid, tab = "map" } = useParams();
  const { products, mode, role, refresh } = useMayl();
  const { data: product, failed } = useLoad(() => api.product(pid), [pid]);
  const [params, setParams] = useSearchParams();
  const [node, setNode] = useState(null);
  const summary = products.find((p) => p.id === pid);

  if (failed) return <main className="page"><p className="error">This project couldn't be loaded. <Link to="/projects">Back to projects</Link></p></main>;
  if (!product || product.id !== pid) return <main className="page"><p className="muted">Loading…</p></main>;

  const cardId = params.get("card");
  const card = cardId && product.proposals.find((c) => c.id === cardId);
  const openCard = (c) => { setNode(null); setParams(c ? { card: c.id } : {}); };
  const o = product.objective;

  return (
    <div className={`project-page${tab === "map" ? " with-sides" : ""}`}>
      {tab === "map" && <ProductList products={products} current={pid} />}
      <main className="project-main">
        <div className="stack-10">
          <span className="crumb"><Link to="/projects">Projects</Link> › {product.name}</span>
          <h1>{product.name}</h1>
          <p className="lede">{product.summary}</p>
          {o && (
            <div className="chips">
              <span className="chip"><span className="muted">Goal</span> {o.success_metric}</span>
              <span className="chip"><span className="muted">Deadline</span> {o.deadline}</span>
              <span className="chip"><span className="muted">Priority</span> {(o.priorities || []).join(" › ")}</span>
            </div>
          )}
          <nav className="tabs" aria-label="Project tabs">
            {TABS.map(([id, label]) => <NavLink key={id} to={`/projects/${pid}/${id}`} className={tab === id ? "active" : ""}>{label}</NavLink>)}
          </nav>
        </div>

        {tab === "map" && (
          <>
            <MetricCards metrics={product.metrics} goals={product.metric_goals} />
            {product.nodes.length === 0
              ? <Intake product={product} role={role} onDone={refresh} />
              : <ProjectMap product={product} highlight={card?.affected} onSelect={(n) => { openCard(null); setNode(n); }} />}
            <AgentsOnProject product={product} />
          </>
        )}
        {tab === "data" && <DataTab pid={pid} />}
        {tab === "knowledge" && <KnowledgeTab pid={pid} />}
        {tab === "results" && (
          <section className="card placeholder">
            <Icon name="chart" size={22} color="#5D6788" />
            <b>Evaluation results coming soon</b>
            <span className="muted small">Accuracy and latency runs for each version will appear here.</span>
          </section>
        )}
      </main>
      {tab === "map" && <ProjectSide product={product} summary={summary} onOpen={openCard} />}

      {node && <ProposePanel node={node} role={role} pid={pid} onClose={() => setNode(null)}
        onCard={(c) => { openCard(c); refresh(); }} />}
      {card && <ImpactCard card={card} role={role} live={mode === "live"} onClose={() => openCard(null)}
        onDecided={(c) => { openCard(c); refresh(); }} />}
    </div>
  );
}

function ProductList({ products, current }) {
  return (
    <aside className="product-list" aria-label="Products">
      <span className="eyebrow">Products</span>
      {products.map((p) => {
        const s = STATE[p.state] || { label: p.state, tone: "neutral" };
        return (
          <Link key={p.id} to={`/projects/${p.id}`} className={`product-item${p.id === current ? " active" : ""}`}>
            <span className={`state-label t-${s.tone}`}><i className={`dot t-${s.tone}`} />{p.state === "bottleneck" ? "Bottleneck" : s.label}</span>
            <b>{p.name}</b>
            <span className="small muted">{p.domain}{p.pending ? ` · ${plural(p.pending, "decision")} pending` : ""}</span>
          </Link>
        );
      })}
    </aside>
  );
}

// What each agent said in the latest review of this project.
function AgentsOnProject({ product }) {
  const reviewed = product.proposals.filter((c) => c.responses.length && c.kind !== "handoff");
  const latest = reviewed.find((c) => c.status === "pending") || reviewed[reviewed.length - 1];
  return (
    <section className="stack-10" aria-label="Agents on this project">
      <div className="row"><h2 className="h-sm">Agents on this project</h2><Link className="push link" to="/agents">See all agents</Link></div>
      <div className="agent-grid">
        {AGENT_ORDER.map((k) => {
          const a = AGENTS[k];
          const r = latest?.responses.find((x) => x.team === k);
          let text = "No review on this project yet.";
          let status = "Standing by";
          if (k === "lead" && latest?.recommendation) {
            text = firstSentence(latest.recommendation_reason);
            status = `Recommended: ${latest.recommendation}`;
          } else if (r) {
            text = `${firstSentence(r.message)} ${r.effort_text !== "no work" ? `(${r.effort_text})` : ""}`;
            status = r.verdict === "conflict" || latest.conflicts.length && k === "domain" ? "Flagged a conflict"
              : r.evidence?.length ? `Reviewed · cited ${plural(r.evidence.length, "source")}` : "Reviewed";
          }
          return (
            <div key={k} className="agent-mini">
              <div className="row"><AgentAvatar agent={k} size={34} /><span className="stack-0"><b>{a.name}</b><span className="small muted">{a.tagline}</span></span></div>
              <span className="small body">{text}</span>
              <span className="small strong" style={{ color: a.ink }}>{status}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ProjectSide({ product, summary, onOpen }) {
  const { inbox, products } = useMayl();
  const navigate = useNavigate();
  const [agent, setAgent] = useState("domain");
  const { messages, ask, busy } = useConversation(product.id, agent);
  const last = messages.slice(-2);
  const nameOf = (id) => products.find((p) => p.id === id)?.name;
  const openInbox = (c) => (c.product_id === product.id ? onOpen(c) : navigate(`/projects/${c.product_id}?card=${c.id}`));

  return (
    <aside className="project-side" aria-label="Inbox, chat and activity">
      <section className="stack-10">
        <span className="h-sm row">My inbox <span className="count">{inbox.length}</span></span>
        {inbox.length === 0 && <p className="muted small">Nothing needs you. The agents have it.</p>}
        {inbox[0] && <InboxCard card={inbox[0]} productName={nameOf(inbox[0].product_id)} onOpen={() => openInbox(inbox[0])} />}
        {inbox.slice(1).map((c) => (
          <button key={c.id} className="inbox-row" onClick={() => openInbox(c)}>
            <span className={`pill risk-${c.risk}`}>{cap(c.risk)}</span><span className="grow">{c.title}</span>
          </button>
        ))}
      </section>

      <section className="card chat-mini" aria-label="Chat with agents">
        <div className="row"><Icon name="chat" size={18} color="#3A52B0" stroke={2} /><b>Chat with an agent</b>
          <Link className="push link small" to={`/chat?project=${product.id}&agent=${agent}`}>Open chat</Link></div>
        <div className="agent-picker" role="group" aria-label="Choose an agent">
          {AGENT_ORDER.map((k) => (
            <button key={k} className={agent === k ? "on" : ""} aria-pressed={agent === k} onClick={() => setAgent(k)}
              style={agent === k ? { borderColor: AGENTS[k].color, background: AGENTS[k].soft } : undefined}>
              <AgentAvatar agent={k} size={24} />{AGENTS[k].name}
            </button>
          ))}
        </div>
        <div className="mini-thread">
          {last.length ? last.map((m, i) => <Message key={i} m={m} />) : <Message m={{ from: agent, text: introFor(agent, summary || product) }} />}
          {busy && <p className="muted small">{AGENTS[agent].name} is answering…</p>}
        </div>
        <Composer compact onSend={ask} busy={busy} placeholder={`Message the ${AGENTS[agent].name}…`} />
      </section>

      <section className="stack-12">
        <h2 className="h-sm">Activity</h2>
        <ActivityFeed items={product.activity} />
      </section>
    </aside>
  );
}
