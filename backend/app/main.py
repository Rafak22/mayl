"""API for the agentic handoff platform.

Each visitor (judge) gets an isolated session, passed explicitly to every
helper so long-running agent calls can never mix sessions up.

Live mode (Claude + tools + RAG) runs when ANTHROPIC_API_KEY is set; if a
live call fails, the platform falls back to the deterministic demo agents so
the demo never breaks.
"""
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import llm
from .agents import AGENT_BY_NAME, TEAM_AGENTS, assess_change, build_from_objective, now, objective_intake
from .details import SAMPLES, documents, product_details
from .products import ROLES, build_products
from .rag import AGENT_SCOPES, Retriever, live_chunks

log = logging.getLogger("mayl")
app = FastAPI(title="Mayl API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/samples", StaticFiles(directory=SAMPLES), name="samples")  # example images for the Data tab

CHAT_AGENTS = ("lead", "ds", "engineer", "domain", "project")
RECOMMENDATION_TEXT = {"approve": "approving the change", "alternative": "the cheaper alternative",
                       "reject": "rejecting the change", "needs_info": "asking for more detail"}
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def _mostly_english(text: str) -> bool:
    letters = LETTER.findall(text)
    return not letters or sum(c.isascii() for c in letters) >= 0.8 * len(letters)


def _merge_hits(lists: list[list[dict]], k: int) -> list[dict]:
    """Union of several searches, best score per source first."""
    best = {}
    for hits in lists:
        for h in hits:
            if h["source"] not in best or h["score"] > best[h["source"]]["score"]:
                best[h["source"]] = h
    return sorted(best.values(), key=lambda h: -h["score"])[:k]

SESSIONS: "OrderedDict[str, dict]" = OrderedDict()
SESSIONS_LOCK = threading.Lock()
MAX_SESSIONS = 300
# Separate budgets per visitor, so chatting never uses up the live change reviews.
LIVE_LIMITS = {
    "review": int(os.getenv("LIVE_REVIEW_LIMIT_PER_SESSION", os.getenv("LIVE_LIMIT_PER_SESSION", "8"))),  # reviews + intake
    "chat": int(os.getenv("LIVE_CHAT_LIMIT_PER_SESSION", "20")),
}


def _live_left(st, kind: str) -> bool:
    return st.get("live_used", {}).get(kind, 0) < LIVE_LIMITS[kind]


def _use_live(st, kind: str) -> bool:
    """Live agents if enabled and this visitor still has live runs of this kind left."""
    if not llm.enabled() or not _live_left(st, kind):
        return False
    used = st.setdefault("live_used", {})
    used[kind] = used.get(kind, 0) + 1
    return True


def new_state() -> dict:
    st = {"products": build_products(), "proposals": {}, "lock": threading.Lock()}
    st["activity"] = {pid: [] for pid in st["products"]}
    _log(st, "chatbot", "Ops check",
         "Weekly check: accuracy 91.2% (target 90%), containment 64%, median handover 22 s. Knowledge base refreshed Sunday. All green.",
         agent="ds")
    _log(st, "ppe", "Domain Expert",
         "Added the helmet rule after the site visit: a helmet in the hand, on a belt or on the ground is a violation.")
    _log(st, "triage", "Lead Agent", "3 documents uploaded by Shifa Clinics. Ready for objective intake.")
    for p in st["products"].values():  # seed each product's open bottleneck, if any
        seed = p.get("seed_proposal")
        if seed:
            node = next(n for n in p["nodes"] if n["id"] == seed["node"])
            option = next(o for o in node["change_options"] if o["id"] == seed["option"])
            start = time.perf_counter()
            card = assess_change(p, node["id"], option, seed["proposer"])
            card["review_seconds"] = round(time.perf_counter() - start, 2)
            _store_card(st, p, card)
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


