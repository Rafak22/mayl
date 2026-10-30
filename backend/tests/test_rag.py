from app import rag
from app.rag import AGENT_SCOPES, Chunk, Retriever


def sources(hits):
    return [h["source"] for h in hits]


def test_meaning_match_without_shared_keywords():
    # No word of the query appears in the chunk: only the embeddings can connect them.
    hits = Retriever("fraud").search("relatives sending money", AGENT_SCOPES["domain"], k=4)
    assert "domain/regional-payment-patterns.md › Family transfers" in sources(hits)
    # It is the closest chunk by meaning (keyword hits on "money" rank other chunks higher in the fused list).
    _, (_, best) = max(rag._vector_static(rag.embed_query("relatives sending money"), "fraud", ["domain", "shared"], 10))
    assert rag._db().execute("SELECT source FROM chunks_fts WHERE rowid = ?", (best,)).fetchone()[0].endswith("Family transfers")


def test_arabic_query():
    hits = Retriever("support").search("العميل يهدد بتقديم شكوى للجهات الرسمية", AGENT_SCOPES["domain"])
    assert hits[0]["source"] == "domain/dialect-guide.md › Escalation words"


def test_scopes_filter():
    r = Retriever("fraud")
    for q in ("family transfers", "compliance explainability reasons", "عائلة تحويل", "latency hardware GPU"):
        assert not any(s.startswith("domain/") for s in sources(r.search(q, AGENT_SCOPES["engineer"], k=10)))
    assert all(s.startswith("domain/") for s in sources(r.search("family transfers", ("domain",), k=10)))


def test_products_are_isolated():
    assert not any("dialect" in s for s in sources(Retriever("fraud").search("Gulf dialect tickets", None, k=10)))


def test_live_chunks_are_merged_and_scoped():
    live = [Chunk("Domain Expert Agent: decided to whitelist payroll batches", "activity › now", "live")]
    assert "activity › now" in sources(Retriever("fraud", live).search("payroll batches", AGENT_SCOPES["ds"]))
    assert "activity › now" not in sources(Retriever("fraud", live).search("payroll batches", ("ds",), k=10))


def test_unrelated_query_finds_nothing():
    assert Retriever("fraud").search("pizza recipe with mozzarella") == []


def test_index_is_up_to_date():
    stored = dict(rag._db().execute("SELECT key, value FROM meta"))
    assert stored["fingerprint"] == rag.fingerprint(rag.knowledge_chunks()), \
        "knowledge/ changed: run python scripts/build_index.py and commit data/mayl.db"
