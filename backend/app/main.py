"""API for the agentic handoff platform.

Each visitor (judge) gets an isolated session, passed explicitly to every
helper so long-running agent calls can never mix sessions up.

Live mode (Claude + tools + RAG) runs when ANTHROPIC_API_KEY is set; if a
live call fails, the platform falls back to the deterministic demo agents so
the demo never breaks.
"""
import logging
import os
import threading
from collections import OrderedDict

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import llm
from .agents import TEAM_AGENTS, assess_change, build_from_objective, now, objective_intake
from .products import ROLES, build_products
from .rag import AGENT_SCOPES, Retriever, live_chunks

log = logging.getLogger("relay")
app = FastAPI(title="Relay API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

SESSIONS: "OrderedDict[str, dict]" = OrderedDict()
SESSIONS_LOCK = threading.Lock()
MAX_SESSIONS = 300


def new_state() -> dict:
    st = {"products": build_products(), "proposals": {}, "lock": threading.Lock()}
    st["activity"] = {pid: [] for pid in st["products"]}
    _log(st, "support", "Ops Agent", "Weekly check: macro F1 0.88 (target 0.85), latency 420 ms. All green.")
    _log(st, "fraud", "Domain Expert Agent",
         "Expert input recorded: family transfers are a normal pattern and shouldn't be flagged.")
    _log(st, "heart", "Lead Agent", "3 documents uploaded by the client. Ready for objective intake.")
    fraud = st["products"]["fraud"]
    node = next(n for n in fraud["nodes"] if n["id"] == "req-family")
    _store_card(st, fraud, assess_change(fraud, node["id"], node["change_options"][0], "domain"))
    return st


def session(x_session: str | None) -> dict:
    key = (x_session or "default")[:64]
    with SESSIONS_LOCK:
        if key not in SESSIONS:
            SESSIONS[key] = new_state()
            while len(SESSIONS) > MAX_SESSIONS:
                SESSIONS.popitem(last=False)
        SESSIONS.move_to_end(key)
        return SESSIONS[key]


def _log(st, pid, actor, text, kind="info"):
    st["activity"][pid].insert(0, {"at": now(), "actor": actor, "text": text, "kind": kind})


def _product(st, pid):
    p = st["products"].get(pid)
    if not p:
        raise HTTPException(404, "Unknown product")
    return p


def _store_card(st, product, card, replaces: str | None = None):
    if replaces:
        st["proposals"].pop(replaces, None)
    st["proposals"][card["id"]] = card
    if card["status"] == "pending":
        for n in product["nodes"]:
            if n["id"] in card["affected"]:
                n["status"] = "pending"
    who = ROLES[card["proposer"]]
    actor = TEAM_AGENTS[card["proposer"]]
    tag = " (live agents)" if card.get("mode") == "live" else ""
    if replaces:
        _log(st, product["id"], "Orchestrator",
             f"Re-assessed “{card['title']}” with {len(card['responses'])} agents{tag}. Risk: {card['risk']}.", "agent")
    elif card["status"] == "auto_approved":
        _log(st, product["id"], actor, f"{who} change “{card['title']}” is low risk: auto-approved and applied{tag}.", "auto")
    else:
        names = ", ".join(ROLES[a] for a in card["approvers"])
        _log(st, product["id"], actor,
             f"{who} proposed “{card['title']}”. Risk: {card['risk']}. Waiting on: {names}{tag}.", "proposal")
    return card


def _assess(st, product, node_id, option, proposer):
    """Live agents when available, demo agents otherwise (or if live fails)."""
    if llm.enabled():
        try:
            from .live_agents import assess_change_live
            return assess_change_live(product, node_id, option, proposer, st["activity"][product["id"]])
        except Exception as e:  # never break the demo
            log.exception("live assessment failed")
            card = assess_change(product, node_id, option, proposer)
            card["fallback_reason"] = str(e)[:200]
            return card
    return assess_change(product, node_id, option, proposer)


# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "mode": "live" if llm.enabled() else "demo", "model": llm.MODEL if llm.enabled() else None}


@app.post("/api/reset")
def reset(x_session: str | None = Header(None)):
    key = (x_session or "default")[:64]
    with SESSIONS_LOCK:
        SESSIONS[key] = new_state()
    return {"ok": True}


@app.get("/api/products")
def products(x_session: str | None = Header(None)):
    st = session(x_session)
    out = []
    for p in st["products"].values():
        pending = [c for c in st["proposals"].values() if c["product_id"] == p["id"] and c["status"] == "pending"]
        out.append({k: p[k] for k in ("id", "name", "domain", "state", "summary", "metrics")} | {"pending": len(pending)})
    return out


@app.get("/api/products/{pid}")
def product(pid: str, x_session: str | None = Header(None)):
    st = session(x_session)
    p = _product(st, pid)
    return p | {
        "edges": [{"source": s, "target": t, "kind": k} for s, t, k in p["edges"]],
        "activity": st["activity"][pid],
        "proposals": [c for c in st["proposals"].values() if c["product_id"] == pid],
    }


class ProposalIn(BaseModel):
    node_id: str
    option_id: str | None = None
    custom_text: str | None = None
    role: str


@app.post("/api/products/{pid}/proposals")
def propose(pid: str, body: ProposalIn, x_session: str | None = Header(None)):
    st = session(x_session)
    p = _product(st, pid)
    node = next((n for n in p["nodes"] if n["id"] == body.node_id), None)
    if not node:
        raise HTTPException(404, "Unknown node")
    if body.role not in ROLES:
        raise HTTPException(400, "Unknown role")
    if body.option_id:
        option = next((o for o in node["change_options"] if o["id"] == body.option_id), None)
        if not option:
            raise HTTPException(404, "Unknown change option")
    elif body.custom_text and body.custom_text.strip():
        option = {"id": "custom", "label": body.custom_text.strip()[:200], "severity": 1.0,
                  "metric_delta": {}, "rationale": ""}
    else:
        raise HTTPException(400, "Give option_id or custom_text")
    card = _assess(st, p, node["id"], option, body.role)
    with st["lock"]:
        return _store_card(st, p, card)


@app.post("/api/proposals/{cid}/rerun")
def rerun(cid: str, x_session: str | None = Header(None)):
    """Re-assess an existing proposal with the live agents (e.g. the seeded bottleneck)."""
    st = session(x_session)
    card = st["proposals"].get(cid)
    if not card:
        raise HTTPException(404, "Unknown proposal")
    if card["status"] != "pending":
        raise HTTPException(409, "Already decided")
    if not llm.enabled():
        raise HTTPException(400, "Live agents are not enabled on this server")
    p = _product(st, card["product_id"])
    node = next(n for n in p["nodes"] if n["id"] == card["node_id"])
    option = next((o for o in node["change_options"] if o["id"] == card["option_id"]),
                  {"id": "custom", "label": card["title"], "severity": 1.0, "metric_delta": {}, "rationale": card["rationale"]})
    new = _assess(st, p, node["id"], option, card["proposer"])
    with st["lock"]:
        return _store_card(st, p, new, replaces=cid)


class DecisionIn(BaseModel):
    role: str
    decision: str  # approve | alternative | reject


@app.post("/api/proposals/{cid}/decide")
def decide(cid: str, body: DecisionIn, x_session: str | None = Header(None)):
    st = session(x_session)
    with st["lock"]:
        card = st["proposals"].get(cid)
        if not card:
            raise HTTPException(404, "Unknown proposal")
        if card["status"] != "pending":
            raise HTTPException(409, "Already decided")
        if body.role not in card["approvers"] and body.role != "lead":
            raise HTTPException(403, "This role is not an approver for this change")
        if body.decision not in ("approve", "alternative", "reject"):
            raise HTTPException(400, "Unknown decision")
        if body.decision == "alternative" and not card.get("alternative"):
            raise HTTPException(400, "No alternative for this change")
        p = _product(st, card["product_id"])
        card["status"] = {"approve": "approved", "alternative": "approved_alternative", "reject": "rejected"}[body.decision]
        card["decided_by"] = body.role
        for n in p["nodes"]:
            if n["id"] in card["affected"] and n["status"] == "pending":
                n["status"] = "ok" if body.decision == "reject" else "changed"
        if card.get("kind") == "handoff" and body.decision == "approve":
            p["state"] = "building"
            p["summary"] = "Handoff accepted. Engine work started with full context attached."
        if card["node_id"] == "req-family" and body.decision != "reject":
            p["state"] = "resolved"
            p["summary"] = "Bottleneck resolved by the agents in one decision. No meeting was needed."
            p["metrics"]["false_alarm_rate"] = 0.06 if body.decision == "alternative" else 0.054
        what = card["alternative"]["label"] if body.decision == "alternative" else card["title"]
        _log(st, p["id"], ROLES[body.role], f"{body.decision.title()}: “{what}”. No meeting needed.", "decision")
        return card


@app.get("/api/inbox/{role}")
def inbox(role: str, x_session: str | None = Header(None)):
    st = session(x_session)
    return [c for c in st["proposals"].values()
            if c["status"] == "pending" and (role in c["approvers"] or (role == "lead" and c["risk"] == "high"))]


# --- from-scratch flow -----------------------------------------------------
@app.post("/api/products/{pid}/intake")
def intake(pid: str, x_session: str | None = Header(None)):
    st = session(x_session)
    p = _product(st, pid)
    if not p.get("documents"):
        raise HTTPException(400, "No documents to read")
    mode = "demo"
    result = None
    if llm.enabled():
        try:
            from .live_agents import intake_live
            result, mode = intake_live(p), "live"
        except Exception:
            log.exception("live intake failed")
    if result is None:
        result = objective_intake(p)
    p["intake"] = result
    n_docs, n_gaps = len(p["documents"]), len(result["gaps"])
    _log(st, pid, "Lead Agent", f"Read {n_docs} documents and filled the Objective Spec. {n_gaps} gap(s) need confirming.")
    return result | {"mode": mode}


class ConfirmIn(BaseModel):
    answers: dict[str, str] = {}


@app.post("/api/products/{pid}/confirm")
def confirm(pid: str, body: ConfirmIn, x_session: str | None = Header(None)):
    st = session(x_session)
    p = _product(st, pid)
    with st["lock"]:
        if p["nodes"]:
            raise HTTPException(409, "Already built")
        result = build_from_objective(p, body.answers)
        spec = (p.get("intake") or {}).get("spec")
        if spec:  # use what the Lead Agent actually extracted
            val = lambda k: spec.get(k, {}).get("value")  # noqa: E731
            pri = val("priorities")
            p["objective"] = {
                "goal": val("goal") or p["objective"]["goal"],
                "success_metric": val("success_metric") or p["objective"]["success_metric"],
                "priorities": pri if isinstance(pri, list) else p["objective"]["priorities"],
                "constraints": val("constraints") or p["objective"]["constraints"],
                "deadline": val("deadline") or p["objective"]["deadline"],
            }
        _log(st, pid, "AI Lead", "Confirmed the Objective Spec.", "decision")
        for actor, text in result["steps"]:
            _log(st, pid, actor, text, "agent")
        st["proposals"][result["handoff"]["id"]] = result["handoff"]
        _log(st, pid, "DS Agent", "Handoff sent to the AI Engineer's inbox.", "proposal")
        return result


# --- project chat + Expert Twin (RAG) ---------------------------------------
class AskIn(BaseModel):
    question: str
    agent: str = "project"  # project | domain


@app.post("/api/products/{pid}/ask")
def ask(pid: str, body: AskIn, x_session: str | None = Header(None)):
    st = session(x_session)
    p = _product(st, pid)
    as_expert = body.agent == "domain"
    retriever = Retriever(pid, live_chunks(p, st["activity"][pid]))
    hits = retriever.search(body.question, AGENT_SCOPES["domain" if as_expert else "lead"], k=5)
    if not hits:
        result = {"answer": "I couldn't find anything about that in this project's knowledge yet.",
                  "sources": [], "confident": False, "mode": "demo"}
    elif llm.enabled():
        try:
            from .live_agents import answer_live
            out = answer_live(body.question, hits, as_expert)
            cited = [hits[i - 1] for i in out.get("cited", []) if 0 < i <= len(hits)] or hits[:1]
            result = {"answer": out["answer"], "sources": cited, "confident": out.get("confident", True), "mode": "live"}
        except Exception:
            log.exception("live answer failed")
            result = None
    else:
        result = None
    if result is None:
        result = {"answer": hits[0]["text"], "sources": hits[:3], "confident": hits[0]["score"] >= 1.0, "mode": "demo"}
    result["escalated"] = as_expert and not result["confident"]
    if result["escalated"]:
        _log(st, pid, "Domain Expert Agent",
             f"Couldn't answer “{body.question[:80]}” from the expert's knowledge. Escalated to the Domain Expert.", "proposal")
    return result
