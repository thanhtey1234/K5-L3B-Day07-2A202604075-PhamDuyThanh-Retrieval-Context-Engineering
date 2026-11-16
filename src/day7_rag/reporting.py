"""Render measured artifacts without manufacturing human labels or quality scores."""
from .io import load_json


def display_rate(value):
    if not value or value.get("N", 0) == 0:
        return "0/0 (không áp dụng)"
    return f"{value['n']}/{value['N']} ({value['rate']:.1%})"


def markdown_report(run_directories):
    lines = ["# Kết quả thực nghiệm Day 7", "", "Chỉ tổng hợp artifact đã chạy; nhãn thủ công chưa có sẽ được ghi rõ.", "",
             "| Cấu hình | Split | Chế độ | Hit@1 | Evidence Hit@3 | Context evidence | Lỗi | Request |",
             "|---|---|---|---|---|---|---:|---:|"]
    audits = []
    for directory in run_directories:
        from pathlib import Path
        root = Path(directory)
        run = load_json(root / "run.json")
        if run["state"] != "complete":
            lines.append(f"| {run['manifest']['experiment']['name']} | {run['manifest']['split']} | {run['state']} | — | — | — | — | — |")
            continue
        summary = load_json(root / "retrieval_summary.json")
        m = run["manifest"]
        lines.append(f"| {m['experiment']['name']} | {m['split']} | {m['mode']} | {display_rate(summary['hit_at_1'])} | "
                     f"{display_rate(summary['evidence_hit_at_3'])} | {display_rate(summary['context_evidence_rate'])} | "
                     f"{summary['errors']} | {summary['request_count']} |")
        audit = root / "audit_summary.json"
        audits.append((m["experiment"]["name"], load_json(audit) if audit.exists() else None))
    lines.extend(["", "## Đánh giá câu trả lời", ""])
    for name, summary in audits:
        if summary is None:
            lines.append(f"- {name}: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.")
        else:
            lines.append(f"- {name}: citation {display_rate(summary['citation_validity'])}; abstention {display_rate(summary['abstention'])}; grounded answer {summary['grounded_answer']}.")
            if "advanced_pass" in summary:
                lines.append(f"  Nâng cao: {display_rate(summary['advanced_pass'])}; đạt ngưỡng 90%: {summary['threshold_met']}.")
    return "\n".join(lines) + "\n"
