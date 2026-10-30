"""Live team agents: Claude + tools + RAG, orchestrated with LangGraph.

Flow for a change proposal:

    START ──┬──> DS Agent ─────────┐
            ├──> AI Engineer Agent ├──> (aggregate: risk, verdict, approvers)
            └──> Domain Expert Agent┘

Only teams whose part of the Project Graph is affected are dispatched; the
Domain Expert Agent always runs because it guards rules and client promises.
Each agent grounds its answer in tools:
  get_impact_on_my_team   graph traversal: which of MY components change
  search_knowledge        RAG over MY knowledge base + shared project memory
  get_rules_and_promises  domain rules and client promises on record
"""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from . import llm
from .agents import TEAM_AGENTS, _fmt_days, finalize_card
from .graph import affected_nodes, path_explanation
from .products import ROLES
from .rag import AGENT_SCOPES, Retriever, live_chunks

PERSONAS = {
    "ds": "You are the DS Agent. You represent the data science team: data, cleaning, features, models, metrics.",
    "engineer": ("You are the AI Engineer Agent. You represent the AI engineering team: the engine, scoring "
                 "services, APIs, dashboards, hardware and the engine contract (latency, interfaces, approved libraries)."),
    "domain": ("You are the Domain Expert Agent (the expert's twin). You guard domain rules, compliance and the "
               "promises made to the client. You never approve something that breaks a rule or promise without flagging it."),
}

RULES = """Rules:
- Use your tools before answering. Ground every claim in a tool result.
- Effort: start from the baseline in get_impact_on_my_team, then adjust using real change history from
  search_knowledge (look for similar past changes and their ACTUAL effort). Give a min-max range in days.
- If nothing of yours is affected, say so and give 0-0 days.
- conflicts: list rule ids from get_rules_and_promises that this change would break. Only real conflicts.
- If you see a cheaper way to reach the same goal, propose it as `alternative`.
- message: max 3 short sentences, plain language, written for the other teams.
- evidence: the `source` strings of the knowledge you relied on."""

SUBMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "effort_min_days": {"type": "number", "minimum": 0},
        "effort_max_days": {"type": "number", "minimum": 0},
        "verdict": {"type": "string", "enum": ["works", "works_with_changes", "conflict", "blocked"]},
        "message": {"type": "string"},
        "conflicts": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "alternative": {
            "type": "object",
            "properties": {"label": {"type": "string"}, "effort_days": {"type": "number"}},
            "required": ["label", "effort_days"],
        },
    },
    "required": ["effort_min_days", "effort_max_days", "verdict", "message", "conflicts", "evidence"],
}


def _tools_for(team, product, node_id, option, nodes, retriever):
    mine = [n for n in nodes if n["owner"] == team]
    severity = option.get("severity", 1.0)

    def get_impact_on_my_team():
        base = sum(n["effort_days"] for n in mine) * severity
        chain = path_explanation(product, node_id, mine[-1]["id"]) if mine else []
        return {
            "changed_node": {k: nodes[0][k] for k in ("id", "label", "kind", "description")},
            "change": option["label"],
            "my_affected_nodes": [{k: n[k] for k in ("id", "label", "kind", "description", "effort_days")} for n in mine],
            "baseline_effort_days": round(base, 1),
            "how_it_reaches_us": " → ".join(chain),
            "all_affected": [f"{n['label']} ({ROLES[n['owner']]})" for n in nodes],
        }

    def search_knowledge(query: str):
        return retriever.search(query, AGENT_SCOPES[team], k=4)

    def get_rules_and_promises():
        return product.get("rules", [])

    tools = [
        {"name": "get_impact_on_my_team", "description": "Graph traversal: which of my team's components this change affects, with a baseline effort.",
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "search_knowledge", "description": "Search my team's knowledge base and the shared project memory (contracts, change history, guidelines, decisions).",
         "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        {"name": "get_rules_and_promises", "description": "Domain rules and client promises on record, with ids.",
         "input_schema": {"type": "object", "properties": {}}},
    ]
    handlers = {"get_impact_on_my_team": get_impact_on_my_team, "search_knowledge": search_knowledge,
                "get_rules_and_promises": get_rules_and_promises}
    return tools, handlers, mine


def _run_team(team, product, node_id, option, proposer, nodes, retriever) -> dict:
    tools, handlers, mine = _tools_for(team, product, node_id, option, nodes, retriever)
    prompt = (f"{ROLES[proposer]} proposes a change to “{nodes[0]['label']}”: {option['label']}.\n"
              f"Reason given: {option.get('rationale') or 'not given'}.\n"
              f"Project objective: {product.get('objective')}\n"
              "Assess what this means for your team, then submit.")
    out, trace = llm.run_agent(PERSONAS[team] + "\n\n" + RULES, prompt, tools, handlers, SUBMIT_SCHEMA)
    lo = max(0.0, float(out.get("effort_min_days", 0)))
    hi = min(30.0, max(lo, float(out.get("effort_max_days", lo))))
    return {
        "agent": TEAM_AGENTS[team], "team": team, "team_name": ROLES[team],
        "effort_range": (lo, hi), "effort_text": _fmt_days((lo, hi)),
        "nodes": [n["id"] for n in mine], "message": out.get("message", ""),
        "verdict": out.get("verdict"), "conflict_ids": out.get("conflicts", []),
        "evidence": out.get("evidence", [])[:4], "alternative": out.get("alternative"),
        "tools_used": [t["tool"] for t in trace],
    }


