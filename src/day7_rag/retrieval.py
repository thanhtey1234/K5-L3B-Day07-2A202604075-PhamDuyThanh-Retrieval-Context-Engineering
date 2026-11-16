import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any


def tokenize(text):
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


def matches_filter(chunk, filters):
    direct = {"document_id": "source_id", "source_id": "source_id", "page": "page", "source": "source"}
    for key, value in (filters or {}).items():
        if value is None:
            continue
        actual = chunk.get(direct[key]) if key in direct else chunk["metadata"].get(key)
        if actual != value or isinstance(actual, bool) != isinstance(value, bool):
            return False
    return True


class BM25:
    def __init__(self, chunks, *, k1=1.5, b=0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.counts = [Counter(tokenize(c["text"])) for c in chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(len(chunks), 1) or 1
        df = Counter(term for row in self.counts for term in row)
        self.idf = {t: math.log(1 + (len(chunks) - n + .5) / (n + .5)) for t, n in df.items()}

    def search(self, query, *, filters=None, top_k=3):
        terms = set(tokenize(query))
        results: list[dict[str, Any]] = []
        for c, tf, length in zip(self.chunks, self.counts, self.lengths):
            if not matches_filter(c, filters):
                continue
            score = sum(self.idf.get(t, 0) * (tf[t] * (self.k1 + 1)) /
                        (tf[t] + self.k1 * (1 - self.b + self.b * length / self.average))
                        for t in terms if tf[t])
            if score > 0:
                results.append({**c, "score": score, "method": "bm25"})
        ranked = sorted(results, key=lambda c: (-c["score"], c["id"]))[:top_k]
        return [{**c, "rank": i} for i, c in enumerate(ranked, 1)]


def rrf(rankings, *, k=60, top_k=None):
    """Fuse ranks, not incompatible raw scores; expose contributing ranks."""
    scores, chunks, provenance = defaultdict(float), {}, {}
    for name, ranking in rankings:
        seen = set()
        for rank, c in enumerate(ranking, 1):
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            scores[c["id"]] += 1 / (k + rank)
            chunks[c["id"]] = c
            provenance.setdefault(c["id"], {})[name] = {"rank": rank, "score": c.get("score")}
    ids = sorted(chunks, key=lambda cid: (-scores[cid], cid))
    if top_k is not None:
        ids = ids[:top_k]
    return [{**chunks[cid], "score": scores[cid], "rank": i, "method": "hybrid",
             "contributions": provenance[cid]} for i, cid in enumerate(ids, 1)]


class Retrieval:
    def __init__(self, chunks, experiment, dense=None):
        self.chunks, self.experiment, self.dense = chunks, experiment, dense
        self.provenance: dict[str, Any] | None = None
        self.lexical = BM25(chunks)

    def search(self, query, *, filters=None, top_k=None):
        e = self.experiment
        if filters is not None and not isinstance(filters, dict):
            raise ValueError("filters must be an object")
        for key, value in (filters or {}).items():
            if value is not None and type(value) not in (str, int, float, bool):
                raise ValueError("Filter values must be scalar JSON values")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Filter numbers must be finite")
            if key == "page" and value is not None and (type(value) is not int or value < 1):
                raise ValueError("Page filter must be a positive integer")
        for key in (filters or {}):
            if key not in {"document_id", "source_id", "source", "page"} and not any(key in c["metadata"] for c in self.chunks):
                raise ValueError(f"Filter field is absent from the corpus export: {key}")
        top_k = e.top_k if top_k is None else top_k
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if e.method == "bm25":
            return self.lexical.search(query, filters=filters, top_k=top_k)
        if self.dense is None:
            raise ValueError("Dense/hybrid requires a configured PostgreSQL vector index")
        if e.method == "dense":
            return self.dense.search(query, filters=filters, top_k=top_k)
        return rrf([
            ("dense", self.dense.search(query, filters=filters, top_k=e.candidate_k)),
            ("bm25", self.lexical.search(query, filters=filters, top_k=e.candidate_k)),
        ], k=e.rrf_k, top_k=top_k)
