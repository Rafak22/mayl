import { AGENTS, ROLE_NAME } from "../agents";
import { textDir, timeAgo } from "../format";
import { AgentAvatar } from "../icons";

const HUMANS = new Set(Object.values(ROLE_NAME));

// One activity line: 4px bar in the agent's color (grey for people), icon, who, when, full sentence.
export function ActivityItem({ item, showProduct = false }) {
  const agent = AGENTS[item.agent];
  return (
    <div className="act" style={{ borderLeftColor: agent ? agent.color : "#C9D1E6" }}>
      <span className="act-h">
        {agent && <AgentAvatar agent={item.agent} size={20} />}
        <b>{item.actor}</b>{!agent && HUMANS.has(item.actor) && <span className="muted"> (human)</span>}
        <span className="act-time">{timeAgo(item.at)}</span>
      </span>
      <span {...textDir(item.text)}>{item.text}</span>
      {showProduct && item.product_name && <span className="act-product">{item.product_name}</span>}
    </div>
  );
}

export function ActivityFeed({ items, showProduct, empty = "Nothing yet." }) {
  if (!items?.length) return <p className="muted">{empty}</p>;
  return <div className="feed">{items.map((a) => <ActivityItem key={a.seq ?? a.at + a.text} item={a} showProduct={showProduct} />)}</div>;
}
