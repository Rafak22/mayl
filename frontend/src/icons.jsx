import { AGENTS, PROJECT_MEMORY } from "./agents";

// Line icons (24x24, stroke only) taken from the approved mockups.
const PATHS = {
  compass: <><circle cx="12" cy="12" r="8" /><path d="M15 9l-2 5-4 1 2-5z" strokeLinejoin="round" /></>,
  chart: <path d="M5 19V10M12 19V5M19 19v-6" strokeLinecap="round" />,
  chip: <><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M10 3v3M14 3v3M10 18v3M14 18v3M3 10h3M3 14h3M18 10h3M18 14h3" strokeLinecap="round" /></>,
  shield: <path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" strokeLinejoin="round" />,
  memory: <path d="M4 6h16M4 12h16M4 18h10" strokeLinecap="round" />,
  send: <path d="M4 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />,
  chat: <path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8l-5 4v-4H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z" strokeLinejoin="round" />,
  plus: <path d="M12 5v14M5 12h14" strokeLinecap="round" />,
  close: <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />,
  doc: <><path d="M7 3h7l4 4v14H7z" strokeLinejoin="round" /><path d="M14 3v4h4" strokeLinejoin="round" /></>,
};

export function Icon({ name, size = 16, color = "currentColor", stroke = 2.2 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke={color} strokeWidth={stroke}>
      {PATHS[name]}
    </svg>
  );
}

// Rounded square in the agent's color with its white icon.
export function AgentAvatar({ agent, size = 30, title }) {
  const a = AGENTS[agent] || PROJECT_MEMORY;
  const glyph = a === PROJECT_MEMORY ? a.iconColor : "#FFFFFF";
  return (
    <span className="avatar" title={title ?? a.name}
      style={{ width: size, height: size, borderRadius: Math.round(size * 0.31), background: a.color }}>
      <Icon name={a.icon} size={Math.round(size * 0.52)} color={glyph} stroke={size < 26 ? 2.8 : 2.2} />
    </span>
  );
}

export function LogoMark({ width = 32 }) {
  return (
    <svg width={width} height={Math.round(width * 0.82)} viewBox="0 0 34 28" aria-hidden="true">
      <path d="M3 4 C 14 4, 14 24, 31 24" fill="none" stroke="#3A52B0" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="3" cy="4" r="3" fill="#3A52B0" /><circle cx="12" cy="8" r="2.6" fill="#3A52B0" />
      <circle cx="18" cy="13" r="2.4" fill="#3A52B0" /><circle cx="24" cy="18" r="2.6" fill="#23885A" />
      <circle cx="31" cy="24" r="3" fill="#23885A" />
    </svg>
  );
}
