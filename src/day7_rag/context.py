"""Refreshable context with explicit, conservative reference-token accounting."""

from .retrieval import rrf

BUDGET_UNIT = "utf8_bytes_token_upper_bound"


def token_upper_bound(text):
    # UTF-8 byte count bounds ordinary byte-fallback text tokens conservatively.
    # Actual model prompt tokens (including framing/images) are recorded by API usage.
    return len(text.encode("utf-8"))


def pack_context(rankings, *, budget=3000, max_chunks=6):
    # Recent round wins a tie. Ranks are fused across rounds instead of comparing
    # BM25/cosine scores; old context never permanently monopolizes the budget.
    fused = rrf([(f"round-{i}", r) for i, r in reversed(list(enumerate(rankings)))])
    latest = {c["id"]: c for ranking in rankings for c in ranking}
    recency = {c["id"]: i for i, rows in enumerate(rankings) for c in rows}
    fused.sort(key=lambda c: (-c["score"], -recency[c["id"]], c["id"]))
    blocks, selected = [], []
    for fused_row in fused:
        c = {**latest[fused_row["id"]], "context_score": fused_row["score"]}
        location = f"[{c['id']}] {c['source']} | PDF page {c['page']}"
        if c.get("bbox"):
            location += f" | bbox={c['bbox']}"
        block = location + "\n" + c["text"]
        if token_upper_bound("\n\n".join([*blocks, block])) <= budget:
            blocks.append(block)
            selected.append(c)
        if len(selected) == max_chunks:
            break
    text = "\n\n".join(blocks)
    return {"text": text, "chunks": selected, "ids": [c["id"] for c in selected],
            "budget": budget, "budget_unit": BUDGET_UNIT, "used": token_upper_bound(text)}