class _State(TypedDict, total=False):
    team: str
    responses: Annotated[list, operator.add]


def assess_change_live(product, node_id, option, proposer, activity) -> dict:
    nodes = affected_nodes(product, node_id)
    retriever = Retriever(product["id"], live_chunks(product, activity))
    teams = sorted({n["owner"] for n in nodes if n["owner"] != "lead"} | {"domain"})

    def team_node(state: _State):
        return {"responses": [_run_team(state["team"], product, node_id, option, proposer, nodes, retriever)]}

    g = StateGraph(_State)
    g.add_node("team_agent", team_node)
    g.add_conditional_edges(START, lambda _: [Send("team_agent", {"team": t}) for t in teams])
    g.add_edge("team_agent", END)
    result = g.compile().invoke({"responses": []})
    responses = sorted(result["responses"], key=lambda r: ["ds", "engineer", "domain"].index(r["team"]))

    rules = {r["id"]: r for r in product.get("rules", [])}
    conflict_ids = {c for r in responses for c in r["conflict_ids"]} | set(option.get("conflicts", []))
    conflicts = [rules[c] for c in conflict_ids if c in rules]
    blocked = any(r["verdict"] == "blocked" for r in responses)

    alternative = option.get("alternative")
    proposed = [r["alternative"] for r in responses if r.get("alternative")]
    if proposed:
        best = min(proposed, key=lambda a: a.get("effort_days", 99))
        if not alternative or best.get("effort_days", 99) < alternative.get("effort_days", 99):
            alternative = {"label": best["label"], "effort_days": best["effort_days"], "metric_delta": {}}
    for r in responses:
        r.pop("alternative", None)
    return finalize_card(product, nodes, option, proposer, responses, conflicts, alternative, "live", blocked)


# ---------------------------------------------------------------------------
# Objective intake: the Lead Agent reads the client's documents.
# ---------------------------------------------------------------------------
FIELD = {"type": "object", "properties": {
    "value": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
    "source": {"type": "string", "description": "Document name the value came from"},
    "inferred": {"type": "boolean", "description": "True if not stated directly"}},
    "required": ["value", "source"]}

INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "spec": {"type": "object", "properties": {k: FIELD for k in (
            "goal", "success_metric", "priorities", "constraints", "deadline", "stakeholders")},
            "required": ["goal", "success_metric", "priorities", "constraints", "deadline", "stakeholders"]},
        "gaps": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "question": {"type": "string"}, "suggested": {"type": "string"}},
            "required": ["id", "question", "suggested"]}},
    },
    "required": ["spec", "gaps"],
}


def intake_live(product) -> dict:
    retriever = Retriever(product["id"])
    docs = "\n\n".join(f"### {d['name']}\n{d['text']}" for d in product["documents"])
    system = ("You are the Lead Agent. Turn client documents into an Objective Spec the whole team builds from. "
              "priorities must be an ordered list (most important first). The success metric must be measurable; "
              "if the documents don't state one, infer it and set inferred=true. List only REAL gaps (max 3): things "
              "missing or contradictory that would change what gets built. For each gap suggest an answer, using "
              "search_knowledge (e.g. domain guidelines) when it helps.")
    tools = [{"name": "search_knowledge", "description": "Search the project's knowledge bases (domain guidelines, engineering contracts).",
              "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}]
    out, _ = llm.run_agent(system, f"Client documents:\n\n{docs}", tools,
                           {"search_knowledge": lambda query: retriever.search(query, None, 3)}, INTAKE_SCHEMA, max_steps=4)
    return out


# ---------------------------------------------------------------------------
# Project chat and Expert Twin (RAG answers with citations)
# ---------------------------------------------------------------------------
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited": {"type": "array", "items": {"type": "integer"}, "description": "Numbers of the passages used"},
        "confident": {"type": "boolean", "description": "False if the passages don't really answer the question"},
    },
    "required": ["answer", "cited", "confident"],
}


def answer_live(question: str, hits: list[dict], as_expert: bool) -> dict:
    passages = "\n".join(f"[{i + 1}] ({h['source']}) {h['text']}" for i, h in enumerate(hits))
    who = ("You are the Domain Expert Agent, answering on behalf of the domain expert from their guidelines and past "
           "decisions. If the passages don't clearly answer it, set confident=false so it goes to the real expert."
           if as_expert else "You are the project assistant. Answer from the project's history and knowledge.")
    system = who + " Answer ONLY from the numbered passages, in 1-3 sentences, in the language of the question."
    out, _ = llm.run_agent(system, f"Passages:\n{passages}\n\nQuestion: {question}", [], {}, ANSWER_SCHEMA,
                           max_steps=1, max_tokens=600)
    return out
