"""API for the agentic handoff platform.

State lives in memory and resets on restart (or POST /api/reset), which keeps
the hosted demo clean for every judge.
"""
import os
from collections import OrderedDict

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agents import TEAM_AGENTS, assess_change, build_from_objective, now, objective_intake
from .products import ROLES, build_products

app = FastAPI(title="Handoff Platform API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# One isolated demo state per visitor, so judges never see each other's clicks.
SESSIONS: "OrderedDict[str, dict]" = OrderedDict()
MAX_SESSIONS = 300
STATE: dict = {}  # bound to the current request's session


def _bind(session: str | None):
    global STATE
    key = (session or "default")[:64]
    if key not in SESSIONS:
        SESSIONS[key] = {}
        STATE = SESSIONS[key]
        reset_state()
        while len(SESSIONS) > MAX_SESSIONS:
            SESSIONS.popitem(last=False)
    SESSIONS.move_to_end(key)
    STATE = SESSIONS[key]


def reset_state():
    STATE.clear()
    STATE["products"] = build_products()
    STATE["proposals"] = {}
    STATE["activity"] = {pid: [] for pid in STATE["products"]}
    _log("support", "Ops Agent", "Weekly check: macro F1 0.88 (target 0.85), latency 420 ms. All green.")
    _log("fraud", "Domain Expert Agent",
         "Expert input recorded: family transfers are a normal pattern and shouldn't be flagged.")
    _log("heart", "Lead Agent", "3 documents uploaded by the client. Ready for objective intake.")
    # Seed the bottleneck: the expert's rule is waiting as a change proposal.
    fraud = STATE["products"]["fraud"]
    node = next(n for n in fraud["nodes"] if n["id"] == "req-family")
    _propose(fraud, node["id"], node["change_options"][0], "domain")


def _log(pid, actor, text, kind="info"):
    STATE["activity"][pid].insert(0, {"at": now(), "actor": actor, "text": text, "kind": kind})


def _product(pid):
    p = STATE["products"].get(pid)
    if not p:
        raise HTTPException(404, "Unknown product")
    return p


def _propose(product, node_id, option, proposer):
    card = assess_change(product, node_id, option, proposer)
    STATE["proposals"][card["id"]] = card
    for nid in card["affected"]:
        for n in product["nodes"]:
            if n["id"] == nid and card["status"] == "pending":
                n["status"] = "pending"
    who = ROLES[proposer]
    if card["status"] == "auto_approved":
        _log(product["id"], TEAM_AGENTS[proposer],
             f"{who} change “{card['title']}” is low risk: auto-approved and applied.", "auto")
    else:
        names = ", ".join(ROLES[a] for a in card["approvers"])
        _log(product["id"], TEAM_AGENTS[proposer],
             f"{who} proposed “{card['title']}”. Risk: {card['risk']}. Waiting on: {names}.", "proposal")
    return card


# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "mode": os.getenv("AGENT_MODE", "demo")}


@app.post("/api/reset")
def reset(x_session: str | None = Header(None)):
    _bind(x_session)
    reset_state()
    return {"ok": True}


@app.get("/api/roles")
def roles():
    return ROLES


@app.get("/api/products")
def products(x_session: str | None = Header(None)):
    _bind(x_session)
    out = []
    for p in STATE["products"].values():
        pending = [c for c in STATE["proposals"].values() if c["product_id"] == p["id"] and c["status"] == "pending"]
        out.append({k: p[k] for k in ("id", "name", "domain", "state", "summary", "metrics")} |
                   {"pending": len(pending)})
    return out


@app.get("/api/products/{pid}")
def product(pid: str, x_session: str | None = Header(None)):
    _bind(x_session)
    p = _product(pid)
    return p | {
        "edges": [{"source": s, "target": t, "kind": k} for s, t, k in p["edges"]],
        "activity": STATE["activity"][pid],
        "proposals": [c for c in STATE["proposals"].values() if c["product_id"] == pid],
    }


class ProposalIn(BaseModel):
    node_id: str
    option_id: str | None = None
    custom_text: str | None = None
    role: str


@app.post("/api/products/{pid}/proposals")
def propose(pid: str, body: ProposalIn, x_session: str | None = Header(None)):
    _bind(x_session)
    p = _product(pid)
    node = next((n for n in p["nodes"] if n["id"] == body.node_id), None)
    if not node:
        raise HTTPException(404, "Unknown node")
    if body.role not in ROLES:
        raise HTTPException(400, "Unknown role")
    if body.option_id:
        option = next((o for o in node["change_options"] if o["id"] == body.option_id), None)
        if not option:
            raise HTTPException(404, "Unknown change option")
    elif body.custom_text:
        option = {"id": "custom", "label": body.custom_text.strip()[:140], "severity": 1.0,
                  "metric_delta": {}, "rationale": "Custom change (estimate from graph only)"}
    else:
        raise HTTPException(400, "Give option_id or custom_text")
    return _propose(p, node["id"], option, body.role)


class DecisionIn(BaseModel):
    role: str
    decision: str  # approve | alternative | reject


@app.post("/api/proposals/{cid}/decide")
def decide(cid: str, body: DecisionIn, x_session: str | None = Header(None)):
    _bind(x_session)
    card = STATE["proposals"].get(cid)
    if not card:
        raise HTTPException(404, "Unknown proposal")
    if card["status"] != "pending":
        raise HTTPException(409, "Already decided")
    if body.role not in card["approvers"] and body.role != "lead":
        raise HTTPException(403, "This role is not an approver for this change")
    p = _product(card["product_id"])
    if body.decision == "alternative" and not card.get("alternative"):
        raise HTTPException(400, "No alternative for this change")
    card["status"] = {"approve": "approved", "alternative": "approved_alternative", "reject": "rejected"}[body.decision]
    card["decided_by"] = body.role
    new_status = "ok" if body.decision == "reject" else "changed"
    for n in p["nodes"]:
        if n["id"] in card["affected"] and n["status"] == "pending":
            n["status"] = new_status
    if card.get("kind") == "handoff" and body.decision == "approve":
        p["state"] = "building"
        p["summary"] = "Handoff accepted. Engine work started with full context attached."
    if card["node_id"] == "req-family" and body.decision != "reject":
        p["state"] = "resolved"
        p["summary"] = "Bottleneck resolved by the agents in one decision. No meeting was needed."
        p["metrics"]["false_alarm_rate"] = 0.06 if body.decision == "alternative" else 0.054
    what = card["alternative"]["label"] if body.decision == "alternative" else card["title"]
    _log(p["id"], ROLES[body.role], f"{body.decision.title()}: “{what}”. No meeting needed.", "decision")
    return card


@app.get("/api/inbox/{role}")
def inbox(role: str, x_session: str | None = Header(None)):
    _bind(x_session)
    return [c for c in STATE["proposals"].values()
            if c["status"] == "pending" and (role in c["approvers"] or (role == "lead" and c["risk"] == "high"))]


# --- from-scratch flow -----------------------------------------------------
@app.post("/api/products/{pid}/intake")
def intake(pid: str, x_session: str | None = Header(None)):
    _bind(x_session)
    p = _product(pid)
    if not p.get("documents"):
        raise HTTPException(400, "No documents to read")
    result = objective_intake(p)
    _log(pid, "Lead Agent", "Read 3 documents and filled the Objective Spec. 2 gaps need confirming.")
    return result


class ConfirmIn(BaseModel):
    answers: dict[str, str] = {}


@app.post("/api/products/{pid}/confirm")
def confirm(pid: str, body: ConfirmIn, x_session: str | None = Header(None)):
    _bind(x_session)
    p = _product(pid)
    if p["nodes"]:
        raise HTTPException(409, "Already built")
    result = build_from_objective(p, body.answers)
    _log(pid, "AI Lead", "Confirmed the Objective Spec.", "decision")
    for actor, text in result["steps"]:
        _log(pid, actor, text, "agent")
    STATE["proposals"][result["handoff"]["id"]] = result["handoff"]
    _log(pid, "DS Agent", "Handoff sent to the AI Engineer's inbox.", "proposal")
    return result


# --- project chat (keyword retrieval for now; ChromaDB later) --------------
class AskIn(BaseModel):
    question: str


@app.post("/api/products/{pid}/ask")
def ask(pid: str, body: AskIn, x_session: str | None = Header(None)):
    _bind(x_session)
    p = _product(pid)
    words = {w for w in body.question.lower().split() if len(w) > 3}
    docs = [{"text": a["text"], "source": f"{a['actor']} · {a['at'][:10]}"} for a in STATE["activity"][pid]]
    docs += [{"text": f"{n['label']}: {n['description']}", "source": "Project Graph"} for n in p["nodes"]]
    docs += [{"text": r["text"], "source": r["source"]} for r in p.get("rules", [])]
    scored = sorted(docs, key=lambda d: -len(words & set(d["text"].lower().split())))
    hits = [d for d in scored[:3] if words & set(d["text"].lower().split())]
    if not hits:
        return {"answer": "I couldn't find that in this project's history yet.", "sources": []}
    return {"answer": hits[0]["text"], "sources": hits}
