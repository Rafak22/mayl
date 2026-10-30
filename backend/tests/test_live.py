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
        self.seen = []  # (system, first user message, submit schema) per call
        self.propose_alternative = True
        self.lead_fails = False

    def lead_calls(self):
        return [s for s in self.seen if "recommendation" in s[2]["properties"]]

    def create(self, model, max_tokens, system, messages, tools=None, tool_choice=None, output_config=None):
        self.calls += 1
        # Like current models: forced tool use is rejected; structured outputs answer in JSON text.
        assert tool_choice in (None, {"type": "auto"}), "forced tool_choice is a 400 on this model"
        structured = output_config is not None
        assert structured != bool(tools), "tool-less agents use structured outputs, tool agents a submit tool"
        names = {t["name"] for t in tools or []}
        schema = output_config["format"]["schema"] if structured else next(
            t for t in tools if t["name"] == "submit")["input_schema"]
        assert all(t.get("strict") for t in tools or []) and schema.get("additionalProperties") is False
        self.seen.append((system, messages[0]["content"], schema))
        tool_results = [b for m in messages if m["role"] == "user" and isinstance(m["content"], list)
                        for b in m["content"] if b.get("type") == "tool_result"]
        if structured or tool_results:
            props = schema["properties"]
            if "recommendation" in props:
                if self.lead_fails:
                    raise RuntimeError("Lead down")
                options = props["recommendation"]["enum"]
                ans = {"recommendation": "alternative" if "alternative" in options else "reject",
                       "reason": "Violation recall is the top priority. The alternative keeps the pilot date."}
            elif "effort_min_days" in props:
                data = json.dumps([json.loads(b["content"]) for b in tool_results])
                conflict = ["p-pilot"] if "Domain Agent" in system and "pilot" in data.lower() else []
                ans = {"effort_min_days": 1, "effort_max_days": 2, "verdict": "conflict" if conflict else "works",
                       "message": "Assessed from tools.", "conflicts": conflict,
                       "evidence": ["engineer/change-history.md › May 2026"]}
                if self.propose_alternative:
                    ans["alternative"] = {"label": "Post-processing overlap rule", "effort_days": 0.5}
            elif "spec" in props:
                f = lambda v: {"value": v, "source": "Client brief.pdf"}  # noqa: E731
                ans = {"spec": {"goal": f("Triage patient messages"), "success_metric": f("100% emergencies escalated"),
                                "priorities": f(["safety", "speed"]), "constraints": f(["< 2 min"]),
                                "deadline": f("4 weeks"), "stakeholders": f(["Head nurse"])},
                       "gaps": [{"id": "emergency-list", "question": "Which symptoms?", "suggested": "Chest pain"}]}
            else:
                ans = {"answer": "Only a helmet worn on the head counts.", "cited": [1], "confident": True}
            if structured:
                return NS(content=[NS(type="text", text=json.dumps(ans))], stop_reason="end_turn")
            return NS(content=[NS(type="tool_use", id="t-submit", name="submit", input=ans)], stop_reason="tool_use")
        blocks = [NS(type="tool_use", id=f"t{i}", name=n, input={"query": "similar past change actual effort"} if n == "search_knowledge" else {})
                  for i, n in enumerate(sorted(names - {"submit"}))]
        return NS(content=blocks or [NS(type="text", text="thinking")], stop_reason="tool_use" if blocks else "end_turn")


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
    # Lead Agent runs once, after the team agents, and its recommendation lands on the card
    assert len(fake.lead_calls()) == 1 and fake.seen[-1] == fake.lead_calls()[0]
    assert new["recommendation"] == "alternative" and new["recommendation_mode"] == "live"
    assert "top priority" in new["recommendation_reason"]


def test_agents_use_their_prompts_and_get_the_objective_spec(fake):
    from app import prompts
    card = c.get("/api/inbox/ds").json()[0]
    c.post(f"/api/proposals/{card['id']}/rerun")
    systems = {s for s, _, _ in fake.seen}
    assert {prompts.DS_AGENT, prompts.ENGINEER_AGENT, prompts.DOMAIN_AGENT, prompts.LEAD_AGENT} <= systems
    for _, task, _ in fake.seen:  # every team and lead call carries the priorities, in order
        assert "Priorities (most important first):\n  1. violation recall\n  2. false alerts\n  3. speed" in task
    lead_task = fake.lead_calls()[0][1]
    assert "p-pilot" in lead_task and "Team assessments:" in lead_task and "risk high" in lead_task


def test_lead_cannot_pick_a_missing_alternative(fake):
    fake.propose_alternative = False
    new = c.post("/api/products/ppe/proposals",
                 json={"node_id": "edge", "custom_text": "Move inference to a cloud GPU", "role": "engineer"}).json()
    assert new["alternative"] is None
    assert fake.lead_calls()[0][2]["properties"]["recommendation"]["enum"] == ["approve", "reject"]
    assert new["recommendation"] in ("approve", "reject")


def test_lead_failure_keeps_team_answers_and_rule_based_recommendation(fake):
    fake.lead_fails = True
    card = c.get("/api/inbox/ds").json()[0]
    new = c.post(f"/api/proposals/{card['id']}/rerun").json()
    assert new["mode"] == "live" and len(new["responses"]) == 3
    assert new["recommendation"] == "alternative" and new["recommendation_mode"] == "demo"


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


def test_live_ask_and_domain_agent():
    a = c.post("/api/products/ppe/ask", json={"question": "does a helmet in the hand count", "agent": "domain"}).json()
    assert a["mode"] == "live" and a["sources"] and not a["escalated"]


def test_live_chat_uses_each_agents_persona(fake):
    from app import prompts
    for agent in ("lead", "ds", "engineer", "domain", "project"):
        a = c.post("/api/products/ppe/ask", json={"question": "helmet rule and pilot date", "agent": agent}).json()
        assert a["mode"] == "live" and a["agent"] == agent
        assert fake.seen[-1][0] == prompts.CHAT_AGENTS[agent]


def test_live_limit_per_session(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "LIVE_LIMIT", 1)
    c.post("/api/reset")
    first = c.post("/api/products/ppe/proposals", json={"node_id": "edge", "custom_text": "A", "role": "engineer"}).json()
    second = c.post("/api/products/ppe/proposals", json={"node_id": "edge", "custom_text": "B", "role": "engineer"}).json()
    assert first["mode"] == "live" and second["mode"] == "demo"
    assert "limit" in second["fallback_reason"]
