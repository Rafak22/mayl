import numpy as np

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


def test_token_ids_match_xlmr_tokenizer():
    # Expected ids come from the model's tokenizer.json (HF `tokenizers`), which the sentencepiece path replaces.
    expected = {
        "query: relatives sending money": [0, 41, 1294, 12, 35845, 7, 135834, 17265, 2],
        "passage: شكوى رسمية": [0, 46692, 12, 72453, 34208, 74023, 250, 2],
        "hello ": [0, 33600, 31, 6, 2],  # trailing whitespace keeps a lone "▁"
        "end.\n": [0, 3564, 5, 6, 2],
        " ": [0, 6, 2],
        "": [0, 2],
    }
    for text, ids in expected.items():
        assert rag.model().token_ids(text) == ids, repr(text)
    assert len(rag.model().token_ids("word " * 700)) == 512


def test_stored_vectors_match_runtime_embeddings():
    """The index and live queries must be embedded the same way (one text per run)."""
    texts = [c.text for _, c in rag.knowledge_chunks()]
    stored = [np.frombuffer(v, dtype=np.float32) for (v,) in
              rag._db().execute("SELECT embedding FROM chunks_vec ORDER BY chunk_id")]
    assert np.array_equal(np.stack(stored), rag.embed_passages(texts))


def test_knowledge_dir_override_for_eval_products():
    rag.register_knowledge_dir("retail-test", rag.BACKEND / "eval" / "knowledge" / "retail")
    r = Retriever("retail-test")
    hits = r.search("when must the nightly batch finish", AGENT_SCOPES["engineer"])
    assert hits and hits[0]["source"].startswith("engineer/batch-contract.md")
    assert not any(s.startswith("domain/") for s in sources(r.search("staple bread milk minimum", AGENT_SCOPES["engineer"], k=10)))
    assert not any("batch-contract" in s for s in sources(Retriever("ppe").search("nightly batch window", None, k=10)))


def test_index_is_up_to_date():
    stored = dict(rag._db().execute("SELECT key, value FROM meta"))
    assert stored["fingerprint"] == rag.fingerprint(rag.knowledge_chunks()), \
        "knowledge/ changed: run python scripts/build_index.py and commit data/mayl.db"
