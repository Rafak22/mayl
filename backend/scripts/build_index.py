"""Build data/mayl.db from knowledge/<product>/<scope>/*.md.

Run from backend/ after editing any knowledge file, then commit the db:

    python scripts/build_index.py

The server only reads the db; it never rebuilds it.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag import DB_PATH, DIM, MODEL_FILE, MODEL_NAME, connect, embed_passages, fingerprint, knowledge_chunks  # noqa: E402

SCHEMA = f"""
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text, chunk_id UNINDEXED, product UNINDEXED, scope UNINDEXED, source UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
CREATE VIRTUAL TABLE chunks_vec USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    product TEXT PARTITION KEY,
    scope TEXT,
    embedding FLOAT[{DIM}] distance_metric=cosine,
    chunk_size = 64  -- default 1024 preallocates ~1.5 MB per product
);
"""


def main():
    rows = knowledge_chunks()
    print(f"{len(rows)} chunks from {len({p for p, _ in rows})} products; embedding with {MODEL_NAME}...")
    vectors = embed_passages([c.text for _, c in rows])

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = connect(tmp, readonly=False)
    conn.executescript(SCHEMA)
    for chunk_id, ((product, c), vec) in enumerate(zip(rows, vectors), 1):
        conn.execute("INSERT INTO chunks_fts (rowid, text, chunk_id, product, scope, source) VALUES (?, ?, ?, ?, ?, ?)",
                     (chunk_id, c.text, chunk_id, product, c.scope, c.source))
        conn.execute("INSERT INTO chunks_vec (chunk_id, product, scope, embedding) VALUES (?, ?, ?, ?)",
                     (chunk_id, product, c.scope, vec.tobytes()))
    conn.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("model", MODEL_NAME), ("model_file", MODEL_FILE), ("dim", str(DIM)), ("fingerprint", fingerprint(rows))])
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    os.replace(tmp, DB_PATH)
    print(f"Wrote {DB_PATH} ({DB_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
