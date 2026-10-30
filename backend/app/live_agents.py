"""Live team agents: Claude + tools + RAG, orchestrated with LangGraph.

Flow for a change proposal:

    START ──┬──> DS Agent ──────────┐
            ├──> AI Engineer Agent ─┼──> Lead Agent ──> END
            └──> Domain Expert Agent┘

Only teams whose part of the Project Graph is affected are dispatched; the
Domain Expert Agent always runs because it guards rules and client promises.
Each team agent grounds its answer in tools:
  get_impact_on_my_team   graph traversal: which of MY components change
  search_knowledge        RAG over MY knowledge base + shared project memory
  get_rules_and_promises  domain rules and client promises on record
The Lead step first computes risk, verdict and approvers in code, then the
Lead Agent recommends approve / alternative / reject. Humans decide.
"""
import logging
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from . import llm, prompts
from .agents import TEAM_AGENTS, _fmt_days, finalize_card
from .graph import affected_nodes, path_explanation
from .products import ROLES
from .rag import AGENT_SCOPES, Retriever, live_chunks

log = logging.getLogger("mayl.agents")

SUBMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "effort_min_days": {"type": "number", "minimum": 0},
        "effort_max_days": {"type": "number", "minimum": 0},
        "verdict": {"type": "string", "enum": ["works", "works_with_changes", "conflict", "blocked"]},
        "message": {"type": "string", "description": "Max 3 short sentences for the other teams, impact first."},
        "conflicts": {"type": "array", "items": {"type": "string"},
                      "description": "Ids from get_rules_and_promises that this change clearly breaks."},
        "evidence": {"type": "array", "items": {"type": "string"},
                     "description": "The `source` strings of the knowledge results you relied on."},
        "alternative": {
            "type": "object",
            "description": "Only if your knowledge supports a cheaper or safer way to the same goal.",
            "properties": {"label": {"type": "string"}, "effort_days": {"type": "number"}},
            "required": ["label", "effort_days"],
        },
    },
    "required": ["effort_min_days", "effort_max_days", "verdict", "message", "conflicts", "evidence"],
}


def objective_spec(product) -> str:
    """The Objective Spec as every agent sees it, priorities numbered in order."""
    o = product.get("objective")
    if not o:
        return "Objective Spec: not defined yet."
    join = lambda v: ", ".join(v) if isinstance(v, list) else str(v or "not set")  # noqa: E731
    priorities = "\n".join(f"  {i}. {p}" for i, p in enumerate(o.get("priorities") or [], 1)) or "  not set"
    return (f"Objective Spec\nGoal: {o.get('goal')}\nSuccess metric: {o.get('success_metric')}\n"
            f"Priorities (most important first):\n{priorities}\n"
            f"Constraints: {join(o.get('constraints'))}\nDeadline: {o.get('deadline')}")


def _change_text(product, nodes, option, proposer) -> str:
    return (f"{ROLES[proposer]} proposes a change to “{nodes[0]['label']}”: {option['label']}.\n"
            f"Reason given: {option.get('rationale') or 'not given'}.\n\n{objective_spec(product)}")


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
    prompt = _change_text(product, nodes, option, proposer) + "\n\nAssess what this means for your team, then submit."
    out, trace = llm.run_agent(prompts.TEAM_AGENT_PROMPTS[team], prompt, tools, handlers, SUBMIT_SCHEMA)
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


def _combine(product, nodes, option, proposer, responses) -> dict:
    """Merge the team answers into one card. Risk, verdict and approvers are computed here, in code."""
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


def _lead_recommendation(product, nodes, option, proposer, card) -> tuple[str, str]:
    options = ["approve", "alternative", "reject"] if card["alternative"] else ["approve", "reject"]
    schema = {"type": "object", "properties": {
        "recommendation": {"type": "string", "enum": options},
        "reason": {"type": "string", "description": "2 sentences that name the deciding priority."}},
        "required": ["recommendation", "reason"]}
    alt = card["alternative"]
    assessments = "\n".join(
        f"- {r['agent']}: {r['effort_text']}, verdict {r.get('verdict')}"
        + (f", conflicts {', '.join(r['conflict_ids'])}" if r.get("conflict_ids") else "")
        + f". “{r['message']}”" for r in card["responses"])
    prompt = (
        _change_text(product, nodes, option, proposer)
        + f"\n\nComputed by the platform: risk {card['risk']}, verdict {card['verdict']}, "
          f"total effort up to {card['total_effort_max']:g} days.\n"
        + "Conflicts: " + ("; ".join(f"{c['id']}: {c['text']} ({c['source']})" for c in card["conflicts"]) or "none") + "\n"
        + "Cheaper alternative: " + (f"{alt['label']} ({alt['effort_days']:g} days)" if alt else "none") + "\n\n"
        + f"Team assessments:\n{assessments}\n\nSubmit your recommendation.")
    out, _ = llm.run_agent(prompts.LEAD_AGENT, prompt, [], {}, schema, max_tokens=4000)
    if out.get("recommendation") not in options or not str(out.get("reason", "")).strip():
        raise ValueError(f"Unusable Lead Agent answer: {out}")
    return out["recommendation"], out["reason"].strip()


class _State(TypedDict, total=False):
    team: str
    responses: Annotated[list, operator.add]
    card: dict


def assess_change_live(product, node_id, option, proposer, activity) -> dict:
    nodes = affected_nodes(product, node_id)
    retriever = Retriever(product["id"], live_chunks(product, activity))
    teams = sorted({n["owner"] for n in nodes if n["owner"] != "lead"} | {"domain"})

    def team_node(state: _State):
        return {"responses": [_run_team(state["team"], product, node_id, option, proposer, nodes, retriever)]}

    def lead_node(state: _State):
        responses = sorted(state["responses"], key=lambda r: ["ds", "engineer", "domain"].index(r["team"]))
        card = _combine(product, nodes, option, proposer, responses)
        if card["status"] == "pending":  # auto-approved changes need no recommendation call
            try:
                card["recommendation"], card["recommendation_reason"] = _lead_recommendation(
                    product, nodes, option, proposer, card)
                card["recommendation_mode"] = "live"
            except Exception:  # keep the team agents' work; the rule-based recommendation stands
                log.exception("Lead Agent failed; keeping the rule-based recommendation")
        return {"card": card}

    g = StateGraph(_State)
    g.add_node("team_agent", team_node)
    g.add_node("lead", lead_node)
    g.add_conditional_edges(START, lambda _: [Send("team_agent", {"team": t}) for t in teams])
    g.add_edge("team_agent", "lead")
    g.add_edge("lead", END)
    return g.compile().invoke({"responses": []})["card"]


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
    tools = [{"name": "search_knowledge", "description": "Search the project's knowledge bases (domain guidelines, engineering contracts).",
              "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}]
    out, _ = llm.run_agent(prompts.INTAKE_AGENT, f"Client documents:\n\n{docs}", tools,
                           {"search_knowledge": lambda query: retriever.search(query, None, 3)}, INTAKE_SCHEMA, max_steps=4)
    out["gaps"] = out.get("gaps", [])[:3]  # maxItems isn't enforceable in a strict schema
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
    system = prompts.EXPERT_TWIN if as_expert else prompts.PROJECT_ASSISTANT
    out, _ = llm.run_agent(system, f"Passages:\n{passages}\n\nQuestion: {question}", [], {}, ANSWER_SCHEMA,
                           max_tokens=4000)
    return out
