"""Explicit AI source review, separate from the existing human-review workflow.

The assistant supplies source-grounded semantic labels. This program validates
and aggregates them; it does not infer support merely from an ID or keyword.
It lives outside the inference package so adding a reviewer cannot change the
runtime hash or require spending the remaining quota re-running unchanged dev.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day7_rag.config import Experiment
from day7_rag.evaluation import package_hash, rate, retrieval_summary
from day7_rag.io import file_hash, fingerprint, load_json, save_json


MODE = "ai_source_review_not_human_verified"


def summarize(cases, job, labels, source_hash):
    selected = [q for q in cases if q["split"] == job["manifest"]["split"]]
    if job["state"] != "complete" or job["manifest"]["mode"] != "agent":
        raise ValueError("AI review requires a complete real-agent run")
    if job["manifest"]["cases_hash"] != fingerprint(selected):
        raise ValueError("Case annotations changed after inference")
    records = {r["query_id"]: r for r in job["records"]}
    reviews = {r["query_id"]: r for r in labels}
    expected = {q["id"] for q in selected}
    if len(records) != len(job["records"]) or set(records) != expected:
        raise ValueError("Records must cover the entire split without duplicates")
    eligible = {qid for qid, r in records.items() if r["status"] != "error"}
    if len(reviews) != len(labels) or set(reviews) != eligible:
        raise ValueError("AI labels must cover every non-error record exactly once")
    grades, contexts = Counter(), Counter()
    supported = citations = answered = grounded = refusals = false_refusals = errors = 0
    answerable_n = unanswerable_n = passed = 0
    for case in selected:
        qid = case["id"]
        record = records[qid]
        if record["status"] == "error":
            errors += 1
            answerable_n += int(case["answerable"])
            unanswerable_n += int(not case["answerable"])
            continue
        label = reviews[qid]
        if (label.get("reviewer_type") != "ai" or label.get("reviewed_original_source") is not False
                or label.get("ai_reviewed_source") is not True or not label.get("reviewer")
                or label.get("source_pdf_sha256") != source_hash or not label.get("reason", "").strip()
                or not label.get("source_pages")):
            raise ValueError(f"{qid}: explicit AI provenance, source checksum/pages and reason required")
        supports = label.get("citation_support")
        if (not isinstance(supports, list) or len(supports) != len(record["citations"])
                or any(type(s) is not bool for s in supports)):
            raise ValueError(f"{qid}: one boolean support label per citation required")
        for cid, support in zip(record["citations"], supports):
            if support and (cid not in record["context"]["ids"] or f"[{cid}]" not in record["answer"]):
                raise ValueError(f"{qid}: a supported citation must be in the actual context and answer")
        if record["status"] not in {"answered", "abstain"}:
            raise ValueError(f"{qid}: unexpected final status")
        supported += sum(supports)
        citations += len(supports)
        answered += record["status"] == "answered"
        if case["answerable"]:
            answerable_n += 1
            grade, context = label.get("answer_grade"), label.get("context_grade")
            if any(type(g) is not int or g not in {0, 1, 2} for g in (grade, context)):
                raise ValueError(f"{qid}: answer/context grades must be 0, 1 or 2")
            if record["status"] == "abstain" and grade != 0:
                raise ValueError(f"{qid}: false abstention must receive answer grade 0")
            grades[grade] += 1
            contexts[context] += 1
            false_refusals += record["status"] == "abstain"
            ok = record["status"] == "answered" and grade == context == 2 and bool(supports) and all(supports)
            grounded += ok
        else:
            unanswerable_n += 1
            correct = label.get("abstention_correct")
            if type(correct) is not bool or (correct and record["status"] != "abstain"):
                raise ValueError(f"{qid}: inconsistent abstention label")
            refusals += correct
            ok = correct
        passed += ok
    return {**retrieval_summary(selected, job["records"]), "evaluation_mode": MODE,
            "human_verified": False, "provisional": True, "source_pdf_sha256": source_hash,
            "review_hash": fingerprint(labels), "run_hash": fingerprint(job),
            "reviewer_code_sha256": file_hash(__file__), "provider_errors": errors,
            "answer_grades": {str(i): grades[i] for i in range(3)},
            "answer_mean": sum(g * n for g, n in grades.items()) / answerable_n if answerable_n else None,
            "context_grades": {str(i): contexts[i] for i in range(3)},
            "grounded_complete": rate(grounded, answerable_n),
            "citation_validity": rate(supported, citations), "abstention": rate(refusals, unanswerable_n),
            "false_abstention": rate(false_refusals, answerable_n), "answered": answered,
            "overall_pass": rate(passed, len(selected)),
            "limitations": "AI semantic/source review requested by user; not independent human grading or a course score."}


def freeze(chunks, test_cases, baseline, candidate, jobs, summaries, source_hash):
    if len(jobs) != 2 or len(summaries) != 2:
        raise ValueError("Compare reviewed baseline and candidate on dev before test")
    for config, job, summary in zip((baseline, candidate), jobs, summaries):
        if (job["state"] != "complete" or job["manifest"]["split"] != "dev"
                or job["manifest"]["mode"] != "agent" or job["manifest"]["experiment"] != config.public()
                or job["manifest"]["code_hash"] != package_hash()
                or job["manifest"]["corpus_hash"] != fingerprint(chunks)
                or summary.get("evaluation_mode") != MODE or summary.get("human_verified") is not False
                or summary.get("run_hash") != fingerprint(job)
                or summary.get("source_pdf_sha256") != source_hash
                or summary.get("reviewer_code_sha256") != file_hash(__file__)):
            raise ValueError("Dev runtime/config/corpus/review/source provenance mismatch")
    if any(jobs[0]["manifest"][key] != jobs[1]["manifest"][key] for key in ("model", "cases_hash")):
        raise ValueError("Baseline and candidate must use the same model and dev cases")

    def quality(summary):
        return (summary["grounded_complete"]["n"], summary["citation_validity"]["rate"] or 0,
                summary["abstention"]["n"], summary["context_grades"]["2"],
                -summary["request_count"], -summary["total_elapsed_ms"])

    index = max(range(2), key=lambda i: quality(summaries[i]))
    configs = (baseline, candidate)
    return {"created_at": datetime.now(timezone.utc).isoformat(), "evaluation_mode": MODE,
            "human_verified": False, "source_pdf_sha256": source_hash,
            "corpus_hash": fingerprint(chunks), "code_hash": package_hash(),
            "test_hash": fingerprint([q for q in test_cases if q["split"] == "test"]),
            "allowed_experiments": [baseline.public(), configs[index].public()],
            "model": jobs[index]["manifest"]["model"], "selected_experiment": configs[index].public(),
            "dev_run_hash": fingerprint(jobs[index]), "dev_review_hash": summaries[index]["review_hash"],
            "reviewer_code_sha256": file_hash(__file__),
            "dev_comparison": [{"experiment": c.name, "quality": list(quality(s))} for c, s in zip(configs, summaries)],
            "selection_rule": "AI-reviewed dev grounded completeness, citation, abstention, context; then requests/latency"}


def report(paths):
    lines = ["# Đánh giá tự động có đối chiếu nguồn", "",
             "**Nhãn do AI chấm theo yêu cầu người dùng; chưa được con người xác minh đầy đủ. Không phải điểm môn học.**", "",
             "| Cấu hình | Split | Grounded đầy đủ | Citation hỗ trợ | Từ chối đúng | Từ chối sai | Request |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for path in paths:
        job = load_json(path / "run.json")
        summary = load_json(path / "audit_summary.ai.json")
        if summary["run_hash"] != fingerprint(job) or summary["evaluation_mode"] != MODE:
            raise ValueError("Stale or non-AI summary")
        def display(value):
            return f"{value['n']}/{value['N']}" if value["N"] else "Không áp dụng"
        lines.append(f"| {job['manifest']['experiment']['name']} | {job['manifest']['split']} | "
                     f"{display(summary['grounded_complete'])} | {display(summary['citation_validity'])} | "
                     f"{display(summary['abstention'])} | {display(summary['false_abstention'])} | {summary['request_count']} |")
    lines.extend(["", "Grounded đầy đủ yêu cầu: đáp án và context đều 2/2, có citation và mọi citation hỗ trợ đúng. "
                  "Câu có đáp án nhưng agent từ chối nhận điểm 0. Lỗi vẫn nằm trong mẫu số. "
                  "Citation không được chấm đúng chỉ vì ID tồn tại.", "",
                  "Groq không trả cost trong usage đã nhận; số tiền không được gán 0. Token/request/latency và nhãn từng câu "
                  "được giữ trong artifact. Nhãn thủ công ban đầu được giữ riêng trong reviews.json."])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review")
    review.add_argument("--run", type=Path, required=True)
    review.add_argument("--cases", type=Path, required=True)
    review.add_argument("--source-pdf", type=Path, required=True)
    frozen = sub.add_parser("freeze")
    frozen.add_argument("--dev-root", type=Path, required=True)
    frozen.add_argument("--corpus", type=Path, required=True)
    frozen.add_argument("--test-cases", type=Path, required=True)
    frozen.add_argument("--baseline", type=Path, default=Path("configs/A-dense.json"))
    frozen.add_argument("--candidate", type=Path, default=Path("configs/D-context.json"))
    frozen.add_argument("--source-pdf", type=Path, required=True)
    frozen.add_argument("--output", type=Path, required=True)
    summary = sub.add_parser("report")
    summary.add_argument("--runs", type=Path, nargs="+", required=True)
    summary.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "review":
        labels = load_json(args.run / "reviews.ai.json")
        result = summarize(load_json(args.cases), load_json(args.run / "run.json"), labels, file_hash(args.source_pdf))
        save_json(args.run / "audit_summary.ai.json", result)
        print({k: result[k] for k in ("evaluation_mode", "grounded_complete", "citation_validity", "abstention")})
    elif args.command == "freeze":
        baseline, candidate = Experiment.read(args.baseline), Experiment.read(args.candidate)
        paths = [args.dev_root / c.name for c in (baseline, candidate)]
        jobs = [load_json(p / "run.json") for p in paths]
        summaries = [load_json(p / "audit_summary.ai.json") for p in paths]
        # The label files remain bound to the summary; never freeze an edited review.
        if any(s["review_hash"] != fingerprint(load_json(p / "reviews.ai.json")) for s, p in zip(summaries, paths)):
            raise ValueError("AI labels changed after aggregation")
        result = freeze(load_json(args.corpus / "chunks.json"), load_json(args.test_cases),
                        baseline, candidate, jobs, summaries, file_hash(args.source_pdf))
        save_json(args.output, result)
        print({"selected": result["selected_experiment"]["name"], "evaluation_mode": MODE, "output": str(args.output)})
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report(args.runs), encoding="utf-8")
        print("Saved", args.output)


if __name__ == "__main__":
    main()