def _log(st, pid, actor, text, kind="info", agent=None):
    """Newest first. `agent` (lead | ds | engineer | domain) marks entries written by an agent; None = a human."""
    agent = agent or AGENT_BY_NAME.get(actor)
    st["seq"] = st.get("seq", 0) + 1  # orders entries across products; timestamps only have 1 s resolution
    st["activity"][pid].insert(0, {"at": now(), "seq": st["seq"], "actor": actor, "text": text, "kind": kind,
                                   "agent": agent})


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
    pid, who = product["id"], ROLES[card["proposer"]]
    tag = " (live agents)" if card.get("mode") == "live" else ""
    if replaces:
        _log(st, pid, "Mayl", f"Re-assessed “{card['title']}” with {len(card['responses'])} agents{tag}. Risk: {card['risk']}.", "agent")
    elif card["status"] == "auto_approved":
        _log(st, pid, who, f"Proposed “{card['title']}”. Low risk, so it was auto-approved and applied{tag}.", "auto")
    else:
        names = ", ".join(ROLES[a] for a in card["approvers"])
        _log(st, pid, who, f"Proposed “{card['title']}”. Risk: {card['risk']}. Waiting on: {names}{tag}.", "proposal")
    for r in card["responses"]:  # each agent's own assessment, in its words
        _log(st, pid, r["agent"], r["message"], "review", agent=r["team"])
    if card["status"] == "pending" and card.get("recommendation"):
        _log(st, pid, TEAM_AGENTS["lead"],
             f"Recommends {RECOMMENDATION_TEXT[card['recommendation']]} for “{card['title']}”. {card['recommendation_reason']}",
             "recommendation", agent="lead")
    return card


def _assess(st, product, node_id, option, proposer):
    """Run the agents on a change and record how long the review took."""
    start = time.perf_counter()
    card = _run_agents(st, product, node_id, option, proposer)
    card["review_seconds"] = round(time.perf_counter() - start, 2)
    return card


def _run_agents(st, product, node_id, option, proposer):
    """Live agents when available, demo agents otherwise (or if live fails)."""
    if _use_live(st, "review"):
        try:
            from .live_agents import assess_change_live
            return assess_change_live(product, node_id, option, proposer, st["activity"][product["id"]])
        except Exception as e:  # never break the demo
            log.exception("live assessment failed")
            card = assess_change(product, node_id, option, proposer)
            card["fallback_reason"] = str(e)[:200]
            return card
    card = assess_change(product, node_id, option, proposer)
    if llm.enabled():
        card["fallback_reason"] = "Live-review limit for this session reached"
    return card


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
        steps = sorted((n for n in p["nodes"] if n["kind"] in ("dataset", "pipeline", "engine")),
                       key=lambda n: (n["position"]["x"], n["position"]["y"]))
        out.append({k: p.get(k) for k in ("id", "name", "domain", "client", "tech", "expert", "state", "summary",
                                           "objective", "metrics", "metric_goals")} | {
            "pending": len(pending),
            "steps": [{"id": n["id"], "short": n.get("short", n["label"]), "status": n["status"], "owner": n["owner"]}
                      for n in steps],
            "documents": len(p.get("documents") or []),
        })
    return out


@app.get("/api/products/{pid}/details")
def details(pid: str, x_session: str | None = Header(None)):
    """Data & solution and Knowledge tabs: examples, dataset, pipeline, samples and knowledge documents."""
    return product_details(_product(session(x_session), pid))


