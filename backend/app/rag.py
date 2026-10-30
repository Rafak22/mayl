"""Per-agent RAG.

Each agent searches its own knowledge base plus the shared project memory:

  knowledge/<product>/shared/    meetings, briefs, decisions   (all agents)
  knowledge/<product>/ds/        data docs, experiment logs     (DS Agent)
  knowledge/<product>/engineer/  contracts, change history      (AI Engineer Agent)
  knowledge/<product>/domain/    domain guidelines, rules       (Domain Expert Agent)

Live project activity (proposals, decisions) is added to shared memory at
query time, so agents always see the latest state.

Retrieval is BM25 over section-sized chunks: no model download, no GPU, works
on free hosting and handles Arabic text. The `Retriever` interface lets us
swap in embeddings (e.g. ChromaDB) without touching the agents.
"""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi

KB_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
TOKEN = re.compile(r"\w+", re.UNICODE)
STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on", "with", "be",
        "by", "at", "it", "this", "that", "as", "from", "we", "our", "should", "must", "not", "why",
        "what", "how", "did", "do", "does", "can", "will", "was", "were", "has", "have"}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass
class Chunk:
    text: str
    source: str  # e.g. "domain/compliance-rules.md › Explainability"
    scope: str  # shared | ds | engineer | domain | live


def _chunk_file(path: Path, scope: str) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    title = raw.splitlines()[0].lstrip("# ").strip() if raw else path.stem
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


@lru_cache(maxsize=32)
def load_static(product_id: str) -> tuple[Chunk, ...]:
    out = []
    base = KB_ROOT / product_id
    for scope in ("shared", "ds", "engineer", "domain"):
        for f in sorted((base / scope).glob("*.md")):
            out.extend(_chunk_file(f, scope))
    return tuple(out)


class Retriever:
    def __init__(self, product_id: str, live_docs: list[Chunk] | None = None):
        self.chunks = list(load_static(product_id)) + list(live_docs or [])

    def search(self, query: str, scopes: tuple[str, ...] | None = None, k: int = 4) -> list[dict]:
        pool = [c for c in self.chunks if not scopes or c.scope in scopes]
        q = tokenize(query)
        if not pool or not q:
            return []
        bm = BM25Okapi([tokenize(c.text) for c in pool])
        scores = bm.get_scores(q)
        ranked = sorted(zip(scores, pool), key=lambda x: -x[0])
        return [{"text": c.text, "source": c.source, "score": round(float(s), 2)}
                for s, c in ranked[:k] if s > 0]


AGENT_SCOPES = {
    "ds": ("ds", "shared", "live"),
    "engineer": ("engineer", "shared", "live"),
    "domain": ("domain", "shared", "live"),
    "lead": ("shared", "ds", "engineer", "domain", "live"),
}


def live_chunks(product: dict, activity: list[dict]) -> list[Chunk]:
    docs = [Chunk(f"{a['actor']}: {a['text']}", f"activity › {a['at'][:16].replace('T', ' ')}", "live")
            for a in activity]
    docs += [Chunk(f"Rule: {r['text']}", f"rules › {r['source']}", "live") for r in product.get("rules", [])]
    docs += [Chunk(f"{n['label']}: {n['description']}", f"project graph › {n['id']}", "live")
             for n in product.get("nodes", [])]
    return docs
