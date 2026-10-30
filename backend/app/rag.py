"""Per-agent RAG: hybrid search (keyword + vector) on SQLite.

Each agent searches its own knowledge base plus the shared project memory:

  knowledge/<product>/shared/    meetings, briefs, decisions   (all agents)
  knowledge/<product>/ds/        data docs, experiment logs     (DS Agent)
  knowledge/<product>/engineer/  contracts, change history      (AI Engineer Agent)
  knowledge/<product>/domain/    domain guidelines, rules       (Domain Expert Agent)

The knowledge base is indexed ahead of time by `scripts/build_index.py` into one
SQLite file (data/mayl.db): an FTS5 table for keyword search (BM25) and a
sqlite-vec table for vector search. Embeddings come from
intfloat/multilingual-e5-small (int8 ONNX on CPU via onnxruntime, sentencepiece
tokenizer, no PyTorch), so Arabic and English queries match by meaning, not
only by shared words.

Live project activity (proposals, decisions, rules, graph nodes) changes at
runtime, so it stays in memory and is searched the same two ways at query
time. Keyword and vector rankings are merged with Reciprocal Rank Fusion.
"""
import hashlib
import math
import os
import re
import sqlite3
import threading
from collections import Counter, OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parent.parent
KB_ROOT = BACKEND / "knowledge"
DB_PATH = Path(os.getenv("MAYL_DB", BACKEND / "data" / "mayl.db"))
SCOPES = ("shared", "ds", "engineer", "domain")

MODEL_NAME = "intfloat/multilingual-e5-small"
MODEL_FILE = "onnx/model_qint8_avx512_vnni.onnx"  # 113 MB int8; the fp32 export is 448 MB
SPM_FILE = "onnx/sentencepiece.bpe.model"
DIM = 384
RRF_K = 60  # standard RRF constant
CANDIDATES = 20  # per ranking, before fusion
MIN_SIMILARITY = 0.80  # e5 cosine below this is treated as unrelated

TOKEN = re.compile(r"\w+", re.UNICODE)
STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on", "with", "be",
        "by", "at", "it", "this", "that", "as", "from", "we", "our", "should", "must", "not", "why",
        "what", "how", "did", "do", "does", "can", "will", "was", "were", "has", "have",
        "في", "من", "على", "عن", "الى", "إلى", "ما", "هل", "او", "أو", "مع", "هذا", "هذه"}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass
class Chunk:
    text: str
    source: str  # e.g. "domain/compliance-rules.md › Explainability"
    scope: str  # shared | ds | engineer | domain | live


def chunk_file(path: Path, scope: str) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    chunks = []
    for part in re.split(r"\n(?=## )", raw):
        lines = part.strip().splitlines()
        if not lines:
            continue
        heading = lines[0].lstrip("# ").strip()
        body = "\n".join(lines[1:]).strip()
        if not body:  # title-only section
            continue
        chunks.append(Chunk(text=f"{heading}: {body}", source=f"{scope}/{path.name} › {heading}", scope=scope))
    return chunks


def knowledge_chunks() -> list[tuple[str, Chunk]]:
    """Every (product, chunk) in knowledge/, in a stable order. Row i gets chunk_id i + 1."""
    out = []
    for product_dir in sorted(p for p in KB_ROOT.iterdir() if p.is_dir()):
        for scope in SCOPES:
            for f in sorted((product_dir / scope).glob("*.md")):
                out.extend((product_dir.name, c) for c in chunk_file(f, scope))
    return out


def fingerprint(rows: list[tuple[str, Chunk]]) -> str:
    """Changes whenever the knowledge files or the model change; stored in the db to detect a stale index."""
    h = hashlib.sha256(f"{MODEL_NAME}|{MODEL_FILE}".encode())
    for product, c in rows:
        h.update(f"\x00{product}\x00{c.scope}\x00{c.source}\x00{c.text}".encode())
    return h.hexdigest()


