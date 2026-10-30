import { Link, useNavigate } from "react-router";
import { AGENTS, AGENT_ORDER, ROLE_NAME } from "../agents";
import { ActivityFeed } from "../components/Activity";
import { ReviewedBy } from "../components/InboxCard";
import { STATE, cap, fmtMetric, fmtSeconds, plural, recPhrase } from "../format";
import { AgentAvatar } from "../icons";
import { useMayl } from "../state";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function agentSummary(key, a) {
  if (!a) return "";
  if (key === "lead") return plural(a.recommendations, "recommendation");
  if (key === "domain" && (a.answers || a.escalations))
    return `${plural(a.answers, "answer")} · ${a.escalations} escalated`;
  return plural(a.reviews, "review");
}

// One line under a project name: its tech plus its first metric against the goal.
function projectLine(p) {
  const first = Object.entries(p.metric_goals || {}).find(([k]) => k in (p.metrics || {}));
  const metric = first ? ` · ${first[1].label.toLowerCase()} ${fmtMetric(p.metrics[first[0]], first[1].unit)}` : "";
  if (p.state === "new") return `${p.tech} · ${plural(p.documents, "client document")} ready`;
  return `${p.tech}${metric}`;
}

export default function Overview() {
  const { products, inbox, stats, role } = useMayl();
  const navigate = useNavigate();
  const top = inbox[0];
  const topProduct = top && products.find((p) => p.id === top.product_id);
  const reviewedToday = stats?.changes_reviewed_today ?? 0;

  return (
    <main className="page">
      <div className="page-h">
        <h1>{greeting()}</h1>
        <span className="muted">
          Your agents reviewed {plural(reviewedToday, "change")} today. {inbox.length ? `${plural(inbox.length, "decision")} ${inbox.length === 1 ? "needs" : "need"} you.` : "Nothing needs you right now."}
        </span>
      </div>

      <div className="tiles">
        <Tile value={inbox.length} label={`Decision${inbox.length === 1 ? "" : "s"} waiting for you`} tone="blue" />
        <Tile value={reviewedToday} label="Changes reviewed by agents today" />
        <Tile value={fmtSeconds(stats?.avg_review_seconds)} label="Average review time" />
        <Tile value={stats?.conflicts_caught ?? 0} label="Conflicts caught before work started" tone="red" />
      </div>

      <div className="split">
        <div className="split-main">
          {top ? (
            <section className="card attention">
              <div className="row">
                <span className="eyebrow warn">Needs your attention</span>
                <span className={`pill risk-${top.risk} push`}>{cap(top.risk)} risk</span>
              </div>
              <div className="stack-4">
                <span className="title-lg">{top.title}</span>
                <span className="muted small">{topProduct?.name} · proposed by the {top.proposer_name}</span>
              </div>
              {top.recommendation && (
                <div className="lead-note">
                  <AgentAvatar agent="lead" size={28} />
                  <span><b>Lead Agent recommends {recPhrase(top)}.</b> {top.recommendation_reason}</span>
                </div>
              )}
              <div className="row wrap">
                <button className="btn primary" onClick={() => navigate(`/projects/${top.product_id}?card=${top.id}`)}>Review decision</button>
                <ReviewedBy card={top} />
              </div>
            </section>
          ) : (
            <section className="card calm">
              <span className="eyebrow">All clear</span>
              <span className="title-md">Nothing needs the {ROLE_NAME[role]} right now. The agents have it.</span>
            </section>
          )}

          <section className="stack-10">
            <div className="row"><h2 className="h-sm">Projects</h2><Link className="push link" to="/projects">See all</Link></div>
            {products.map((p) => {
              const pending = inbox.filter((c) => c.product_id === p.id).length;
              const state = STATE[p.state] || { label: p.state, tone: "neutral" };
              return (
                <Link key={p.id} to={`/projects/${p.id}`} className={`project-row${pending ? " active" : ""}`}>
                  <span className={`dot t-${state.tone}`} />
                  <span className="project-row-text"><b>{p.name}</b><span className="small">{projectLine(p)}</span></span>
                  <span className={`pill ${pending ? "t-warn" : `t-${state.tone}`}`}>{pending ? plural(pending, "decision") : state.label}</span>
                </Link>
              );
            })}
          </section>
        </div>

        <aside className="split-side">
          <section className="dark-card">
            <span className="h-sm">Agents today</span>
            {AGENT_ORDER.map((k) => (
              <div key={k} className="dark-row">
                <AgentAvatar agent={k} size={30} /><span className="grow">{AGENTS[k].name}</span>
                <span className="dim">{agentSummary(k, stats?.agents?.[k])}</span>
              </div>
            ))}
          </section>
          <section className="stack-12">
            <h2 className="h-sm">Latest across projects</h2>
            <ActivityFeed items={stats?.latest?.slice(0, 5)} showProduct />
          </section>
        </aside>
      </div>
    </main>
  );
}

function Tile({ value, label, tone }) {
  return <span className="tile"><span className={`tile-v${tone ? ` c-${tone}` : ""}`}>{value}</span><span className="muted small">{label}</span></span>;
}
