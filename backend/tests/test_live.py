"""Live agents tested against a fake Claude that follows the tool protocol."""
import json
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app

c = TestClient(app)


class FakeClaude:
    """Step 1: call tools. Step 2: submit an answer built from what the tools returned."""

    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, model, max_tokens, system, tools, messages, tool_choice):
        self.calls += 1
        names = {t["name"] for t in tools}
        tool_results = [b for m in messages if m["role"] == "user" and isinstance(m["content"], list)
                        for b in m["content"]]
        if "submit" in names and tool_choice.get("name") == "submit" or tool_results or names == {"submit"}:
            props = next(t for t in tools if t["name"] == "submit")["input_schema"]["properties"]
            if "effort_min_days" in props:
                data = json.dumps([json.loads(b["content"]) for b in tool_results])
                conflict = ["p-pilot"] if "Domain Expert Agent" in system and "pilot" in data.lower() else []
                ans = {"effort_min_days": 1, "effort_max_days": 2, "verdict": "conflict" if conflict else "works",
                       "message": "Assessed from tools.", "conflicts": conflict,
                       "evidence": ["engineer/change-history.md › May 2026"],
                       "alternative": {"label": "Post-processing overlap rule", "effort_days": 0.5}}
            elif "spec" in props:
                f = lambda v: {"value": v, "source": "Client brief.pdf"}  # noqa: E731
                ans = {"spec": {"goal": f("Triage patient messages"), "success_metric": f("100% emergencies escalated"),
                                "priorities": f(["safety", "speed"]), "constraints": f(["< 2 min"]),
                                "deadline": f("4 weeks"), "stakeholders": f(["Head nurse"])},
                       "gaps": [{"id": "emergency-list", "question": "Which symptoms?", "suggested": "Chest pain"}]}
            else:
                ans = {"answer": "Only a helmet worn on the head counts.", "cited": [1], "confident": True}
            return NS(content=[NS(type="tool_use", id="t-submit", name="submit", input=ans)])
        blocks = [NS(type="tool_use", id=f"t{i}", name=n, input={"query": "similar past change actual effort"} if n == "search_knowledge" else {})
                  for i, n in enumerate(sorted(names - {"submit"}))]
        return NS(content=blocks or [NS(type="text", text="thinking")])


@pytest.fixture(autouse=True)
def fake():
    f = FakeClaude()
    llm.set_client(f)
    c.post("/api/reset")
    yield f
    llm.set_client(None)


def test_health_live():
    assert c.get("/api/health").json()["mode"] == "live"


def test_live_rerun_of_bottleneck(fake):
    card = c.get("/api/inbox/ds").json()[0]
    new = c.post(f"/api/proposals/{card['id']}/rerun").json()
    assert new["mode"] == "live"
    teams = {r["team"] for r in new["responses"]}
    assert teams == {"ds", "engineer", "domain"}  # dispatched in parallel by LangGraph
    assert all("get_impact_on_my_team" in r["tools_used"] for r in new["responses"])
    assert new["conflicts"][0]["id"] == "p-pilot"
    assert new["risk"] == "high"
    assert new["alternative"]["effort_days"] == 0.5
    assert card["id"] not in {x["id"] for x in c.get("/api/inbox/ds").json()}


def test_live_custom_change():
    card = c.post("/api/products/ppe/proposals",
                  json={"node_id": "edge", "custom_text": "Move inference to a cloud GPU", "role": "engineer"}).json()
    assert card["mode"] == "live" and "ds" in {r["team"] for r in card["responses"]}


def test_live_failure_falls_back(fake):
    def boom(**_):
        raise RuntimeError("API down")
    fake.create = boom
    card = c.post("/api/products/ppe/proposals",
                  json={"node_id": "edge", "custom_text": "Move inference to a cloud GPU", "role": "engineer"}).json()
    assert card["mode"] == "demo" and "API down" in card["fallback_reason"]


def test_live_intake_then_confirm():
    r = c.post("/api/products/triage/intake").json()
    assert r["mode"] == "live" and r["spec"]["goal"]["source"] == "Client brief.pdf"
    c.post("/api/products/triage/confirm", json={"answers": {"emergency-list": "Chest pain"}})
    assert c.get("/api/products/triage").json()["objective"]["success_metric"] == "100% emergencies escalated"


def test_live_ask_and_expert_twin():
    a = c.post("/api/products/ppe/ask", json={"question": "does a helmet in the hand count", "agent": "domain"}).json()
    assert a["mode"] == "live" and a["sources"] and not a["escalated"]


def test_live_limit_per_session(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "LIVE_LIMIT", 1)
    c.post("/api/reset")
    first = c.post("/api/products/ppe/proposals", json={"node_id": "edge", "custom_text": "A", "role": "engineer"}).json()
    second = c.post("/api/products/ppe/proposals", json={"node_id": "edge", "custom_text": "B", "role": "engineer"}).json()
    assert first["mode"] == "live" and second["mode"] == "demo"
    assert "limit" in second["fallback_reason"]
