"""Read-only Day 6 access and separately versioned Day 7 indexes."""

import json
import math

from .contracts import validate_chunks
from .io import fingerprint


def connect(url, *, readonly=False):
    import psycopg
    if not url:
        raise ValueError("DATABASE_URL chưa được cấu hình")
    return psycopg.connect(url, connect_timeout=10,
                           options="-c default_transaction_read_only=on" if readonly else "")


def filter_sql(filters):
    clauses, params = [], []
    direct = {"source_id": "document_id", "document_id": "document_id", "source": "source", "page": "page"}
    for key, value in (filters or {}).items():
        if value is None:
            continue
        if key in direct:
            clauses.append(f"{direct[key]} = %s")
            params.append(value)
        else:
            clauses.append("metadata @> %s::jsonb")
            params.append(json.dumps({key: value}, ensure_ascii=False))
    return clauses, params


def rows_to_chunks(rows):
    return [{"id": r[0], "source_id": r[1], "source": r[2], "page": r[3], "text": r[4],
             "metadata": r[5], **(r[5].get("day7", {})),
             **({"score": float(r[6])} if len(r) > 6 else {})} for r in rows]


class PgRetriever:
    def __init__(self, database_url, embedder, *, strategy="strategy_b", index_id=None):
        self.url, self.embedder, self.strategy, self.index_id = database_url, embedder, strategy, index_id
        self.dimensions = embedder.dimensions if embedder else None

    def _scope(self):
        if self.index_id:
            return "rag_day7.chunks", "index_id = %s", self.index_id
        return "public.chunks", "strategy = %s", self.strategy

    def inspect(self):
        table, condition, value = self._scope()
        with connect(self.url, readonly=True) as conn:
            if self.index_id:
                row = conn.execute("SELECT manifest FROM rag_day7.indexes WHERE index_id = %s", (self.index_id,)).fetchone()
                if not row:
                    raise ValueError("Day 7 index not found")
                manifest = row[0]
                if self.embedder and manifest["embedding"] != self.embedder.identity:
                    raise ValueError("Embedding model/revision/config does not match index")
            else:
                manifest = {"strategy": self.strategy, "model_verification": "Day 6 model identity supplied by operator"}
            rows = conn.execute(f"SELECT count(*), min(vector_dims(embedding)), max(vector_dims(embedding)) "
                                f"FROM {table} WHERE {condition}", (value,)).fetchone()
            if not rows[0]:
                raise ValueError("Index is empty; check DAY6_STRATEGY or build the Day 7 index")
            if rows[1] != rows[2] or (self.dimensions and rows[1] != self.dimensions):
                raise ValueError("Embedding dimension mismatch")
        return {**manifest, "chunk_count": rows[0], "dimensions": rows[1]}

    def load_chunks(self):
        table, condition, value = self._scope()
        with connect(self.url, readonly=True) as conn:
            rows = conn.execute(f"SELECT chunk_id, document_id, source, page, text, metadata "
                                f"FROM {table} WHERE {condition} ORDER BY chunk_id", (value,)).fetchall()
        chunks = rows_to_chunks(rows)
        validate_chunks(chunks)
        return chunks

    def search(self, query, *, filters=None, top_k=3):
        if not self.embedder:
            raise ValueError("Dense search requires a real embedder")
        vector = self.embedder.query(query)
        if len(vector) != self.dimensions or not all(math.isfinite(v) for v in vector):
            raise ValueError("Invalid query vector")
        table, condition, value = self._scope()
        clauses, params = filter_sql(filters)
        where = " AND ".join([condition, *clauses])
        with connect(self.url, readonly=True) as conn:
            rows = conn.execute(
                f"SELECT chunk_id, document_id, source, page, text, metadata, "
                f"1 - (embedding <=> %s::vector) AS score FROM {table} WHERE {where} "
                "ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s",
                (str(vector), value, *params, str(vector), top_k),
            ).fetchall()
        return [{**c, "method": "dense", "rank": rank} for rank, c in enumerate(rows_to_chunks(rows), 1)]


def build_index(database_url, chunks, embedder, *, corpus_manifest=None):
    """An immutable index version; never modifies public.chunks."""
    validate_chunks(chunks)
    manifest = {"corpus_hash": fingerprint(chunks), "embedding": embedder.identity,
                "source": corpus_manifest or {}, "chunk_count": len(chunks)}
    index_id = fingerprint(manifest)[:24]
    with connect(database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("CREATE SCHEMA IF NOT EXISTS rag_day7")
        conn.execute("CREATE TABLE IF NOT EXISTS rag_day7.indexes (index_id TEXT PRIMARY KEY, manifest JSONB NOT NULL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS rag_day7.chunks (
            index_id TEXT REFERENCES rag_day7.indexes(index_id), chunk_id TEXT, document_id TEXT NOT NULL,
            source TEXT NOT NULL, page INTEGER NOT NULL, text TEXT NOT NULL, metadata JSONB NOT NULL,
            embedding vector NOT NULL, PRIMARY KEY (index_id, chunk_id))""")
        exists = conn.execute("SELECT 1 FROM rag_day7.indexes WHERE index_id = %s", (index_id,)).fetchone()
        if exists:
            return index_id, manifest
    # Download/encode outside the database transaction. Caches survive interruption.
    vectors = embedder.encode([c["text"] for c in chunks])
    with connect(database_url) as conn:
        conn.execute("INSERT INTO rag_day7.indexes VALUES (%s, %s::jsonb) ON CONFLICT DO NOTHING",
                     (index_id, json.dumps(manifest)))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO rag_day7.chunks VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::vector)
                ON CONFLICT (index_id,chunk_id) DO NOTHING""", [(
                    index_id, c["id"], c["source_id"], c["source"], c["page"], c["text"],
                    json.dumps({**c["metadata"], "day7": {k: c[k] for k in
                               ("content_type", "bbox", "image", "pdf", "page_image") if k in c}}), str(v)
                ) for c, v in zip(chunks, vectors)])
    return index_id, manifest
