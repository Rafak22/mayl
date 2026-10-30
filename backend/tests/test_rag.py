from app import rag
from app.rag import AGENT_SCOPES, Chunk, Retriever

HELMET_RULE = "domain/site-safety-rules.md › Helmet rule"
HANDOVER = "domain/service-guidelines.md › Must hand over to a human"


def sources(hits):
    return [h["source"] for h in hits]


def test_helmet_on_belt_finds_helmet_rule():
    hits = Retriever("ppe").search("helmet hanging from a worker's belt", AGENT_SCOPES["domain"])
    assert hits[0]["source"] == HELMET_RULE


def test_arabic_query():
    hits = Retriever("chatbot").search("شكوى رسمية", AGENT_SCOPES["domain"])
    assert hits[0]["source"] == HANDOVER


def test_scopes_filter():
    for product, queries in {
        "ppe": ("helmet rule violation", "false alerts per camera", "خوذة العامل", "latency GPU camera stream"),
        "chatbot": ("شكوى رسمية", "hand over to a human", "Gulf dialect", "response time contract"),
    }.items():
        r = Retriever(product)
        for q in queries:
            assert not any(s.startswith("domain/") for s in sources(r.search(q, AGENT_SCOPES["engineer"], k=10))), q
    assert all(s.startswith("domain/") for s in sources(Retriever("ppe").search("helmet", ("domain",), k=10)))


def test_products_are_isolated():
    assert not any("service-guidelines" in s for s in sources(Retriever("ppe").search("Gulf dialect customers", None, k=10)))


def test_live_chunks_are_merged_and_scoped():
    live = [Chunk("Domain Expert Agent: decided to exempt welding booths", "activity › now", "live")]
    assert "activity › now" in sources(Retriever("ppe", live).search("welding booths", AGENT_SCOPES["ds"]))
    assert "activity › now" not in sources(Retriever("ppe", live).search("welding booths", ("ds",), k=10))


def test_unrelated_query_finds_nothing():
    for product in ("chatbot", "ppe", "triage"):
        assert Retriever(product).search("pizza recipe with mozzarella") == [], product


def test_index_is_up_to_date():
    stored = dict(rag._db().execute("SELECT key, value FROM meta"))
    assert stored["fingerprint"] == rag.fingerprint(rag.knowledge_chunks()), \
        "knowledge/ changed: run python scripts/build_index.py and commit data/mayl.db"
