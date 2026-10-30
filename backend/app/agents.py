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
    "engineer": "AI Engineer Agent",
    "domain": "Domain Expert Agent",
    "lead": "Lead Agent",
}


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
        "mode": mode,
        "created_at": now(),
    }


# ---------------------------------------------------------------------------
# Objective intake (from-scratch product)
# ---------------------------------------------------------------------------
def objective_intake(product: dict) -> dict:
    """Read the uploaded documents and fill the Objective Spec.

    Demo mode uses simple extraction over the seeded documents; every field
    keeps its source so judges can see where each value came from.
    """
    docs = {d["name"]: d["text"].lower() for d in product.get("documents", [])}

    def find(word):
        return next((name for name, text in docs.items() if word in text), None)

    spec = {
        "goal": {"value": "Flag abnormal heart readings from wearables so nurses can call patients early",
                 "source": find("abnormal")},
        "priorities": {"value": ["recall", "speed", "cost"], "source": find("worse than a false alarm")},
        "success_metric": {"value": "Recall >= 90% (missing a case is worse than a false alarm)",
                           "source": find("worse than a false alarm"), "inferred": True},
        "constraints": {"value": ["Results to nurse < 5 min", "Patient data stays in-country"],
                        "source": find("5 minutes")},
        "deadline": {"value": "Pilot in 6 weeks across 3 clinics", "source": find("6 weeks")},
        "stakeholders": {"value": ["Clinic ops lead", "Cardiologist", "Nurses"], "source": find("cardiologist")},
    }
    gaps = [
        {"id": "abnormal-def", "question": "What counts as an 'abnormal' reading? The cardiologist said this still needs agreeing.",
         "suggested": "Resting HR > 120 or < 40 bpm, or irregular rhythm flag"},
        {"id": "metric-confirm", "question": "Confirm the target: recall >= 90%? (inferred from the brief)",
         "suggested": "Yes, recall >= 90%"},
    ]
    return {"spec": spec, "gaps": gaps}


def build_from_objective(product: dict, answers: dict) -> dict:
    """After the lead confirms, the DS Agent plans and builds the project graph,
    including a best and a backup pipeline, then runs the contract check."""
    abnormal = answers.get("abnormal-def") or "Resting HR > 120 or < 40 bpm, or irregular rhythm flag"
    product["objective"] = {
        "goal": "Flag abnormal heart readings from wearables",
        "success_metric": "Recall >= 90%",
        "priorities": ["recall", "speed", "cost"],
        "constraints": ["< 5 min to nurse", "data stays in-country"],
        "deadline": "Pilot in 6 weeks",
    }
    product["rules"] = [{"id": "r-abnormal", "text": f"Abnormal = {abnormal}", "source": "Cardiologist (via intake)"}]

    def n(id, label, kind, owner, effort, desc, x, y, status="ok"):
        return {"id": id, "label": label, "kind": kind, "owner": owner, "effort_days": effort,
                "description": desc, "status": status, "position": {"x": x, "y": y}, "change_options": []}

    product["nodes"] = [
        n("obj", "Objective: flag abnormal readings", "objective", "lead", 0, "Recall >= 90%, < 5 min", 0, 0),
        n("req-abnormal", "Rule: what is abnormal", "requirement", "domain", 1, abnormal, 0, 140),
        n("data", "Wearable readings (synthetic)", "dataset", "ds", 2, "3% abnormal, 12% missing", 260, 0),
        n("clean", "Clean + fix timestamps", "pipeline", "ds", 1, "Two timestamp formats unified", 520, 0),
        n("pipeA", "Pipeline A (best)", "pipeline", "ds", 2, "Gradient boosting + oversampling · recall 92% · 2 min", 780, -70),
        n("pipeB", "Pipeline B (backup)", "pipeline", "ds", 1, "Isolation forest · recall 85% · 30 s", 780, 90),
        n("alerts", "Nurse alert service", "engine", "engineer", 2, "Push alerts < 5 min", 1040, 0),
    ]
    product["nodes"][4]["change_options"] = [{
        "id": "to-lstm", "label": "Switch Pipeline A to an LSTM on raw signal", "severity": 1.6,
        "metric_delta": {"recall": 2, "latency_min": 2}, "rationale": "Learns rhythm patterns directly",
        "conflicts": [], "alternative": {"label": "Add rhythm features to gradient boosting",
                                          "effort_days": 1, "metric_delta": {"recall": 1}},
    }]
    product["edges"] = [
        ("obj", "data", "feeds"), ("req-abnormal", "clean", "feeds"), ("data", "clean", "feeds"),
        ("clean", "pipeA", "feeds"), ("clean", "pipeB", "feeds"), ("pipeA", "alerts", "feeds"),
    ]
    product["metrics"] = {"recall": 0.92, "latency_min": 2}
    product["state"] = "handoff"
    product["summary"] = "Agents built and checked the pipeline. Waiting for the AI Engineer to accept the handoff."
    steps = [
        ("DS Agent", "Profiled data: 3% abnormal (imbalanced), 12% missing values, two timestamp formats."),
        ("DS Agent", "Built 2 pipelines in the sandbox. A: recall 92%, 2 min. B: recall 85%, 30 s."),
        ("DS Agent", "Chose Pipeline A: recall is the top priority and it meets the 90% target. B kept as backup."),
        ("AI Engineer Agent", "Contract check: 'imbalanced-learn==0.9' not on the approved list → swapped to 0.12 and re-tested. All checks pass."),
        ("AI Engineer Agent", "Handoff package ready: code, data version, assumptions, test results."),
    ]
    handoff = {
        "id": "chg-" + uuid.uuid4().hex[:6], "product_id": product["id"], "node_id": "pipeA",
        "node_label": "Pipeline A (best)", "option_id": "handoff",
        "title": "Handoff: Pipeline A ready for engine work",
        "rationale": "All contract checks passed. Recall 92% (target 90%).",
        "proposer": "ds", "proposer_name": "Data Scientist", "affected": ["pipeA", "alerts"],
        "metric_delta": {}, "responses": [], "conflicts": [], "alternative": None,
        "risk": "medium", "verdict": "works", "total_effort_max": 0,
        "approvers": ["engineer"], "status": "pending", "created_at": now(), "kind": "handoff",
    }
    return {"steps": steps, "handoff": handoff}
