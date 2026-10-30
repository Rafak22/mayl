import { AGENTS } from "../agents";
import { api, assetUrl } from "../api";
import { plural, textDir } from "../format";
import { AgentAvatar } from "../icons";
import { useLoad } from "../state";

const TONE_DOT = { good: "t-good", warn: "t-warn", bad: "t-bad" };
const OWNER_RING = { ds: "#3CC27A", engineer: "#6E8BF0", domain: "#E2709E", lead: "#8B7CF0" };

export function DataTab({ pid }) {
  const { data: d, failed } = useLoad(() => api.details(pid), [pid]);
  if (failed) return <p className="error">The project details couldn't be loaded.</p>;
  if (!d) return <p className="muted">Loading…</p>;
  return (
    <>
      {d.examples && (
        <section className="stack-12">
          <div className="row wrap baseline"><h2 className="h-md">{d.examples.title}</h2><span className="muted small">{d.examples.note}</span></div>
          <div className="examples">
            {d.examples.items.map((x) => (
              <figure key={x.image} className={`example${x.tone === "warn" ? " warn" : ""}`}>
                <img src={assetUrl(x.image)} alt={x.alt} loading="lazy" />
                <figcaption>
                  <span className={`example-title c-${x.tone}`}><i className={`dot ${TONE_DOT[x.tone]}`} />{x.title}</span>
                  <span className="small body">{x.caption}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      <div className="two-up">
        {d.data && (
          <section className="card stack-14">
            <div className="card-h"><AgentAvatar agent="ds" size={30} /><h2 className="h-md">The data</h2></div>
            <div className="stat-boxes">{d.data.stats.map((s) => <span key={s.label}><b>{s.value}</b><small>{s.label}</small></span>)}</div>
            <div className="stack-8">
              <span className="small strong">{d.data.bars.title}</span>
              {d.data.bars.items.map((b) => {
                const max = Math.max(...d.data.bars.items.map((x) => x.value));
                return (
                  <div key={b.label} className="hbar">
                    <span className="hbar-label">{b.label}</span>
                    <span className="bar"><span className="bar-fill t-good" style={{ width: `${(b.value / max) * 100}%` }} /></span>
                    <span className="hbar-value">{b.display}</span>
                  </div>
                );
              })}
            </div>
            <div className="note"><i className="dot t-warn" /><span {...textDir(d.data.note)}>{d.data.note}</span></div>
            <span className="muted small">{d.data.footer} · Source: {d.data.source}</span>
          </section>
        )}

        <section className="card stack-14">
          <div className="card-h"><AgentAvatar agent="engineer" size={30} /><h2 className="h-md">The implemented solution</h2></div>
          {d.solution ? (
            <>
              <div className="pipeline">
                {d.solution.pipeline.map((s, i) => (
                  <span key={s.label} className="pipeline-wrap">
                    <span className="pipeline-step" style={{ boxShadow: `inset 0 0 0 1px ${OWNER_RING[s.owner] || "#2A3553"}` }}>{s.label}</span>
                    {i < d.solution.pipeline.length - 1 && <span className="mini-arrow">›</span>}
                  </span>
                ))}
              </div>
              <span className="small strong">{d.solution.table.title}</span>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr>{d.solution.table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {d.solution.table.rows.map((r) => (
                      <tr key={r.cells[0]} className={r.chosen ? "chosen" : ""}>
                        {r.cells.map((c, i) => <td key={i}>{c}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="card-stats">{d.solution.stats.map((s) => <span key={s.label}><b>{s.value}</b><small>{s.label}</small></span>)}</div>
              <span className="muted small">Source: {d.solution.source}</span>
            </>
          ) : <p className="muted">{d.solution_pending}</p>}
        </section>
      </div>

      {d.samples && (
        <section className="card stack-12">
          <div className="row wrap baseline"><h2 className="h-md">{d.samples.title}</h2><span className="muted small">{d.samples.note}</span></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr>{d.samples.columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
              <tbody>
                {d.samples.rows.map((row, i) => (
                  <tr key={i}>{d.samples.columns.map((c) => <td key={c.key} {...textDir(row[c.key])}>{(row[c.key] || "").replace(/_/g, " ")}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card stack-12">
        <div className="row wrap baseline">
          <h2 className="h-md">What the agents know about this project</h2>
          <span className="muted small">{plural(d.documents.length, "document")} in the knowledge base, searched with keyword + meaning search</span>
        </div>
        <div className="doc-grid">
          {d.documents.map((doc) => (
            <span key={doc.file} className="doc-row" style={{ borderLeftColor: doc.agent ? AGENTS[doc.agent].color : AGENTS.lead.color }}>
              <b>{doc.title}</b><span className="push muted small">{doc.agent ? AGENTS[doc.agent].name : "Shared"}</span>
            </span>
          ))}
        </div>
      </section>
    </>
  );
}

export function KnowledgeTab({ pid }) {
  const { data: d, failed } = useLoad(() => api.details(pid), [pid]);
  if (failed) return <p className="error">The knowledge base couldn't be loaded.</p>;
  if (!d) return <p className="muted">Loading…</p>;
  const groups = [["domain", "Domain Agent"], ["ds", "DS Agent"], ["engineer", "Engineer Agent"], [null, "Shared by all agents"]];
  return (
    <div className="stack-16">
      <p className="muted">Each agent searches its own documents plus the shared ones. Open a document to read what the agents read.</p>
      {groups.map(([agent, label]) => {
        const docs = d.documents.filter((x) => x.agent === agent);
        if (!docs.length) return null;
        return (
          <section key={label} className="stack-10">
            <div className="row">{agent && <AgentAvatar agent={agent} size={26} />}<h2 className="h-sm">{label}</h2></div>
            {docs.map((doc) => (
              <details key={doc.file} className="doc-detail" style={{ borderLeftColor: agent ? AGENTS[agent].color : AGENTS.lead.color }}>
                <summary><b>{doc.title}</b><span className="muted small">{plural(doc.sections.length, "section")} · {doc.file}</span></summary>
                {doc.sections.map((s) => (
                  <div key={s.heading} className="doc-section"><b>{s.heading}</b><p {...textDir(s.text)}>{s.text}</p></div>
                ))}
              </details>
            ))}
          </section>
        );
      })}
    </div>
  );
}
