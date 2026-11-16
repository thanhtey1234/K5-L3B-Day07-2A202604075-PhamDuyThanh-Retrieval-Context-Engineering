import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

from .config import Experiment, Settings
from .contracts import validate_cases, validate_chunks
from .evaluation import audit_summary, freeze_config, run_benchmark, validate_benchmark
from .io import load_json, save_json


def parser():
    p = argparse.ArgumentParser(description="Day 7 Agentic RAG — bằng chứng, nguồn và benchmark tái lập")
    sub = p.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check dependencies and configuration without exposing secrets")
    doctor.add_argument("--online", action="store_true")
    doctor.add_argument("--database", action="store_true")
    prepare = sub.add_parser("prepare", help="Download pinned public sources; no inference")
    prepare.add_argument("--corpus", choices=["day6", "wdr2023", "all"], default="all")
    prepare.add_argument("--output", type=Path, default=Path("work/corpora"))
    extract = sub.add_parser("extract", help="Extract every PDF page, tables and visual regions")
    extract.add_argument("--corpus", required=True, type=Path)
    extract.add_argument("--ocr-language", default="eng")
    describe = sub.add_parser("describe", help="Enrich visual index surrogates with the free vision model")
    describe.add_argument("--corpus", required=True, type=Path)
    export = sub.add_parser("export-day6", help="SELECT real Day 6 chunks into a portable corpus export")
    export.add_argument("--output", type=Path, required=True)
    index = sub.add_parser("index", help="Build an immutable index in rag_day7, without altering Day 6")
    index.add_argument("--corpus", required=True, type=Path)
    validate = sub.add_parser("validate", help="Validate chunks and/or benchmark; no inference")
    validate.add_argument("--corpus", type=Path)
    validate.add_argument("--cases", type=Path, nargs="+")
    validate.add_argument("--advanced", action="store_true")
    for name in ("ask", "benchmark"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--corpus", required=True, type=Path)
        cmd.add_argument("--config", type=Path, default=Path("configs/A-dense.json"))
        cmd.add_argument("--index-id")
        cmd.add_argument("--output", required=True, type=Path)
        if name == "ask":
            cmd.add_argument("question")
            cmd.add_argument("--filter", type=json.loads)
        else:
            cmd.add_argument("--cases", required=True, type=Path)
            cmd.add_argument("--split", choices=["dev", "test"], required=True)
            cmd.add_argument("--mode", choices=["agent", "retrieval"], default="agent")
            cmd.add_argument("--frozen", type=Path)
    review = sub.add_parser("review", help="Aggregate human labels; never infer them")
    review.add_argument("--run", required=True, type=Path)
    review.add_argument("--cases", required=True, type=Path)
    review.add_argument("--reviews", required=True, type=Path)
    review.add_argument("--advanced", action="store_true")
    freeze = sub.add_parser("freeze", help="Freeze a reviewed dev configuration before test")
    freeze.add_argument("--corpus", type=Path, required=True)
    freeze.add_argument("--test-cases", type=Path, required=True)
    freeze.add_argument("--config", type=Path, required=True)
    freeze.add_argument("--baseline", type=Path, default=Path("configs/A-dense.json"))
    freeze.add_argument("--dev-run", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    report = sub.add_parser("report", help="Generate a Markdown comparison from real run artifacts")
    report.add_argument("--runs", nargs="+", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    return p


def dispatch(args):
    settings = Settings.from_env()
    if args.command == "doctor":
        result = {"python": sys.version.split()[0], "api_key_configured": bool(settings.active_key),
                  "database_configured": bool(settings.database_url), "model": settings.active_model,
                  "provider": settings.provider,
                  "free_only": settings.groq_free_confirmed if settings.provider == "groq" else settings.model.endswith(":free"),
                  "dependencies": {}}
        for pkg in ("httpx", "psycopg", "sentence-transformers", "pymupdf", "streamlit"):
            try:
                result["dependencies"][pkg] = importlib.metadata.version(pkg)
            except importlib.metadata.PackageNotFoundError:
                result["dependencies"][pkg] = "missing"
        if args.online:
            from .providers import create_client
            client = create_client(settings)
            try:
                result[settings.provider] = client.preflight()
            finally:
                client.close()
        if args.database:
            from .store import PgRetriever
            result["database"] = PgRetriever(settings.database_url, None, strategy=settings.day6_strategy).inspect()
        return result
    if args.command == "prepare":
        from .sources import prepare_day6, prepare_wdr
        return {name: fn(args.output / name) for name, fn in (("day6", prepare_day6), ("wdr2023", prepare_wdr))
                if args.corpus in (name, "all")}
    if args.command == "extract":
        from .pdf import extract_pdf
        m = load_json(args.corpus / "manifest.json")
        return extract_pdf(args.corpus / m["pdf"], args.corpus, source_id=m["source_id"],
                           source_url=m["source_url"], ocr_language=args.ocr_language)
    if args.command == "validate":
        chunks = load_json(args.corpus / "chunks.json") if args.corpus else None
        if chunks is not None:
            validate_chunks(chunks)
        cases = [q for path in (args.cases or []) for q in load_json(path)]
        if cases:
            validate_cases(cases, chunks)
            if {q["split"] for q in cases} == {"dev", "test"}:
                validate_benchmark(cases, advanced=args.advanced)
        return {"valid": True, "chunks": len(chunks or []), "cases": len(cases)}
    if args.command == "export-day6":
        from .store import PgRetriever
        retriever = PgRetriever(settings.database_url, None, strategy=settings.day6_strategy)
        info = retriever.inspect()
        chunks = retriever.load_chunks()
        save_json(args.output / "chunks.json", chunks)
        save_json(args.output / "manifest.json", {"source_id": "luat_an_ninh_mang_116-2025",
                  "embedding_model": settings.day6_model, "embedding_dimensions": info["dimensions"],
                  "strategy": settings.day6_strategy, "origin": "read-only export from Day 6"})
        return info
    if args.command == "index":
        from .embedding import Embedder
        from .store import build_index
        manifest = load_json(args.corpus / "manifest.json")
        day6 = manifest["source_id"] == "luat_an_ninh_mang_116-2025"
        embedder = Embedder(settings.day6_model if day6 else settings.advanced_model,
                            revision=settings.day6_revision if day6 else settings.advanced_revision,
                            device=settings.device, cache_dir=settings.work_dir / "embedding_cache")
        index_id, m = build_index(settings.database_url, load_json(args.corpus / "chunks.json"), embedder,
                                  corpus_manifest=manifest)
        save_json(args.corpus / "index.json", {"index_id": index_id, "manifest": m})
        return {"index_id": index_id, "manifest": m}
    if args.command == "review":
        job = load_json(args.run / "run.json")
        summary = audit_summary(load_json(args.cases), job, load_json(args.reviews), advanced=args.advanced)
        save_json(args.run / "audit_summary.json", summary)
        return summary
    if args.command == "freeze":
        frozen = freeze_config(load_json(args.corpus / "chunks.json"), load_json(args.test_cases),
                               Experiment.read(args.baseline), Experiment.read(args.config),
                               load_json(args.dev_run / "run.json"), load_json(args.dev_run / "audit_summary.json"))
        save_json(args.output, frozen)
        return frozen
    if args.command == "report":
        from .reporting import markdown_report
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown_report(args.runs), encoding="utf-8")
        return {"report": str(args.output)}
    if args.command == "describe":
        from .providers import create_client
        from .pdf import describe_visuals
        client = create_client(settings)
        try:
            client.preflight()
            return describe_visuals(args.corpus, client)
        finally:
            client.close()
    if args.command in ("ask", "benchmark"):
        from .providers import create_client
        from .runtime import build_runtime
        experiment = Experiment.read(args.config)
        # New Day 6 indexes are an explicit fallback, preserving the original DB.
        index_path = args.corpus / "index.json"
        index_id = args.index_id or (load_json(index_path)["index_id"] if index_path.exists() else None)
        chunks, retriever = build_runtime(args.corpus, settings, experiment, index_id=index_id)
        client = None
        try:
            if args.command == "ask" or args.mode == "agent":
                client = create_client(settings)
                client.preflight()
            if args.command == "ask":
                from .agent import run_agent
                checkpoint = None
                if args.output.exists():
                    old = load_json(args.output)
                    if old.get("status") != "pending":
                        raise ValueError("Output already exists; use another filename")
                    checkpoint = old["checkpoint"]
                result = run_agent(args.question, client, retriever, experiment, filters=args.filter,
                                   asset_root=args.corpus, checkpoint=checkpoint)
                save_json(args.output, result)
                return result
            job = run_benchmark(load_json(args.cases), chunks, retriever, experiment, args.output,
                                split=args.split, client=client, asset_root=args.corpus,
                                frozen=load_json(args.frozen) if args.frozen else None)
            return {"state": job["state"], "completed": len(job["records"]), "output": str(args.output),
                    "pending_reason": (job.get("pending") or {}).get("reason")}
        finally:
            if client:
                client.close()
    raise ValueError("Unknown command")


def main():
    args = parser().parse_args()
    try:
        result = dispatch(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        # Provider/database exceptions can contain credentials in URLs; expose
        # actionable messages only for our own validation errors.
        from .openrouter import ProviderError, QuotaPause
        message = str(exc) if isinstance(exc, (ValueError, ProviderError, QuotaPause)) else "Kiểm tra cấu hình, kết nối và dependency."
        print(json.dumps({"error": type(exc).__name__, "message": message}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None
