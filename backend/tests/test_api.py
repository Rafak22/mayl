from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def setup_function():
    c.post("/api/reset")


def test_products_listed():
    ps = c.get("/api/products").json()
    assert {p["id"] for p in ps} == {"chatbot", "ppe", "triage"}
    assert {p["id"]: p["pending"] for p in ps} == {"chatbot": 0, "ppe": 1, "triage": 0}


def test_bottleneck_card_has_conflict_and_alternative():
    card = c.get("/api/inbox/ds").json()[0]
    assert card["product_id"] == "ppe" and card["risk"] == "high"
    assert card["conflicts"][0]["id"] == "p-pilot"
    assert card["alternative"]["effort_days"] == 1
    eng = next(r for r in card["responses"] if r["team"] == "engineer")
    assert "Compliance logic" in eng["message"]


def test_engineer_change_reaches_data_scientists():
    card = c.post("/api/products/ppe/proposals",
                  json={"node_id": "edge", "custom_text": "Replace edge boxes with a cloud GPU", "role": "engineer"}).json()
    assert "model" in card["affected"]
    assert "ds" in {r["team"] for r in card["responses"]}
    assert card["status"] == "pending"


def test_low_risk_auto_approved():
    card = c.post("/api/products/chatbot/proposals",
                  json={"node_id": "channels", "custom_text": "Rename a button", "role": "engineer"}).json()
    assert card["status"] == "auto_approved"


def test_decide_alternative_resolves_bottleneck():
    card = c.get("/api/inbox/ds").json()[0]
    r = c.post(f"/api/proposals/{card['id']}/decide", json={"role": "ds", "decision": "alternative"})
    assert r.json()["status"] == "approved_alternative"
    p = c.get("/api/products/ppe").json()
    assert p["state"] == "resolved" and p["metrics"]["violation_recall"] == 0.94


def test_from_scratch_flow():
    spec = c.post("/api/products/triage/intake").json()
    assert len(spec["gaps"]) == 2 and spec["spec"]["goal"]["source"] == "Client brief.pdf"
    out = c.post("/api/products/triage/confirm", json={"answers": {}}).json()
    assert out["handoff"]["approvers"] == ["engineer"]
    p = c.get("/api/products/triage").json()
    assert len(p["nodes"]) == 8 and p["state"] == "handoff"
    assert len(c.get("/api/inbox/engineer").json()) == 2


def test_ask():
    a = c.post("/api/products/ppe/ask", json={"question": "helmet carried in the hand"}).json()
    assert "helmet" in a["answer"].lower()


def test_expert_twin_arabic():
    a = c.post("/api/products/chatbot/ask", json={"question": "شكوى رسمية", "agent": "domain"}).json()
    assert a["sources"] and not a["escalated"]


def test_sessions_are_isolated():
    a = {"X-Session": "judge-a"}
    card = c.get("/api/inbox/ds", headers=a).json()[0]
    c.post(f"/api/proposals/{card['id']}/decide", json={"role": "ds", "decision": "approve"}, headers=a)
    assert c.get("/api/products/ppe", headers=a).json()["state"] == "resolved"
    assert c.get("/api/products/ppe", headers={"X-Session": "judge-b"}).json()["state"] == "bottleneck"
