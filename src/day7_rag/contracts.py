"""Runtime data is deliberately separated from evaluator-only annotations."""

import math
import unicodedata


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def validate_chunks(chunks):
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Corpus must be a nonempty JSON array")
    seen = set()
    for c in chunks:
        if not isinstance(c, dict):
            raise ValueError("Chunk must be an object")
        for k in ("id", "text", "source_id", "source"):
            if not isinstance(c.get(k), str) or not c[k].strip():
                raise ValueError(f"Chunk missing nonempty {k}")
        if c["id"] in seen or any(s in c["id"] for s in "[]\n\r"):
            raise ValueError("Chunk ID must be unique and citation-safe")
        seen.add(c["id"])
        if type(c.get("page")) is not int or c["page"] < 1:
            raise ValueError("page must be a positive physical page number")
        if not isinstance(c.get("metadata"), dict):
            raise ValueError("metadata must be an object")
        bbox = c.get("bbox")
        if bbox is not None and (
            not isinstance(bbox, list) or len(bbox) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in bbox)
            or not (0 <= bbox[0] < bbox[2] and 0 <= bbox[1] < bbox[3])
        ):
            raise ValueError("bbox must be [x0,y0,x1,y1] in PDF points, top-left origin")


def evidence_sets(case):
    """OR between sets; AND within a set. Legacy gold entries are alternatives."""
    return case.get("evidence_sets") or [[g] for g in case.get("gold", [])]


def evidence_matches(chunk, evidence):
    if chunk["source_id"] != evidence["source_id"] or chunk["page"] != evidence["page"]:
        return False
    if evidence.get("region_id") and evidence["region_id"] != chunk["id"]:
        return False
    quote = evidence.get("evidence", "")
    return bool(quote and normalize(quote) in normalize(chunk["text"]))


def has_evidence(chunks, case):
    return any(all(any(evidence_matches(c, e) for c in chunks) for e in group)
               for group in evidence_sets(case))


def validate_cases(cases, chunks=None):
    if not isinstance(cases, list) or not cases:
        raise ValueError("Cases must be a nonempty JSON array")
    seen = set()
    for q in cases:
        if not isinstance(q.get("id"), str) or not q["id"] or q["id"] in seen:
            raise ValueError("Case IDs must be unique nonempty strings")
        seen.add(q["id"])
        if q.get("split") not in {"dev", "test"} or not isinstance(q.get("question"), str) or not q["question"].strip():
            raise ValueError(f"{q['id']}: invalid split/question")
        if type(q.get("answerable")) is not bool:
            raise ValueError(f"{q['id']}: answerable boolean required")
        if not q["answerable"]:
            if not q.get("absence_reason"):
                raise ValueError(f"{q['id']}: absence_reason required")
            continue
        if not q.get("expected_answer") or not evidence_sets(q):
            raise ValueError(f"{q['id']}: expected answer and evidence required")
        for group in evidence_sets(q):
            if not isinstance(group, list) or not group:
                raise ValueError("Evidence sets must not be empty")
            for e in group:
                if not e.get("source_id") or type(e.get("page")) is not int or not e.get("evidence"):
                    raise ValueError(f"{q['id']}: invalid evidence")
                if chunks is not None and not any(evidence_matches(c, e) for c in chunks):
                    raise ValueError(f"{q['id']}: evidence not found in corpus: page {e['page']}")


def runtime_question(case):
    """An allowlist, never dict(case): labels cannot reach model/retrieval."""
    return {"question": case["question"], "filters": case.get("filter")}
