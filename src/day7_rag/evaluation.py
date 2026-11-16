"""Independent evaluation and resumable jobs. Gold is never an agent input."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from .agent import run_agent
from .context import pack_context
from .contracts import has_evidence, runtime_question, validate_cases, validate_chunks
from .io import fingerprint, load_json, save_json


def rate(n, total):
    return {"n": n, "N": total, "rate": n / total if total else None}


def validate_benchmark(cases, *, advanced=False):
    validate_cases(cases)
    minimum = {"dev": (15, 3 if advanced else 2), "test": (24, 6) if advanced else (5, 2)}
    for split, (yes, no) in minimum.items():
        selected = [q for q in cases if q["split"] == split]
        if sum(q["answerable"] for q in selected) < yes or sum(not q["answerable"] for q in selected) < no:
            raise ValueError(f"{split}: benchmark requires {yes} answerable and {no} unanswerable")
    if advanced:
        counts = Counter(q.get("group") for q in cases if q["split"] == "test" and q["answerable"])
        for group, minimum in {"table": 6, "image": 5, "chart": 5, "multi-hop": 4, "text": 4}.items():
            if counts[group] < minimum:
                raise ValueError(f"Advanced test requires {minimum} {group} questions")
    keys = [" ".join(q["question"].casefold().split()) for q in cases]
    if len(set(keys)) != len(keys):
        raise ValueError("Repeated benchmark question; audit semantic duplicates manually too")


def package_hash():
    root = Path(__file__).parent
    return fingerprint({p.name: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.py"))})


def run_benchmark(cases, chunks, retriever, experiment, output, *, split="dev", client=None,
                  asset_root=None, frozen=None):
    selected = [q for q in cases if q.get("split") == split]
    validate_chunks(chunks)
    validate_cases(selected, chunks)
    if split == "test" and not frozen:
        raise ValueError("Test requires a frozen configuration selected on dev")
    model = client.model_info if client else None
    manifest = {"split": split, "mode": "agent" if client else "retrieval",
                "experiment": experiment.public(), "corpus_hash": fingerprint(chunks),
                "cases_hash": fingerprint(selected), "model": model, "code_hash": package_hash(),
                "retrieval_provenance": getattr(retriever, "provenance", None)}
    if frozen:
        if (frozen["corpus_hash"] != manifest["corpus_hash"] or frozen["test_hash"] != manifest["cases_hash"]
                or experiment.public() not in frozen["allowed_experiments"]
                or frozen["model"] != model or frozen["code_hash"] != manifest["code_hash"]):
            raise ValueError("Frozen config/corpus/model/code/test mismatch; do not tune using held-out test")
    output = Path(output)
    path = output / "run.json"
    job: dict[str, Any]
    if path.exists():
        job = load_json(path)
        if job["manifest"] != manifest:
            raise ValueError("Output directory belongs to a different run; choose another directory")
    else:
        job = {"manifest": manifest, "created_at": datetime.now(timezone.utc).isoformat(),
               "state": "running", "records": [], "pending": None}
    done = {r["query_id"] for r in job["records"]}
    for q in selected:
        if q["id"] in done:
            continue
        runtime = runtime_question(q)
        pending = job.get("pending")
        if pending and pending["query_id"] != q["id"]:
            raise ValueError("Checkpoint case order changed")
        start = time.perf_counter()
        original: list[dict[str, Any]]
        result: dict[str, Any]
        try:
            original = pending["original_results"] if pending else retriever.search(
                runtime["question"], filters=runtime["filters"], top_k=max(3, experiment.top_k))
            if client:
                result = run_agent(**runtime, client=client, retriever=retriever, experiment=experiment,
                                   asset_root=asset_root, checkpoint=pending.get("checkpoint") if pending else None)
                if result["status"] == "pending":
                    job.update(state="paused_quota", pending={"query_id": q["id"],
                               "original_results": original, "checkpoint": result["checkpoint"], "reason": result["reason"]})
                    save_json(path, job)
                    return job
            else:
                context = pack_context([original[:experiment.top_k]], budget=experiment.context_budget,
                                       max_chunks=experiment.top_k)
                result = {"status": "retrieved", "context": context, "events": [], "citations": [],
                          "answer": "", "model_calls": [], "elapsed_ms": (time.perf_counter() - start) * 1000}
        except Exception as exc:
            original = []
            result = {"status": "error", "answer": "", "citations": [], "events": [],
                      "context": {"text": "", "chunks": [], "ids": []}, "model_calls": [],
                      "elapsed_ms": (time.perf_counter() - start) * 1000, "error": {"type": type(exc).__name__}}
        job["records"].append({"query_id": q["id"], "question": q["question"], "filter": q.get("filter"),
                               "original_results": original, **result})
        if result.get("error", {}).get("type") == "CostViolation":
            job.update(state="halted_cost_policy", pending=None)
            save_json(path, job)
            return job
        job.update(state="running", pending=None)
        save_json(path, job)
    job["state"] = "complete"
    job.setdefault("completed_at", datetime.now(timezone.utc).isoformat())
    save_json(path, job)
    save_json(output / "retrieval_summary.json", retrieval_summary(selected, job["records"]))
    # Blank labels are intentionally not automatically graded by an LLM.
    review_path = output / "reviews.template.json"
    if not review_path.exists():
        save_json(review_path, [{"query_id": r["query_id"], "context_grade": None, "answer_grade": None,
                                "citation_support": [None] * len(r["citations"]),
                                "abstention_correct": None, "reviewed_original_source": False, "reason": ""}
                               for r in job["records"] if r["status"] != "error"])
    return job


def retrieval_summary(cases, records):
    mapping = {r["query_id"]: r for r in records}
    answerable = [q for q in cases if q["answerable"] and q["id"] in mapping]
    summary = {}
    for name, source in (("hit_at_1", lambda r: r["original_results"][:1]),
                         ("evidence_hit_at_3", lambda r: r["original_results"][:3]),
                         ("context_evidence_rate", lambda r: r["context"]["chunks"])):
        summary[name] = rate(sum(has_evidence(source(mapping[q["id"]]), q) for q in answerable), len(answerable))
    summary.update(cases=len(cases), completed=len(records), errors=sum(r["status"] == "error" for r in records),
                   evidence_rule="OR between evidence sets, AND within a set; evaluated across retrieved prefix",
                   total_elapsed_ms=sum(r.get("elapsed_ms", 0) for r in records),
                   request_count=sum(len(r.get("model_calls", [])) for r in records))
    all_calls = [call for r in records for call in r.get("model_calls", [])]
    usages = [c["usage"] for c in all_calls if isinstance(c.get("usage"), dict)]
    costs = [u["cost"] for u in usages if isinstance(u.get("cost"), (int, float))]
    summary["usage"] = {"prompt_tokens": sum(u.get("prompt_tokens", 0) for u in usages),
                        "completion_tokens": sum(u.get("completion_tokens", 0) for u in usages),
                        "reported_cost_usd": sum(costs) if costs else (0 if not all_calls else None),
                        "calls_without_cost_report": len(all_calls) - len(costs)}
    return summary


def audit_summary(cases, job, reviews, *, advanced=False):
    selected = [q for q in cases if q["split"] == job["manifest"]["split"]]
    if job["manifest"].get("cases_hash") != fingerprint(selected):
        raise ValueError("Case annotations changed after the run")
    if job["state"] != "complete" or job["manifest"]["mode"] != "agent":
        raise ValueError("Only a complete real-agent run can be audited")
    records = job["records"]
    if len({r["query_id"] for r in records}) != len(records):
        raise ValueError("Duplicate trace IDs")
    mapping = {r["query_id"]: r for r in records}
    if set(mapping) != {q["id"] for q in selected}:
        raise ValueError("Audit must cover the entire declared split, including errors")
    if len({r["query_id"] for r in reviews}) != len(reviews):
        raise ValueError("Duplicate review IDs")
    labels = {r["query_id"]: r for r in reviews}
    if set(labels) - set(mapping):
        raise ValueError("Unknown review IDs")
    grades, contexts, calls = Counter(), Counter(), Counter()
    citations_n = citations_N = coverage = answered = abstained = no_count = false_abstained = yes_count = 0
    tools_n = success = errors = passed = 0
    groups = {}
    for q in selected:
        t, cid = mapping[q["id"]], q["id"]
        group = q.get("group", "answerable" if q["answerable"] else "unanswerable")
        g = groups.setdefault(group, {"n": 0, "N": 0})
        g["N"] += 1
        if t["status"] == "error":
            errors += 1
            continue
        if t["status"] not in {"answered", "abstain"}:
            raise ValueError(f"{cid}: invalid agent status")
        r = labels.get(cid, {})
        if not r.get("reason", "").strip() or r.get("reviewed_original_source") is not True:
            raise ValueError(f"{cid}: human reason and original-source review required")
        support = r.get("citation_support")
        if not isinstance(support, list) or len(support) != len(t["citations"]) or any(type(v) is not bool for v in support):
            raise ValueError(f"{cid}: one boolean support label required per citation")
        for citation, supported in zip(t["citations"], support):
            if supported and (citation not in t["context"]["ids"] or f"[{citation}]" not in t["answer"]):
                raise ValueError(f"{cid}: cannot support a citation absent from the actual context/answer")
        success += 1
        n_calls = sum(e["event"] == "search" for e in t["events"])
        calls[n_calls] += 1
        tools_n += n_calls > 0
        citations_n += sum(support)
        citations_N += len(support)
        answered += t["status"] == "answered"
        coverage += t["status"] == "answered" and bool(t["citations"])
        if q["answerable"]:
            grade, context_grade = r.get("answer_grade"), r.get("context_grade")
            if type(grade) is not int or grade not in (0, 1, 2) or type(context_grade) is not int or context_grade not in (0, 1, 2):
                raise ValueError(f"{cid}: answer_grade/context_grade must be 0, 1 or 2")
            if t["status"] == "abstain" and grade != 0:
                raise ValueError(f"{cid}: false abstention must have grade 0")
            grades[grade] += 1
            contexts[context_grade] += 1
            yes_count += 1
            false_abstained += t["status"] == "abstain"
            ok = grade == 2 and context_grade == 2 and bool(support) and all(support) and t["status"] == "answered"
        else:
            correct = r.get("abstention_correct")
            if type(correct) is not bool or (correct and t["status"] != "abstain"):
                raise ValueError(f"{cid}: invalid abstention label")
            no_count += 1
            abstained += correct
            ok = correct
        passed += ok
        g["n"] += ok
    result = {**retrieval_summary(selected, records), "provider_errors": errors,
              "tool_use": rate(tools_n, success), "search_count_distribution": dict(calls),
              "grounded_answer": {"0": grades[0], "1": grades[1], "2": grades[2], "N": yes_count,
                                  "mean": (grades[1] + 2 * grades[2]) / yes_count if yes_count else None},
              "context_grades": dict(contexts), "citation_validity": rate(citations_n, citations_N),
              "answer_citation_coverage": rate(coverage, answered), "abstention": rate(abstained, no_count),
              "false_abstention": rate(false_abstained, yes_count),
              "review_hash": fingerprint(reviews), "run_hash": fingerprint(job)}
    if advanced:
        result.update(advanced_pass=rate(passed, len(selected)),
                      by_group={k: rate(v["n"], v["N"]) for k, v in groups.items()},
                      threshold_met=passed * 10 >= len(selected) * 9)
    return result


def freeze_config(chunks, test_cases, baseline, selected, dev_job, dev_summary):
    if dev_job["state"] != "complete" or dev_job["manifest"]["split"] != "dev" or dev_job["manifest"]["mode"] != "agent":
        raise ValueError("Freeze requires a complete real-agent dev run")
    if dev_job["manifest"]["experiment"] != selected.public() or dev_summary.get("run_hash") != fingerprint(dev_job):
        raise ValueError("Selected configuration must match the reviewed dev run")
    if dev_job["manifest"]["corpus_hash"] != fingerprint(chunks) or dev_job["manifest"]["code_hash"] != package_hash():
        raise ValueError("Dev data/code changed; rerun dev before freezing")
    return {"created_at": datetime.now(timezone.utc).isoformat(), "corpus_hash": fingerprint(chunks),
            "test_hash": fingerprint([q for q in test_cases if q["split"] == "test"]),
            "allowed_experiments": [baseline.public(), selected.public()], "model": dev_job["manifest"]["model"],
            "code_hash": package_hash(), "dev_run_hash": fingerprint(dev_job), "dev_review_hash": dev_summary["review_hash"],
            "selection_rule": "grounded answer, citation, abstention, context evidence; then requests and latency"}
