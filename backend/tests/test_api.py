from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def setup_function():
    c.post("/api/reset")


def test_products_listed():
    ps = c.get("/api/products").json()
    assert {p["id"] for p in ps} == {"support", "fraud", "heart"}
    assert next(p for p in ps if p["id"] == "fraud")["pending"] == 1


def test_bottleneck_card_has_conflict_and_alternative():
    card = c.get("/api/inbox/ds").json()[0]
    assert card["risk"] == "high"
    assert card["conflicts"][0]["id"] == "p-large"
    assert card["alternative"]["effort_days"] == 0.5
    eng = next(r for r in card["responses"] if r["team"] == "engineer")
    assert "Scoring service" in eng["message"]


def test_engineer_change_reaches_data_scientists():
    card = c.post("/api/products/fraud/proposals",
                  json={"node_id": "hw", "custom_text": "Move serving to CPU", "role": "engineer"}).json()
    assert "model" in card["affected"]
    assert "ds" in {r["team"] for r in card["responses"]}
    assert card["status"] == "pending"


def test_low_risk_auto_approved():
    card = c.post("/api/products/support/proposals",
                  json={"node_id": "ui", "custom_text": "Rename a label", "role": "engineer"}).json()
    assert card["status"] == "auto_approved"


def test_decide_alternative_resolves_bottleneck():
    card = c.get("/api/inbox/ds").json()[0]
    r = c.post(f"/api/proposals/{card['id']}/decide", json={"role": "ds", "decision": "alternative"})
    assert r.json()["status"] == "approved_alternative"
    assert c.get("/api/products/fraud").json()["state"] == "resolved"


def test_from_scratch_flow():
    spec = c.post("/api/products/heart/intake").json()
    assert len(spec["gaps"]) == 2
    out = c.post("/api/products/heart/confirm", json={"answers": {}}).json()
    assert out["handoff"]["approvers"] == ["engineer"]
    assert len(c.get("/api/products/heart").json()["nodes"]) == 7
    assert len(c.get("/api/inbox/engineer").json()) == 2


def test_ask():
    a = c.post("/api/products/fraud/ask", json={"question": "why family transfers"}).json()
    assert "family" in a["answer"].lower()


def test_sessions_are_isolated():
    a = {"X-Session": "judge-a"}
    card = c.get("/api/inbox/ds", headers=a).json()[0]
    c.post(f"/api/proposals/{card['id']}/decide", json={"role": "ds", "decision": "approve"}, headers=a)
    assert c.get("/api/products/fraud", headers=a).json()["state"] == "resolved"
    assert c.get("/api/products/fraud", headers={"X-Session": "judge-b"}).json()["state"] == "bottleneck"
