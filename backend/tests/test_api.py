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


def test_demo_recommendation_on_bottleneck():
    card = c.get("/api/inbox/ds").json()[0]
    assert card["recommendation"] == "alternative" and card["recommendation_mode"] == "demo"
    assert "violation recall" in card["recommendation_reason"]


def test_demo_recommendation_rules():
    from app.agents import recommend
    product = {"objective": {"priorities": ["patient safety", "speed"]}}
    rule = {"id": "r1", "text": "Never miss an emergency", "source": "nurse"}
    alt = {"label": "Cheaper", "effort_days": 1}
    assert recommend(product, "conflict", "high", [rule], alt, 8)[0] == "alternative"
    assert recommend(product, "conflict", "high", [rule], None, 8)[0] == "reject"
    assert recommend(product, "works_with_changes", "high", [], None, 14)[0] == "reject"
    assert recommend(product, "works_with_changes", "medium", [], None, 4)[0] == "approve"
    assert "patient safety" in recommend(product, "works", "low", [], None, 1)[1]


def test_engineer_change_reaches_data_scientists():
    card = c.post("/api/products/ppe/proposals",
                  json={"node_id": "edge", "custom_text": "Replace edge boxes with a cloud GPU", "role": "engineer"}).json()
    assert "model" in card["affected"]
    assert "ds" in {r["team"] for r in card["responses"]}
    assert card["status"] == "pending"


def test_low_risk_auto_approved():
    card = c.post("/api/products/chatbot/proposals",
                  json={"node_id": "channels", "custom_text": "Rename a button", "role": "engineer"}).json()
    assert card["status"] == "auto_approved" and card["recommendation"] == "approve"


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


def test_products_carry_goals_and_steps():
    ppe = next(p for p in c.get("/api/products").json() if p["id"] == "ppe")
    assert ppe["metric_goals"]["violation_recall"] == {"label": "Violation recall", "goal": 0.95, "better": "higher", "unit": "%"}
    assert [s["short"] for s in ppe["steps"]][:3] == ["Images", "Labels", "Model"]
    assert ppe["client"] == "Binaa Contracting"


def test_activity_names_the_agent_for_every_review():
    act = c.get("/api/products/ppe").json()["activity"]
    reviews = [a for a in act if a["kind"] == "review"]
    assert {a["agent"] for a in reviews} == {"ds", "engineer", "domain"}
    assert {a["actor"] for a in reviews} == {"DS Agent", "Engineer Agent", "Domain Agent"}
    assert act[0]["kind"] == "recommendation" and act[0]["agent"] == "lead"
    human = next(a for a in act if a["kind"] == "proposal")
    assert human["agent"] is None and human["actor"] == "Domain Expert"


def test_stats_are_counted_from_proposals_and_activity():
    s = c.get("/api/stats").json()
    assert s["changes_reviewed"] == 1 and s["changes_reviewed_today"] == 1 and s["conflicts_caught"] == 1
    assert s["avg_review_seconds"] is not None
    assert s["agents"]["ds"]["reviews"] == 1 and s["agents"]["lead"]["recommendations"] == 1
    c.post("/api/products/chatbot/ask", json={"question": "pizza recipe with mozzarella", "agent": "domain"})
    card = c.get("/api/inbox/ds").json()[0]
    c.post(f"/api/proposals/{card['id']}/decide", json={"role": "ds", "decision": "alternative"})
    s = c.get("/api/stats").json()
    assert s["agents"]["domain"]["answers"] == 1 and s["agents"]["domain"]["escalations"] == 1
    assert s["agents"]["lead"]["accepted"] == {"followed": 1, "decided": 1}  # the Lead recommended the alternative
    assert s["latest"][0]["kind"] == "decision" and s["latest"][0]["product_id"] == "ppe"


def test_details_and_sample_images():
    d = c.get("/api/products/ppe/details").json()
    assert len(d["examples"]["items"]) == 3
    img = c.get(d["examples"]["items"][1]["image"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert {doc["agent"] for doc in d["documents"]} == {"ds", "engineer", "domain", None}
    assert any(s["heading"] == "Helmet rule" for doc in d["documents"] for s in doc["sections"])
    chat = c.get("/api/products/chatbot/details").json()
    assert chat["samples"]["rows"][0]["question"] and len(chat["samples"]["rows"]) == 10
    tri = c.get("/api/products/triage/details").json()
    assert tri["solution"] is None and tri["solution_pending"] and len(tri["samples"]["rows"]) == 20


def test_chat_with_each_agent_uses_its_own_scope():
    for agent in ("lead", "ds", "engineer", "domain", "project"):
        a = c.post("/api/products/ppe/ask", json={"question": "helmet rule latency dataset", "agent": agent}).json()
        assert a["agent"] == agent and a["sources"]
        if agent in ("ds", "engineer", "domain"):  # never another team's documents
            others = {"ds", "engineer", "domain"} - {agent}
            assert not any(s["source"].split("/")[0] in others for s in a["sources"])
    assert c.post("/api/products/ppe/ask", json={"question": "x", "agent": "expert"}).status_code == 400


def test_chat_log_lines_are_not_retrieved():
    q = "zebra crossing paint colour"
    c.post("/api/products/ppe/ask", json={"question": q, "agent": "domain"})
    a = c.post("/api/products/ppe/ask", json={"question": q, "agent": "domain"}).json()
    assert not any(s["source"].startswith("activity") for s in a["sources"])


def test_sessions_are_isolated():
    a = {"X-Session": "judge-a"}
    card = c.get("/api/inbox/ds", headers=a).json()[0]
    c.post(f"/api/proposals/{card['id']}/decide", json={"role": "ds", "decision": "approve"}, headers=a)
    assert c.get("/api/products/ppe", headers=a).json()["state"] == "resolved"
    assert c.get("/api/products/ppe", headers={"X-Session": "judge-b"}).json()["state"] == "bottleneck"


def test_results_tab_reads_saved_eval_runs():
    r = c.get("/api/products/ppe/eval").json()
    splits = {s["split"]: s for s in r["splits"]}
    assert set(splits) == {"dev", "heldout"}
    cr = next(k for k in splits["heldout"]["kinds"] if k["kind"] == "change_review")
    assert cr["cases"] > 0 and 0 <= cr["pass_rate"] <= 1 and cr["run"]["report"]
    for f in splits["heldout"]["failed"]:  # only this project's cases, explained in plain words
        assert "-ppe-" in f["id"] and f["text"] and not any("[" in x for x in f["reasons"])
    assert c.get("/api/products/nope/eval").status_code == 404
