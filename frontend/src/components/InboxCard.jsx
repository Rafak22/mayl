import { AGENTS } from "../agents";
import { cap, fmtDays, recPhrase } from "../format";
import { AgentAvatar } from "../icons";

// A pending decision: risk + conflict, original vs alternative effort, the Lead's recommendation.
export function InboxCard({ card, productName, onOpen }) {
  const conflict = card.conflicts?.[0];
  return (
    <div className="inbox-card">
      <span className="pills">
        <span className={`pill risk-${card.risk}`}>{cap(card.risk)} risk</span>
        {conflict && <span className="pill t-bad">Conflict: {conflict.id}</span>}
      </span>
      <span className="inbox-title">{card.title}</span>
      <span className="muted small">From {card.proposer_name}{productName ? ` · ${productName}` : ""}</span>
      {card.alternative && (
        <div className="compare">
          <span className="compare-a"><small>Original</small><b>up to {fmtDays(card.total_effort_max)}</b></span>
          <span className="compare-b"><small>Alternative</small><b>{fmtDays(card.alternative.effort_days)}</b></span>
        </div>
      )}
      {card.recommendation && card.kind !== "handoff" && (
        <span className="inbox-rec"><AgentAvatar agent="lead" size={22} />Lead Agent recommends {recPhrase(card)}.</span>
      )}
      <button className="btn primary block" onClick={onOpen}>Review decision</button>
    </div>
  );
}

export function ReviewedBy({ card }) {
  if (!card.responses?.length) return null;
  return (
    <span className="reviewed-by">Reviewed by
      {card.responses.map((r) => <AgentAvatar key={r.team} agent={r.team} size={22} title={AGENTS[r.team].name} />)}
    </span>
  );
}