@app.get("/api/stats")
def stats(x_session: str | None = Header(None)):
    """Overview and Agents pages: counted from this session's proposals and activity."""
    st = session(x_session)
    today = datetime.now(timezone.utc).date().isoformat()
    reviews = [c for c in st["proposals"].values() if c.get("kind") != "handoff" and c["responses"]]
    timed = [c["review_seconds"] for c in reviews if "review_seconds" in c]
    activity = sorted(({**a, "product_id": pid, "product_name": st["products"][pid]["name"]}
                       for pid, entries in st["activity"].items() for a in entries),
                      key=lambda a: a["seq"], reverse=True)

    decided = [c for c in reviews if c["status"] in ("approved", "approved_alternative", "rejected") and c.get("recommendation")]
    followed = {"approve": "approved", "alternative": "approved_alternative", "reject": "rejected"}
    accepted = sum(c["status"] == followed[c["recommendation"]] for c in decided)
    docs = [d for pid in st["products"] for d in documents(pid)]
    agents = {}
    for key in ("lead", "ds", "engineer", "domain"):
        mine = [a for a in activity if a["agent"] == key]
        count = lambda kind: sum(a["kind"] == kind for a in mine)  # noqa: E731
        agents[key] = {
            "reviews": count("review"), "recommendations": count("recommendation"),
            "answers": count("answer"), "escalations": count("escalation"),
            "documents": sum(d["agent"] == key for d in docs) if key != "lead" else len(docs),
            "latest": mine[0] if mine else None,
        }
    agents["lead"]["accepted"] = {"followed": accepted, "decided": len(decided)}
    return {
        "changes_reviewed_today": sum(c["created_at"].startswith(today) for c in reviews),
        "changes_reviewed": len(reviews),
        "avg_review_seconds": round(sum(timed) / len(timed), 2) if timed else None,
        "conflicts_caught": sum(c["verdict"] == "conflict" for c in reviews),
        "agents": agents,
        "latest": activity[:12],
    }


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
    if not _live_left(st, "review"):
        raise HTTPException(429, "You've used all live reviews for this session. Restart the demo to start over.")
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
        seed = p.get("seed_proposal")
        if seed and card["node_id"] == seed["node"] and body.decision != "reject":
            p["state"] = "resolved"
            p["summary"] = p["resolved"]["summary"]
            p["metrics"].update(p["resolved"]["metrics"])
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
    if _use_live(st, "review"):
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


# --- chat with an agent (RAG over that agent's knowledge) -------------------
class AskIn(BaseModel):
    question: str
    agent: str = "project"  # lead | ds | engineer | domain | project


@app.post("/api/products/{pid}/ask")
def ask(pid: str, body: AskIn, x_session: str | None = Header(None)):
    st = session(x_session)
    p = _product(st, pid)
    if body.agent not in CHAT_AGENTS:
        raise HTTPException(400, f"agent must be one of: {', '.join(CHAT_AGENTS)}")
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Empty question")
    retriever = Retriever(pid, live_chunks(p, st["activity"][pid]))
    scopes = AGENT_SCOPES["lead" if body.agent == "project" else body.agent]
    result, queries = None, [question]
    if _use_live(st, "chat"):
        # Live: also search in English (the documents are mostly English), drop the similarity cutoff and let
        # the agent judge whether the hits answer the question; it escalates when they don't.
        try:
            from .live_agents import answer_live, translate_for_search
            if not _mostly_english(question):
                queries.append(translate_for_search(question))
            hits = _merge_hits([retriever.search(q, scopes, k=5, min_similarity=0.0) for q in queries], k=5)
            if hits:
                out = answer_live(question, hits, body.agent)
                cited = [hits[i - 1] for i in out.get("cited", []) if 0 < i <= len(hits)] or hits[:1]
                result = {"answer": out["answer"], "sources": cited, "confident": out.get("confident", True), "mode": "live"}
        except Exception:
            log.exception("live answer failed")
    if result is None:  # demo agents: the similarity cutoff decides
        hits = retriever.search(question, scopes, k=5)
        if not hits:
            result = {"answer": "I couldn't find anything about that in this project's knowledge yet.",
                      "sources": [], "confident": False, "mode": "demo"}
        else:
            result = {"answer": hits[0]["text"], "sources": hits[:3], "confident": hits[0]["score"] >= 1.0, "mode": "demo"}
    result["search_queries"] = queries
    result["agent"] = body.agent
    result["escalated"] = body.agent == "domain" and not result["confident"]
    if body.agent != "project":
        _log(st, pid, TEAM_AGENTS[body.agent], f"Answered a question: “{question[:100]}”", "answer", agent=body.agent)
    if result["escalated"]:
        _log(st, pid, TEAM_AGENTS["domain"],
             f"Couldn't answer “{question[:80]}” from the expert's knowledge, so it went to the Domain Expert.",
             "escalation", agent="domain")
    return result
