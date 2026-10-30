"""Team agents.

Each agent speaks for one team and answers the same question about a change
proposal: "what does this mean for MY team?"

Demo mode (default) is deterministic: estimates come from the Project Graph
(which components a change touches and their effort profile), conflicts come
from the product's recorded rules and client promises. Live mode can later
swap the message wording for LLM-written text without changing the numbers.
"""
import math
import uuid
from datetime import datetime, timezone

from .graph import affected_nodes, path_explanation
from .products import ROLES

TEAM_AGENTS = {
    "ds": "DS Agent",
    "engineer": "Engineer Agent",
    "domain": "Domain Agent",
    "lead": "Lead Agent",
}
AGENT_BY_NAME = {name: key for key, name in TEAM_AGENTS.items()}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _range(days: float) -> tuple[float, float]:
    if days <= 0:
        return (0, 0)
    lo = max(0.5, round(days * 0.8 * 2) / 2)
    hi = max(lo, math.ceil(days * 1.25 * 2) / 2)
    return (lo, hi)


def _fmt_days(r: tuple[float, float]) -> str:
    lo, hi = r
    if hi == 0:
        return "no work"
    if lo == hi:
        return f"{lo:g} day" + ("" if lo == 1 else "s")
    return f"{lo:g}–{hi:g} days"


def assess_change(product: dict, node_id: str, option: dict, proposer: str) -> dict:
    """Run every team agent on a change and return one impact card."""
    nodes = affected_nodes(product, node_id)
    origin = nodes[0]
    severity = option.get("severity", 1.0)
    rules = {r["id"]: r for r in product.get("rules", [])}
    conflicts = [rules[c] for c in option.get("conflicts", []) if c in rules]

    # --- per-team effort from the graph --------------------------------
    teams: dict[str, dict] = {}
    for n in nodes:
        t = teams.setdefault(n["owner"], {"nodes": [], "days": 0.0})
        t["nodes"].append(n)
        t["days"] += n["effort_days"] * severity

    responses = []
    for team, info in teams.items():
        if team == "lead":
            continue
        r = _range(info["days"])
        labels = [n["label"] for n in info["nodes"]]
        if team == proposer:
            msg = f"Applying this touches {len(labels)} of our components ({', '.join(labels)}). Estimated {_fmt_days(r)}."
        elif team == "engineer":
            chain = path_explanation(product, node_id, info["nodes"][-1]["id"])
            via = f" The change reaches us through {' → '.join(chain)}." if len(chain) > 2 else ""
            msg = (f"This affects {len(labels)} engine component(s): {', '.join(labels)}.{via} "
                   f"Estimated engine work: {_fmt_days(r)}.")
        elif team == "ds":
            msg = (f"Pipeline steps that must be updated and re-tested: {', '.join(labels)}. "
                   f"Estimated: {_fmt_days(r)}.")
        else:
            msg = f"Affects: {', '.join(labels)}. Estimated: {_fmt_days(r)}."
        responses.append({
            "agent": TEAM_AGENTS[team], "team": team, "team_name": ROLES[team],
            "effort_range": r, "effort_text": _fmt_days(r),
            "nodes": [n["id"] for n in info["nodes"]], "message": msg,
        })

    # --- domain agent always checks rules and promises -----------------
    if conflicts:
        dmsg = "Conflict found: " + "; ".join(f"“{c['text']}” ({c['source']})" for c in conflicts) + "."
    else:
        dmsg = "No conflicts with recorded domain rules or client promises."
    domain_resp = next((r for r in responses if r["team"] == "domain"), None)
    if domain_resp:
        domain_resp["message"] += " " + dmsg
    else:
        responses.append({"agent": TEAM_AGENTS["domain"], "team": "domain", "team_name": ROLES["domain"],
                          "effort_range": (0, 0), "effort_text": "no work", "nodes": [], "message": dmsg})

    return finalize_card(product, nodes, option, proposer, responses, conflicts, option.get("alternative"), "demo")


def finalize_card(product, nodes, option, proposer, responses, conflicts, alternative, mode, blocked=False):
    """Shared by demo and live agents: risk level, verdict, and who must approve."""
    severity = option.get("severity", 1.0)
    other_teams = {r["team"] for r in responses if r["team"] != proposer and r["effort_range"][1] > 0}
    touches_objective = any(n["kind"] == "objective" for n in nodes)
    total = sum(r["effort_range"][1] for r in responses)
    if conflicts or blocked or touches_objective or severity >= 1.6 or total > 10:
        risk = "high"
    elif other_teams:
        risk = "medium"
    else:
        risk = "low"

    approvers = set(other_teams)
    if conflicts or risk == "high":
        approvers.add("lead")
    if conflicts or blocked:
        verdict = "conflict"
    else:
        verdict = "works_with_changes" if other_teams else "works"
    recommendation, reason = recommend(product, verdict, risk, conflicts, alternative, total)

    return {
        "id": "chg-" + uuid.uuid4().hex[:6],
        "product_id": product["id"],
        "node_id": nodes[0]["id"],
        "node_label": nodes[0]["label"],
        "option_id": option.get("id", "custom"),
        "title": option["label"],
        "rationale": option.get("rationale", ""),
        "proposer": proposer,
        "proposer_name": ROLES[proposer],
        "affected": [n["id"] for n in nodes],
        "metric_delta": option.get("metric_delta", {}),
        "responses": responses,
        "conflicts": conflicts,
        "alternative": alternative,
        "risk": risk,
        "verdict": verdict,
        "total_effort_max": total,
        "approvers": [] if risk == "low" else sorted(approvers),
        "status": "auto_approved" if risk == "low" else "pending",
        "recommendation": recommendation,
        "recommendation_reason": reason,
        "recommendation_mode": "demo",  # rule-based; live_agents switches it to "live" when the Lead Agent answers
        "mode": mode,
        "created_at": now(),
    }


