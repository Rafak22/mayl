import { fmtMetric, goalText, metricStatus } from "../format";

// Value vs goal with a status pill and a progress bar (bar = value / goal).
export function MetricCard({ value, goal }) {
  const s = metricStatus(value, goal);
  return (
    <div className="metric">
      <span className="metric-h">
        <span className="muted">{goal.label}</span>
        <span className={`pill t-${s.tone}`}>{s.status}</span>
      </span>
      <span className="metric-v">{fmtMetric(value, goal.unit)} <small>{goalText(goal)}</small></span>
      {s.fill != null && (
        <span className="bar"><span className={`bar-fill t-${s.tone}`} style={{ width: `${Math.max(3, s.fill * 100)}%` }} /></span>
      )}
    </div>
  );
}

export function MetricCards({ metrics, goals }) {
  const keys = Object.keys(goals || {}).filter((k) => k in (metrics || {}));
  if (!keys.length) return null;
  return <div className="metrics">{keys.map((k) => <MetricCard key={k} value={metrics[k]} goal={goals[k]} />)}</div>;
}
