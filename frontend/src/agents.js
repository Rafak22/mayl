// One identity per agent, used everywhere: map, activity, chat, inbox, agents page.
// color: the agent's own color · soft/ink: tinted background and text on light cards ·
// mapColor: brighter variant for the dark project map.
export const AGENTS = {
  lead: {
    key: "lead", name: "Lead Agent", icon: "compass", role: "lead",
    color: "#6B5BD2", soft: "#F1EFFC", ink: "#4A3DA8", mapColor: "#8B7CF0",
    tagline: "The decider",
    subtitle: "Works for the AI Lead",
    quote: "I weigh every team's answer against the client's priorities, then recommend one option. You make the call.",
    owns: "Objectives, priorities, deadlines, client promises",
    skills: ["Objective intake", "Recommend", "Search all knowledge"],
    chatHint: "Priorities and decisions",
  },
  ds: {
    key: "ds", name: "DS Agent", icon: "chart", role: "ds",
    color: "#23885A", soft: "#EAF6EF", ink: "#1B6E48", mapColor: "#3CC27A",
    tagline: "Data first",
    subtitle: "Speaks for data science",
    quote: "Data first. I won't claim a metric will move unless an experiment shows it.",
    owns: "Data, annotations, features, models, evaluation",
    skills: ["Graph impact", "Experiment logs", "Data cards"],
    chatHint: "Data, models, experiments",
  },
  engineer: {
    key: "engineer", name: "Engineer Agent", icon: "chip", role: "engineer",
    color: "#3A52B0", soft: "#ECF0FC", ink: "#2E44A0", mapColor: "#6E8BF0",
    tagline: "Guards the engine",
    subtitle: "Speaks for AI engineering",
    quote: "I guard the engine. Every estimate is anchored to how long a similar change really took.",
    owns: "Engine, APIs, apps, hardware, the engine contract",
    skills: ["Contract check", "Change history", "Graph impact"],
    chatHint: "Engine, contracts, effort",
  },
  domain: {
    key: "domain", name: "Domain Agent", icon: "shield", role: "domain",
    color: "#C2457A", soft: "#FCEEF4", ink: "#A33666", mapColor: "#E2709E",
    tagline: "The expert's twin",
    subtitle: "The expert's twin",
    quote: "I answer from the expert's rulebook and past decisions. Anything new, I send to the real expert.",
    owns: "Domain rules, safety, compliance, promises to the client",
    skills: ["Rule check", "Guidelines", "Arabic + English"],
    chatHint: "Speaks for the domain expert",
  },
};

export const AGENT_ORDER = ["lead", "ds", "engineer", "domain"];

// Not an agent: answers from the whole project history (all knowledge scopes).
export const PROJECT_MEMORY = {
  key: "project", name: "Project memory", icon: "memory",
  color: "#E6EAF3", iconColor: "#5D6788", soft: "#F1F3F8", ink: "#33405F",
  chatHint: "Why did we…? Any question",
};

export const CHAT_TARGETS = [...AGENT_ORDER.map((k) => AGENTS[k]), PROJECT_MEMORY];

// The human roles you can view the app as; each has the agent that speaks for it.
export const ROLES = [
  { id: "lead", name: "AI Lead" },
  { id: "ds", name: "Data Scientist" },
  { id: "engineer", name: "AI Engineer" },
  { id: "domain", name: "Domain Expert" },
];
export const ROLE_NAME = Object.fromEntries(ROLES.map((r) => [r.id, r.name]));

export const chatTarget = (key) => AGENTS[key] || PROJECT_MEMORY;