def recommend(product, verdict, risk, conflicts, alternative, total_effort) -> tuple[str, str]:
    """Deterministic Lead recommendation (demo mode, and the fallback if the live Lead Agent fails)."""
    top = ((product.get("objective") or {}).get("priorities") or ["the objective"])[0]
    if verdict == "conflict" and alternative:
        broken = conflicts[0]["text"] if conflicts else "a team's assessment"
        return "alternative", (f"The change conflicts with “{broken}”, and the cheaper alternative avoids that in "
                               f"{alternative['effort_days']:g} day(s). It keeps {top}, the top priority, on track without breaking that rule.")
    if risk == "high" and not alternative:
        why = f"conflicts with “{conflicts[0]['text']}”" if conflicts else f"is high risk (up to {total_effort:g} days of work)"
        return "reject", f"The change {why} and no cheaper alternative was found. Rejecting protects {top}, the top priority, until a safer option is proposed."
    return "approve", f"No conflicts block the change and it costs up to {total_effort:g} days. It moves {top}, the top priority, forward."


# ---------------------------------------------------------------------------
# Objective intake (from-scratch product)
# ---------------------------------------------------------------------------
def objective_intake(product: dict) -> dict:
    """Read the uploaded documents and fill the Objective Spec (demo mode).

    The live Lead Agent does this with Claude; this deterministic version keeps
    the same shape, and every field keeps its source document.
    """
    docs = {d["name"]: d["text"].lower() for d in product.get("documents", [])}

    def find(word):
        return next((name for name, text in docs.items() if word in text), None)

    spec = {
        "goal": {"value": "Reply to patient messages, judge urgency, book appointments and alert a nurse for serious cases",
                 "source": find("books the right appointment")},
        "success_metric": {"value": "100% of emergencies escalated; reply within 2 minutes",
                           "source": find("never miss an emergency"), "inferred": True},
        "priorities": {"value": ["patient safety", "reply speed", "booking accuracy"], "source": find("never miss an emergency")},
        "constraints": {"value": ["Reply < 2 min", "Patient data stays in-country", "Calendar: book/cancel only, no delete"],
                        "source": find("inside the country")},
        "deadline": {"value": "Pilot in 4 weeks, 2 clinics", "source": find("pilot")},
        "stakeholders": {"value": ["Operations manager", "Head nurse", "IT manager", "Patients"], "source": find("head nurse")},
    }
    gaps = [
        {"id": "emergency-list", "question": "Which symptoms are ALWAYS emergencies? The head nurse wants to agree this, not leave it to the agent.",
         "suggested": "Chest pain, difficulty breathing, stroke signs, severe bleeding, loss of consciousness, seizure"},
        {"id": "child-rule", "question": "Confirm: any message about a child under 2 goes to a nurse callback?",
         "suggested": "Yes, nurse callback within 1 hour"},
    ]
    return {"spec": spec, "gaps": gaps}