# --- embeddings ------------------------------------------------------------
class Embedder:
    """multilingual-e5-small on onnxruntime, tokenized with the model's own sentencepiece file.

    Gives the same token ids and vectors as fastembed did for a single text (mean pooling, then
    L2 norm), but the 5 MB sentencepiece model replaces tokenizer.json, which the `tokenizers`
    library holds as ~250 MB of RAM for XLM-R's 250k-token vocabulary.
    """
    MAX_TOKENS = 512  # model_max_length in the model's tokenizer_config.json, special tokens included

    def __init__(self, cache_dir: str):
        import onnxruntime as ort
        import sentencepiece as spm
        from huggingface_hub import hf_hub_download

        onnx_path, sp_path = (hf_hub_download(MODEL_NAME, f, cache_dir=cache_dir) for f in (MODEL_FILE, SPM_FILE))
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.enable_cpu_mem_arena = False  # return batch buffers instead of keeping them (~95 MB less, same speed)
        self.session = ort.InferenceSession(onnx_path, sess_options=so, providers=["CPUExecutionProvider"])
        proto = Path(sp_path).read_bytes()  # bytes: sentencepiece's file loader fails on non-ASCII paths on Windows
        self.sp = spm.SentencePieceProcessor(model_proto=proto)
        self.normalizer = spm.SentencePieceNormalizer(model_proto=proto, remove_extra_whitespaces=False)

    def token_ids(self, text: str) -> list[int]:
        # XLM-R ids: <s>=0, <pad>=1, </s>=2, <unk>=3; every other sentencepiece id is shifted by one.
        pieces = [i + 1 if i else 3 for i in self.sp.encode(text)]
        if self.normalizer.normalize(text).endswith(" "):
            pieces.append(6)  # tokenizer.json keeps a lone "▁" for trailing whitespace; sentencepiece drops it
        return [0, *pieces[:self.MAX_TOKENS - 2], 2]

    def embed(self, texts: list[str]) -> np.ndarray:
        """One text per run: the int8 model quantizes activations per batch, so texts sharing a batch
        (and its padding) would shift each other's vectors."""
        out = np.zeros((len(texts), DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            ids = np.array([self.token_ids(text)], dtype=np.int64)
            hidden = self.session.run(None, {"input_ids": ids, "attention_mask": np.ones_like(ids),
                                             "token_type_ids": np.zeros_like(ids)})[0][0]
            pooled = np.sum(hidden, axis=0, dtype=np.float64) / len(hidden)
            out[row] = pooled / max(np.linalg.norm(pooled), 1e-12)
        return out


@lru_cache(maxsize=1)
def model() -> Embedder:
    """Loaded once per process; the first call downloads ~118 MB to the cache dir. Uses ~150 MB of RAM."""
    return Embedder(os.getenv("MODEL_CACHE_PATH", str(BACKEND / ".cache" / "models")))


def embed_passages(texts: list[str]) -> np.ndarray:
    return model().embed([f"passage: {t}" for t in texts])


def embed_query(text: str) -> np.ndarray:
    return model().embed([f"query: {text}"])[0]


_LIVE_VECTORS: "OrderedDict[str, np.ndarray]" = OrderedDict()  # live text -> vector, shared across requests
_LIVE_VECTORS_LOCK = threading.Lock()
_LIVE_VECTORS_MAX = 4096


def _live_vectors(texts: list[str]) -> np.ndarray:
    """Activity repeats across requests, so each live text is embedded only once."""
    with _LIVE_VECTORS_LOCK:
        vecs = {t: _LIVE_VECTORS[t] for t in texts if t in _LIVE_VECTORS}
    missing = [t for t in dict.fromkeys(texts) if t not in vecs]
    vecs.update(zip(missing, embed_passages(missing)))  # embed outside the lock
    with _LIVE_VECTORS_LOCK:
        for t in texts:
            _LIVE_VECTORS[t] = vecs[t]
            _LIVE_VECTORS.move_to_end(t)
        while len(_LIVE_VECTORS) > _LIVE_VECTORS_MAX:
            _LIVE_VECTORS.popitem(last=False)
    return np.stack([vecs[t] for t in texts]) if texts else np.zeros((0, DIM), dtype=np.float32)


# --- database --------------------------------------------------------------
def connect(path: Path = DB_PATH, readonly: bool = True) -> sqlite3.Connection:
    import sqlite_vec

    if readonly and not path.exists():
        raise FileNotFoundError(f"{path} is missing. Build it with: python scripts/build_index.py")
    uri = f"{path.resolve().as_uri()}?mode=ro" if readonly else str(path)
    conn = sqlite3.connect(uri, uri=readonly, check_same_thread=False)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


_local = threading.local()  # one read-only connection per thread (agents run in parallel)


def _db() -> sqlite3.Connection:
    if getattr(_local, "conn", None) is None:
        _local.conn = connect()
    return _local.conn


def _keyword_static(query_tokens, product, scopes, n) -> list[int]:
    match = " OR ".join(f'"{t}"' for t in query_tokens)
    marks = ",".join("?" * len(scopes))
    rows = _db().execute(
        f"SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? AND product = ? AND scope IN ({marks}) "
        f"ORDER BY bm25(chunks_fts) LIMIT ?", (match, product, *scopes, n)).fetchall()
    return [r[0] for r in rows]


def _vector_static(qvec, product, scopes, n) -> list[tuple[float, tuple]]:
    out = []
    for scope in scopes:  # vec0 metadata filters take equality, so one KNN per scope
        out += [(1 - d, ("db", cid)) for cid, d in _db().execute(
            "SELECT chunk_id, distance FROM chunks_vec WHERE embedding MATCH ? AND k = ? AND product = ? AND scope = ?",
            (qvec.tobytes(), n, product, scope))]
    return out


def _bm25(query_tokens, docs: list[list[str]], k1=1.5, b=0.75) -> list[float]:
    """Okapi BM25 for the handful of in-memory live chunks."""
    if not docs:
        return []
    avg = sum(map(len, docs)) / len(docs) or 1
    df = Counter(t for d in docs for t in set(d))
    scores = []
    for d in docs:
        tf = Counter(d)
        scores.append(sum(
            math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * (k1 + 1)
            / (tf[t] + k1 * (1 - b + b * len(d) / avg))
            for t in query_tokens if t in tf))
    return scores


EXTRA_KNOWLEDGE: dict[str, Path] = {}  # product id -> knowledge dir, for products outside data/mayl.db


def register_knowledge_dir(product_id: str, path: Path) -> None:
    """Search `path/<scope>/*.md` for this product, in memory (used by eval-only products)."""
    EXTRA_KNOWLEDGE[product_id] = Path(path)
    _extra_chunks.cache_clear()


@lru_cache(maxsize=8)
def _extra_chunks(product_id: str) -> tuple[Chunk, ...]:
    root = EXTRA_KNOWLEDGE.get(product_id)
    if not root:
        return ()
    return tuple(c for scope in SCOPES for f in sorted((root / scope).glob("*.md")) for c in chunk_file(f, scope))


class Retriever:
    def __init__(self, product_id: str, live_docs: list[Chunk] | None = None):
        self.product_id = product_id
        # Searched in memory: an override knowledge dir's chunks (real scopes) + live project memory (scope "live").
        self.live = list(_extra_chunks(product_id)) + list(live_docs or [])
        self._live_tokens = [tokenize(c.text) for c in self.live]
        self._live_vecs = None
        self._lock = threading.Lock()

    def _live_matrix(self) -> np.ndarray:
        with self._lock:  # one Retriever is shared by the parallel team agents
            if self._live_vecs is None:
                self._live_vecs = _live_vectors([c.text for c in self.live])
            return self._live_vecs

    def search(self, query: str, scopes: tuple[str, ...] | None = None, k: int = 4,
               min_similarity: float = MIN_SIMILARITY) -> list[dict]:
        """min_similarity=0 keeps every vector candidate: use it when an agent judges relevance itself."""
        q = tokenize(query)
        if not q:
            return []
        static_scopes = [s for s in (scopes or SCOPES) if s in SCOPES]
        mem = [i for i, c in enumerate(self.live) if not scopes or c.scope in scopes]  # in-memory chunks in scope
        qvec = embed_query(query)

        # Each ranking is a list of keys: ("db", chunk_id) or ("live", index into self.live).
        rankings = []
        if static_scopes:
            rankings.append([("db", cid) for cid in _keyword_static(q, self.product_id, static_scopes, CANDIDATES)])
        vectors = _vector_static(qvec, self.product_id, static_scopes, CANDIDATES) if static_scopes else []
        if mem:
            kw = _bm25(q, [self._live_tokens[i] for i in mem])
            order = sorted(range(len(mem)), key=lambda j: -kw[j])
            rankings.append([("live", mem[j]) for j in order[:CANDIDATES] if kw[j] > 0])
            sims = self._live_matrix()[mem] @ qvec  # vectors are normalized: dot product = cosine
            vectors += [(float(s), ("live", i)) for i, s in zip(mem, sims)]
        # Same model, same cosine: static and live vector hits rank together.
        vectors = sorted((v for v in vectors if v[0] >= min_similarity), key=lambda v: -v[0])
        rankings.append([key for _, key in vectors[:CANDIDATES]])

        # Reciprocal Rank Fusion, scaled so rank 1 in one ranking = 1.0 and rank 1 in both = 2.0.
        fused: dict[tuple, float] = {}
        for ranking in rankings:
            for rank, key in enumerate(ranking, 1):
                fused[key] = fused.get(key, 0.0) + (RRF_K + 1) / (RRF_K + rank)
        top = sorted(fused.items(), key=lambda x: -x[1])[:k]

        ids = [cid for (kind, cid), _ in top if kind == "db"]
        rows = {}
        if ids:
            marks = ",".join("?" * len(ids))
            rows = {cid: (source, text) for cid, source, text in _db().execute(
                f"SELECT rowid, source, text FROM chunks_fts WHERE rowid IN ({marks})", ids)}
        out = []
        for (kind, key), score in top:
            source, text = rows[key] if kind == "db" else (self.live[key].source, self.live[key].text)
            out.append({"text": text, "source": source, "score": round(score, 2)})
        return out


AGENT_SCOPES = {
    "ds": ("ds", "shared", "live"),
    "engineer": ("engineer", "shared", "live"),
    "domain": ("domain", "shared", "live"),
    "lead": ("shared", "ds", "engineer", "domain", "live"),
}


CHAT_LOG_KINDS = ("answer", "escalation")  # chat Q&A log lines: retrieving them would echo old questions back


def live_chunks(product: dict, activity: list[dict]) -> list[Chunk]:
    docs = [Chunk(f"{a['actor']}: {a['text']}", f"activity › {a['at'][:16].replace('T', ' ')}", "live")
            for a in activity if a.get("kind") not in CHAT_LOG_KINDS]
    docs += [Chunk(f"Rule: {r['text']}", f"rules › {r['source']}", "live") for r in product.get("rules", [])]
    docs += [Chunk(f"{n['label']}: {n['description']}", f"project graph › {n['id']}", "live")
             for n in product.get("nodes", [])]
    return docs
