import { useState } from "react";
import { Link } from "react-router";
import { STATE, fmtMetric, metricStatus, plural, recPhrase } from "../format";
import { Icon } from "../icons";
import { useMayl } from "../state";

const FILTERS = [
  ["all", "All", () => true],
  ["decision", "Needs decision", (p, pending) => pending > 0],
  ["healthy", "Healthy", (p) => p.state === "healthy" || p.state === "resolved"],
  ["new", "New", (p) => ["new", "handoff", "building"].includes(p.state)],
];

export default function Projects() {
  const { products, inbox } = useMayl();
  const [filter, setFilter] = useState("all");
  const pendingFor = (p) => inbox.filter((c) => c.product_id === p.id);
  const test = FILTERS.find(([id]) => id === filter)[2];
  const shown = products.filter((p) => test(p, pendingFor(p).length));

  return (
    <main className="page narrow">
      <div className="page-h-row">
        <div className="stack-6 grow">
          <h1>Projects</h1>
          <span className="muted">{plural(products.length, "AI product")} · {plural(inbox.length, "decision")} waiting for you</span>
        </div>
        <div className="filters" role="group" aria-label="Filter">
          {FILTERS.map(([id, label]) => (
            <button key={id} className={filter === id ? "on" : ""} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>
          ))}
        </div>
      </div>

      <div className="project-grid">
        {shown.map((p) => <ProjectCard key={p.id} p={p} pending={pendingFor(p)} />)}
        <div className="new-project" aria-disabled="true">
          <span className="new-icon"><Icon name="plus" size={20} color="#3A52B0" /></span>
          <b>New project</b>
          <span className="small">Upload a brief, the agents do the rest</span>
          <span className="pill t-neutral">Coming soon</span>
        </div>
      </div>
    </main>
  );
}

function ProjectCard({ p, pending }) {
  const state = pending.length ? STATE.bottleneck : STATE[p.state] || { label: p.state, tone: "neutral" };
  const changed = p.steps.filter((s) => s.status === "pending" || s.status === "changed").length;
  const metrics = Object.entries(p.metric_goals || {}).filter(([k]) => k in (p.metrics || {})).slice(0, 3);
  const statuses = metrics.map(([k, g]) => metricStatus(p.metrics[k], g));
  const top = pending[0];
  const footer = top ? <><b>{plural(pending.length, "decision")}</b> · Lead suggests {recPhrase(top)}</>
    : p.state === "new" ? "Next: the Lead Agent reads the brief"
      : statuses.every((s) => s.tone !== "warn") ? `${p.objective?.deadline || ""} · all on target`.replace(/^ · /, "")
        : `${statuses.filter((s) => s.tone === "warn").length} metric(s) off target`;

  return (
    <Link to={`/projects/${p.id}`} className={`project-card${pending.length ? " active" : ""}`}>
      {pending.length > 0 && <span className="badge-top">Needs you</span>}
      <div className="row">
        <span className={`pill t-${state.tone}`}><i className={`dot t-${state.tone}`} />{state.label}</span>
        <span className="push muted small">{p.tech}</span>
      </div>
      <div className="stack-4">
        <span className="title-md">{p.name}</span>
        <span className="muted small">{p.client} · {p.domain.split(" · ")[0]}</span>
      </div>
      {p.steps.length ? (
        <div className="mini-map">
          <div className="mini-steps">
            {p.steps.map((s, i) => (
              <span key={s.id} className="mini-step-wrap">
                <span className={`mini-step${s.status === "pending" || s.status === "changed" ? " hot" : p.state === "healthy" ? " ok" : ""}`}>{s.short}</span>
                {i < p.steps.length - 1 && <span className="mini-arrow">›</span>}
              </span>
            ))}
          </div>
          <span className="dim small">{changed ? `A change affects ${changed} of ${p.steps.length} steps` : `All ${p.steps.length} steps healthy`}</span>
        </div>
      ) : (
        <div className="mini-map empty"><i className="dashed" />{plural(p.documents, "document")} ready · not built yet</div>
      )}
      <div className="card-stats">
        {metrics.length ? metrics.map(([k, g]) => (
          <span key={k}><b>{fmtMetric(p.metrics[k], g.unit)}</b><small>{g.label}{g.goal != null ? ` · goal ${fmtMetric(g.goal, g.unit)}` : ""}</small></span>
        )) : (
          <>
            <span><b>{p.documents}</b><small>Documents</small></span>
            <span><b>4</b><small>Agents ready</small></span>
          </>
        )}
      </div>
      <div className="card-foot"><span className="small">{footer}</span><span className="push link-text">{p.state === "new" ? "Start" : "Open"}</span></div>
    </Link>
  );
}
