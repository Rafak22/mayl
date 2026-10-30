import { useCallback, useEffect, useMemo, useState } from "react";
import { ReactFlow, Background, Controls, MarkerType, Position } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api } from "./api";
import "./App.css";

const ROLES = [
  { id: "lead", name: "AI Lead" },
  { id: "ds", name: "Data Scientist" },
  { id: "engineer", name: "AI Engineer" },
  { id: "domain", name: "Domain Expert" },
];
const ROLE_NAME = Object.fromEntries(ROLES.map((r) => [r.id, r.name]));
const STATE_LABEL = {
  healthy: "Healthy", bottleneck: "Bottleneck", new: "New", handoff: "Handoff ready",
  building: "Engine in progress", resolved: "Resolved",
};

export default function App() {
  const [role, setRole] = useState("ds");
  const [products, setProducts] = useState([]);
  const [pid, setPid] = useState("fraud");
  const [product, setProduct] = useState(null);
  const [inbox, setInbox] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [card, setCard] = useState(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [ps, p, ib] = await Promise.all([api.products(), api.product(pid), api.inbox(role)]);
      setProducts(ps); setProduct(p); setInbox(ib); setError("");
    } catch (e) {
      setError("Can't reach the API. If it's just waking up, wait ~30 s and refresh.");
    }
  }, [pid, role]);

  useEffect(() => { refresh(); }, [refresh]);
  const [queued, setQueued] = useState(null);
  useEffect(() => { setSelectedNode(null); setCard(queued); setQueued(null); }, [pid]); // eslint-disable-line

  const openCard = (c) => { setSelectedNode(null); setCard(c); };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="dot" />Relay <small>agentic handoffs</small></div>
        <div className="roles" role="tablist" aria-label="View as">
          {ROLES.map((r) => (
            <button key={r.id} className={`role ${role === r.id ? "on" : ""}`} data-role={r.id}
              onClick={() => setRole(r.id)}>{r.name}</button>
          ))}
        </div>
        <button className="ghost" onClick={async () => { await api.reset(); setCard(null); refresh(); }}>
          Reset demo
        </button>
      </header>

      {error && <div className="banner">{error}</div>}

      <div className="layout">
        <aside className="portfolio">
          <h3>Products</h3>
          {products.map((p) => (
            <button key={p.id} className={`prod ${pid === p.id ? "on" : ""}`} onClick={() => setPid(p.id)}>
              <span className={`state s-${p.state}`}>{STATE_LABEL[p.state] || p.state}</span>
              <strong>{p.name}</strong>
              <span className="muted">{p.domain}{p.pending ? ` · ${p.pending} decision${p.pending > 1 ? "s" : ""} pending` : ""}</span>
            </button>
          ))}
        </aside>

        <main className="main">
          {product && (
            <>
              <ProductHeader product={product} />
              {product.nodes.length === 0 ? (
                <Intake product={product} role={role} onDone={refresh} />
              ) : (
                <ProjectMap product={product} role={role} highlight={card?.affected}
                  onSelect={(n) => { setCard(null); setSelectedNode(n); }} />
              )}
              {selectedNode && (
                <ProposePanel node={selectedNode} role={role} pid={product.id}
                  onClose={() => setSelectedNode(null)}
                  onCard={(c) => { openCard(c); refresh(); }} />
              )}
              {card && (
                <ImpactCard card={card} role={role} onClose={() => setCard(null)}
                  onDecided={(c) => { setCard(c); refresh(); }} />
              )}
            </>
          )}
        </main>

        <aside className="side">
          <section>
            <h3>My inbox <span className="count">{inbox.length}</span></h3>
            {inbox.length === 0 && <p className="muted">Nothing needs you. The agents have it.</p>}
            {inbox.map((c) => (
              <button key={c.id} className="inbox-item" onClick={() => { if (c.product_id === pid) openCard(c); else { setQueued(c); setPid(c.product_id); } }}>
                <span className={`risk r-${c.risk}`}>{c.risk}</span>
                <strong>{c.title}</strong>
                <span className="muted">from {c.proposer_name} · {products.find((p) => p.id === c.product_id)?.name}</span>
              </button>
            ))}
          </section>
          {product && <Ask pid={product.id} />}
          {product && (
            <section>
              <h3>Activity</h3>
              <ul className="feed">
                {product.activity.map((a, i) => (
                  <li key={i} className={`k-${a.kind}`}><b>{a.actor}</b> {a.text}</li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}

function ProductHeader({ product }) {
  const o = product.objective;
  return (
    <div className="phead">
      <div>
        <h2>{product.name}</h2>
        <p className="muted">{product.summary}</p>
      </div>
      {o && (
        <div className="chips">
          <span className="chip">🎯 {o.success_metric}</span>
          <span className="chip">⏱ {o.deadline}</span>
          <span className="chip">Priority: {o.priorities.join(" > ")}</span>
        </div>
      )}
    </div>
  );
}

function ProjectMap({ product, role, highlight, onSelect }) {
  const hl = useMemo(() => new Set(highlight || []), [highlight]);
  const nodes = product.nodes.map((n) => ({
    id: n.id,
    position: { x: n.position.x * 0.82, y: n.position.y * 0.9 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: { label: <NodeBox n={n} mine={n.owner === role || role === "lead"} /> },
    className: `fnode o-${n.owner} st-${n.status} ${hl.has(n.id) ? "hl" : ""} ${n.owner === role || role === "lead" ? "mine" : "other"}`,
  }));
  const edges = product.edges.map((e, i) => ({
    id: `e${i}`, source: e.source, target: e.target,
    animated: hl.has(e.source) && hl.has(e.target),
    style: e.kind === "constrains" ? { strokeDasharray: "5 4" } : undefined,
    label: e.kind === "constrains" ? "constrains" : undefined,
    markerEnd: { type: MarkerType.ArrowClosed },
  }));
  return (
    <div className="map">
      <div className="legend">
        {ROLES.map((r) => <span key={r.id} className={`lg o-${r.id}`}>{r.name}</span>)}
        <span className="muted">Tap a node to propose a change</span>
      </div>
      <ReactFlow key={product.id + product.nodes.length} nodes={nodes} edges={edges} fitView
        fitViewOptions={{ padding: 0.15 }} minZoom={0.2} proOptions={{ hideAttribution: true }}
        nodesDraggable={false} onNodeClick={(_, n) => onSelect(product.nodes.find((x) => x.id === n.id))}>
        <Background gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

function NodeBox({ n }) {
  return (
    <div className="nbox">
      <span className="nkind">{n.kind} · {ROLE_NAME[n.owner]}</span>
      <strong>{n.label}</strong>
      {n.status !== "ok" && <span className="nstat">{n.status}</span>}
    </div>
  );
}

function ProposePanel({ node, role, pid, onClose, onCard }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (body) => {
    setBusy(true);
    try { onCard(await api.propose(pid, { node_id: node.id, role, ...body })); }
    finally { setBusy(false); }
  };
  return (
    <div className="panel">
      <div className="panel-h">
        <div><span className="muted">{node.kind} · owned by {ROLE_NAME[node.owner]}</span><h3>{node.label}</h3></div>
        <button className="ghost" onClick={onClose}>✕</button>
      </div>
      <p>{node.description}</p>
      <h4>Propose a change as {ROLE_NAME[role]}</h4>
      {node.change_options.map((o) => (
        <button key={o.id} disabled={busy} className="opt" onClick={() => send({ option_id: o.id })}>
          {o.label}<span className="muted">{o.rationale}</span>
        </button>
      ))}
      <div className="custom">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Or describe your own change…" />
        <button disabled={busy || !text.trim()} onClick={() => send({ custom_text: text })}>Ask the agents</button>
      </div>
    </div>
  );
}

function Delta({ d }) {
  const entries = Object.entries(d || {});
  if (!entries.length) return null;
  return (
    <div className="deltas">
      {entries.map(([k, v]) => (
        <span key={k} className={`delta ${(k.includes("false") || k.includes("latency")) ? (v < 0 ? "good" : "bad") : (v >= 0 ? "good" : "bad")}`}>
          {k.replace(/_/g, " ")} {v > 0 ? "+" : ""}{v}{k.includes("latency") ? (k.endsWith("min") ? " min" : " ms") : "%"}
        </span>
      ))}
    </div>
  );
}

function ImpactCard({ card, role, onClose, onDecided }) {
  const canDecide = card.status === "pending" && (card.approvers.includes(role) || role === "lead");
  const decide = async (decision) => onDecided(await api.decide(card.id, { role, decision }));
  const verdict = { works: "Works", works_with_changes: "Works, with changes in other teams", conflict: "Conflict found" }[card.verdict];
  return (
    <div className="panel impact">
      <div className="panel-h">
        <div>
          <span className="muted">{card.kind === "handoff" ? "Handoff" : "Change proposal"} from {card.proposer_name} · {card.node_label}</span>
          <h3>{card.title}</h3>
        </div>
        <button className="ghost" onClick={onClose}>✕</button>
      </div>
      <div className="row">
        <span className={`risk r-${card.risk}`}>{card.risk} risk</span>
        <span className={`verdict v-${card.verdict}`}>{verdict}</span>
        <span className="status">{card.status.replace(/_/g, " ")}</span>
      </div>
      {card.rationale && <p className="muted">{card.rationale}</p>}
      <Delta d={card.metric_delta} />
      {card.responses.length > 0 && (
        <div className="responses">
          {card.responses.map((r) => (
            <div key={r.team} className={`resp o-${r.team}`}>
              <div className="resp-h"><b>{r.agent}</b><span>{r.effort_text}</span></div>
              <p>{r.message}</p>
            </div>
          ))}
        </div>
      )}
      {card.alternative && (
        <div className="alt">
          <b>Cheaper alternative</b>
          <p>{card.alternative.label} · {card.alternative.effort_days} day{card.alternative.effort_days === 1 ? "" : "s"}</p>
          <Delta d={card.alternative.metric_delta} />
        </div>
      )}
      {card.status === "pending" && (
        <p className="muted">Waiting on: {card.approvers.map((a) => ROLE_NAME[a]).join(", ")}</p>
      )}
      {canDecide && (
        <div className="actions">
          <button className="primary" onClick={() => decide("approve")}>Approve</button>
          {card.alternative && <button onClick={() => decide("alternative")}>Use cheaper alternative</button>}
          <button className="ghost" onClick={() => decide("reject")}>Reject</button>
        </div>
      )}
    </div>
  );
}

function Intake({ product, role, onDone }) {
  const [res, setRes] = useState(null);
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const read = async () => {
    setBusy(true);
    const r = await api.intake(product.id);
    setRes(r);
    setAnswers(Object.fromEntries(r.gaps.map((g) => [g.id, g.suggested])));
    setBusy(false);
  };
  const confirm = async () => { setBusy(true); await api.confirm(product.id, answers); setBusy(false); onDone(); };
  return (
    <div className="intake">
      <h3>Objective intake</h3>
      <div className="docs">{product.documents.map((d) => <span key={d.name} className="doc">📄 {d.name}</span>)}</div>
      {!res && <button className="primary" disabled={busy} onClick={read}>{busy ? "Reading…" : "Let the agent read the documents"}</button>}
      {res && (
        <>
          <table className="spec">
            <tbody>
              {Object.entries(res.spec).map(([k, v]) => (
                <tr key={k}>
                  <th>{k.replace(/_/g, " ")}</th>
                  <td>{Array.isArray(v.value) ? v.value.join(" · ") : v.value}{v.inferred && <em> (inferred)</em>}</td>
                  <td className="muted">{v.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h4>Only these need a human</h4>
          {res.gaps.map((g) => (
            <label key={g.id} className="gap">
              {g.question}
              <input value={answers[g.id] || ""} onChange={(e) => setAnswers({ ...answers, [g.id]: e.target.value })} />
            </label>
          ))}
          {role === "lead"
            ? <button className="primary" disabled={busy} onClick={confirm}>{busy ? "Agents building…" : "Confirm and let the agents build"}</button>
            : <p className="muted">Switch to AI Lead to confirm.</p>}
        </>
      )}
    </div>
  );
}

function Ask({ pid }) {
  const [q, setQ] = useState("");
  const [a, setA] = useState(null);
  useEffect(() => { setA(null); }, [pid]);
  return (
    <section>
      <h3>Ask the project</h3>
      <form className="custom" onSubmit={async (e) => { e.preventDefault(); if (q.trim()) setA(await api.ask(pid, q)); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Why did we…?" />
        <button>Ask</button>
      </form>
      {a && (
        <div className="answer">
          <p>{a.answer}</p>
          {a.sources.map((s, i) => <span key={i} className="muted src">↳ {s.source}</span>)}
        </div>
      )}
    </section>
  );
}
