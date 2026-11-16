"""Run the declared A–E experiments on DEV only, with resumable artifacts."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from day7_rag.config import Experiment, Settings
from day7_rag.evaluation import run_benchmark
from day7_rag.io import load_json
from day7_rag.providers import create_client
from day7_rag.retrieval import Retrieval
from day7_rag.runtime import build_runtime

parser = argparse.ArgumentParser()
parser.add_argument("--corpus", type=Path, default=Path("work/corpora/day6"))
parser.add_argument("--cases", type=Path, default=Path("data/benchmarks/basic/dev.json"))
parser.add_argument("--mode", choices=["retrieval", "agent"], default="retrieval")
parser.add_argument("--output", type=Path, default=Path("artifacts/runs/basic-dev"))
parser.add_argument("--configs", type=Path, nargs="+", help="Explicit config subset, e.g. A and D to reserve test quota")
parser.add_argument("--rate-retries", type=int, default=0,
                    help="Resume a saved HTTP 429 checkpoint after 60s; never retries a daily-budget pause")
args = parser.parse_args()
cases = load_json(args.cases)
if any(q["split"] != "dev" for q in cases):
    raise ValueError("This runner accepts only an independent dev file")
settings = Settings.from_env()
client = create_client(settings) if args.mode == "agent" else None
try:
    if client:
        client.preflight()
    shared_chunks, shared_dense = None, None
    shared_provenance = None
    for path in args.configs or sorted(Path("configs").glob("*.json")):
        experiment = Experiment.read(path)
        if shared_chunks is None:
            chunks, retriever = build_runtime(args.corpus, settings, experiment)
            shared_chunks, shared_dense = chunks, retriever.dense
            shared_provenance = retriever.provenance
            if shared_dense:
                # Same warm-cache conditions for every configuration; no gold
                # enters embedding or the model during this preparation.
                shared_dense.embedder.encode([q["question"] for q in cases])
        else:
            chunks = shared_chunks
            retriever = Retrieval(chunks, experiment, dense=shared_dense)
            retriever.provenance = shared_provenance if experiment.method != "bm25" else {
                "store": "in-memory BM25", "embedding": None}
        retriever.provenance = {**(retriever.provenance or {}), "query_cache_policy": "original dev queries prewarmed"}
        output = args.output / experiment.name
        job = run_benchmark(cases, chunks, retriever, experiment, output, client=client, asset_root=args.corpus)
        print(experiment.name, job["state"], len(job["records"]), flush=True)
        for retry in range(args.rate_retries):
            if job["state"] != "paused_quota" or "429" not in (job.get("pending") or {}).get("reason", ""):
                break
            print(f"HTTP 429: saved checkpoint; wait 60s ({retry + 1}/{args.rate_retries})", flush=True)
            time.sleep(60)
            job = run_benchmark(cases, chunks, retriever, experiment, output, client=client, asset_root=args.corpus)
            print(experiment.name, job["state"], len(job["records"]), flush=True)
        if job["state"] != "complete":
            break
finally:
    if client:
        client.close()