def build_from_objective(product: dict, answers: dict) -> dict:
    """After the lead confirms, the agents design the triage agent: a main and a
    backup urgency classifier, the booking tool and the nurse alert, then run
    the integration contract check and hand over to the AI engineer."""
    emergencies = answers.get("emergency-list") or "Chest pain, difficulty breathing, stroke signs, severe bleeding, loss of consciousness, seizure"
    child = answers.get("child-rule") or "Yes, nurse callback within 1 hour"
    product["objective"] = {
        "goal": "Triage patient messages and book appointments automatically",
        "success_metric": "100% of emergencies escalated; reply < 2 min",
        "priorities": ["patient safety", "reply speed", "booking accuracy"],
        "constraints": ["Reply < 2 min", "Data in-country", "Book/cancel only"],
        "deadline": "Pilot in 4 weeks",
    }
    product["rules"] = [
        {"id": "r-emergency", "text": f"Always emergency: {emergencies}", "source": "Head nurse (via intake)"},
        {"id": "r-child", "text": f"Child under 2: {child}", "source": "Head nurse (via intake)"},
        {"id": "e-nodelete", "text": "Calendar API: book and cancel only, never delete", "source": "IT manager"},
    ]

    shorts = {"data": "Messages", "agentA": "Agent A", "agentB": "Agent B", "booking": "Booking",
              "nurse": "Nurse alert", "whatsapp": "WhatsApp"}

    def n(id, label, kind, owner, effort, desc, x, y, options=None):
        return {"id": id, "label": label, "short": shorts.get(id, label), "kind": kind, "owner": owner,
                "effort_days": effort, "description": desc, "status": "ok", "position": {"x": x, "y": y},
                "change_options": options or []}

    product["nodes"] = [
        n("obj", "Objective: safe triage + booking", "objective", "lead", 0, "100% emergencies escalated, reply < 2 min", 0, 0),
        n("rule-emergency", "Rule: emergency symptoms", "requirement", "domain", 1, emergencies, 0, 150),
        n("data", "Patient messages (12k)", "dataset", "ds", 1, "82% Arabic · 1% emergencies · tagged outcomes", 290, 0),
        n("agentA", "Agent A (main)", "pipeline", "ds", 2,
          "LLM urgency classifier + hard safety rules · emergency recall 100%, routine accuracy 93%", 580, -80,
          options=[{"id": "drop-rules", "label": "Remove the hard safety rules and trust the LLM alone", "severity": 1.0,
                    "metric_delta": {"reply_speed": 5}, "rationale": "Simpler pipeline",
                    "conflicts": ["r-emergency"], "alternative": {"label": "Keep the rules; cache the rule check to save latency",
                                                                   "effort_days": 0.5, "metric_delta": {"reply_speed": 4}}}]),
        n("agentB", "Agent B (backup)", "pipeline", "ds", 1, "Rules + keyword matching only · emergency recall 100%, routine accuracy 78%", 580, 90),
        n("booking", "Booking tool (calendar API)", "engine", "engineer", 2, "find_slots, book, cancel · no delete", 870, -80),
        n("nurse", "Nurse alert", "engine", "engineer", 1, "Push to nurse station < 30 s", 870, 90),
        n("whatsapp", "WhatsApp channel", "engine", "engineer", 2, "Reply < 2 min, Arabic + English", 1160, 0),
    ]
    product["edges"] = [
        ("obj", "data", "feeds"), ("rule-emergency", "agentA", "feeds"), ("rule-emergency", "agentB", "feeds"),
        ("data", "agentA", "feeds"), ("data", "agentB", "feeds"),
        ("agentA", "booking", "feeds"), ("agentA", "nurse", "feeds"),
        ("booking", "whatsapp", "feeds"), ("nurse", "whatsapp", "feeds"),
    ]
    product["metrics"] = {"emergency_recall": 1.0, "routine_accuracy": 0.93, "reply_s": 40}
    product["metric_goals"] = {
        "emergency_recall": {"label": "Emergencies escalated", "goal": 1.0, "better": "higher", "unit": "%"},
        "routine_accuracy": {"label": "Routine booking accuracy", "goal": None, "better": "higher", "unit": "%"},
        "reply_s": {"label": "Reply time", "goal": 120, "better": "lower", "unit": "s"},
    }
    product["state"] = "handoff"
    product["summary"] = "Agents designed and tested the triage agent. Waiting for the AI Engineer to accept the handoff."
    steps = [
        ("DS Agent", "Profiled 12,000 messages: 82% Arabic, emergencies only 1% (about 120 examples), many messages mix symptoms and booking requests."),
        ("DS Agent", "Built 2 agent designs. A: LLM classifier + hard safety rules (emergency recall 100%, routine accuracy 93%). B: rules only (100% / 78%)."),
        ("DS Agent", "Chose A: patient safety is the top priority and both catch every emergency, but A books correctly far more often. B kept as backup."),
        ("Domain Agent", "Checked both designs against the head nurse's emergency list and the under-2 rule. No conflicts."),
        ("Engineer Agent", "Contract check: the booking tool used a delete call for rescheduling, so it was replaced with cancel + book. All checks pass."),
        ("Engineer Agent", "Handoff package ready: agent design, tools, test results on 400 messages, assumptions."),
    ]
    handoff = {
        "id": "chg-" + uuid.uuid4().hex[:6], "product_id": product["id"], "node_id": "agentA",
        "node_label": "Agent A (main)", "option_id": "handoff",
        "title": "Handoff: triage agent ready for integration",
        "rationale": "All contract checks passed. Emergency recall 100%, routine booking accuracy 93% on 400 test messages.",
        "proposer": "ds", "proposer_name": "Data Scientist", "affected": ["agentA", "booking", "nurse", "whatsapp"],
        "metric_delta": {}, "responses": [], "conflicts": [], "alternative": None,
        "risk": "medium", "verdict": "works", "total_effort_max": 0, "mode": "demo",
        "approvers": ["engineer"], "status": "pending", "created_at": now(), "kind": "handoff",
    }
    return {"steps": steps, "handoff": handoff}
