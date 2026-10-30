import { useState } from "react";
import { api } from "../api";
import { AgentAvatar, Icon } from "../icons";
import { Thinking } from "./ImpactCard";

// New project: the Lead Agent reads the client's documents and fills the Objective Spec.
export function Intake({ product, role, onDone }) {
  const [res, setRes] = useState(null);
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const read = async () => {
    setBusy(true); setError("");
    try {
      const r = await api.intake(product.id);
      setRes(r);
      setAnswers(Object.fromEntries(r.gaps.map((g) => [g.id, g.suggested])));
    } catch (e) { setError(e.message || "The Lead Agent couldn't read the documents. Try again."); }
    finally { setBusy(false); }
  };
  const confirm = async () => {
    setBusy(true); setError("");
    try { await api.confirm(product.id, answers); onDone(); }
    catch (e) { setError(e.message || "The agents couldn't build the project. Try again."); }
    finally { setBusy(false); }
  };
  return (
    <section className="card intake">
      <div className="card-h"><AgentAvatar agent="lead" size={30} /><h2>Objective intake</h2></div>
      <div className="docs">
        {product.documents.map((d) => <span key={d.name} className="doc-chip"><Icon name="doc" size={14} />{d.name}</span>)}
      </div>
      {error && <p className="error">{error}</p>}
      {!res && (busy ? <Thinking text="The Lead Agent is reading the documents…" />
        : <button className="btn primary" onClick={read}>Let the Lead Agent read the documents</button>)}
      {res && (
        <>
          <span className={`pill ${res.mode === "live" ? "t-good" : "t-neutral"}`}>{res.mode === "live" ? "Extracted by the live Lead Agent" : "Demo extraction"}</span>
          <div className="table-wrap">
            <table className="table">
              <tbody>
                {Object.entries(res.spec).map(([k, v]) => (
                  <tr key={k}>
                    <th>{k.replace(/_/g, " ")}</th>
                    <td>{Array.isArray(v.value) ? v.value.join(" · ") : v.value}{v.inferred && <em className="muted"> (inferred)</em>}</td>
                    <td className="muted small">{v.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h4>Only these need a human</h4>
          {res.gaps.map((g) => (
            <label key={g.id} className="field">
              {g.question}
              <input value={answers[g.id] || ""} onChange={(e) => setAnswers({ ...answers, [g.id]: e.target.value })} />
            </label>
          ))}
          {role === "lead"
            ? <button className="btn primary" disabled={busy} onClick={confirm}>{busy ? "Agents building…" : "Confirm and let the agents build"}</button>
            : <p className="muted">Switch to AI Lead to confirm.</p>}
        </>
      )}
    </section>
  );
}
