// Small display helpers shared by the pages.

const ARABIC = /[؀-ۿ]/;
export const isArabic = (text) => ARABIC.test(text || "");
export const textDir = (text) => (isArabic(text) ? { dir: "rtl", lang: "ar" } : {});

export function timeAgo(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export const plural = (n, word, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;
export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

// Metric values: "%" means a 0-1 ratio.
export function fmtMetric(value, unit) {
  if (value == null) return "–";
  if (unit === "%") return `${+(value * 100).toFixed(value * 100 % 1 ? 1 : 0)}%`;
  if (unit === "s") return `${value} s`;
  return `${value}`;
}

// Value vs goal: status, bar fill (0-1) and whether it's on target.
// Percentages fill to the value itself (88% recall = 88% bar); counts and times fill to value / limit.
export function metricStatus(value, goal) {
  if (!goal || goal.goal == null) return { status: "Tracked", tone: "neutral", fill: null };
  const fill = Math.max(0, Math.min(1, goal.unit === "%" ? value : value / goal.goal));
  const ok = goal.better === "higher" ? value >= goal.goal : value <= goal.goal;
  return { status: ok ? "On target" : goal.better === "higher" ? "Below goal" : "Over limit", tone: ok ? "good" : "warn", fill };
}

export const goalText = (goal) =>
  goal.goal == null ? "no goal set" : `${goal.better === "higher" ? "of" : "limit"} ${fmtMetric(goal.goal, goal.unit)}${goal.better === "higher" ? " goal" : ""}`;

export function fmtSeconds(s) {
  if (s == null) return "–";
  if (s < 1) return "< 1 s";
  return s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`;
}

export const fmtDays = (d) => `${d} day${d === 1 ? "" : "s"}`;

const RISK_ORDER = { high: 0, medium: 1, low: 2 };
export const byUrgency = (a, b) => (RISK_ORDER[a.risk] - RISK_ORDER[b.risk]) || b.created_at.localeCompare(a.created_at);

export const STATE = {
  healthy: { label: "Healthy", tone: "good" },
  resolved: { label: "Resolved", tone: "good" },
  bottleneck: { label: "Needs a decision", tone: "warn" },
  new: { label: "New", tone: "new" },
  handoff: { label: "Handoff ready", tone: "new" },
  building: { label: "Engine in progress", tone: "new" },
};

export const REC_LABEL = { approve: "Approve", alternative: "Use the cheaper alternative", reject: "Reject",
  needs_info: "Ask the proposer for more detail" };

export function recPhrase(card) {
  if (card.recommendation === "alternative" && card.alternative)
    return `the cheaper alternative (${fmtDays(card.alternative.effort_days)})`;
  if (card.recommendation === "needs_info") return "asking for more detail first";
  return card.recommendation === "reject" ? "rejecting this change" : "approving this change";
}

export const firstSentence = (text) => (text || "").split(/(?<=[.!?])\s/)[0];
