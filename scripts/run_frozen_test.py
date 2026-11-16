"""Run only the held-out split and configurations bound to an existing freeze."""

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rate-retries", type=int, default=5)
    args = parser.parse_args()
    frozen, cases = load_json(args.frozen), load_json(args.cases)
    if any(q.get("split") != "test" for q in cases):
        raise ValueError("This runner only accepts the declared held-out test file")
    configs = [Experiment(**c) for c in frozen["allowed_experiments"]]
    selected = frozen.get("selected_experiment")
    configs.sort(key=lambda c: c.public() != selected)  # Preserve quota for selected config first.
    settings = Settings.from_env()
    client = create_client(settings)
    try:
        client.preflight()
        chunks, dense, provenance = None, None, None
        for config in configs:
            if chunks is None:
                chunks, retriever = build_runtime(args.corpus, settings, config)
                dense, provenance = retriever.dense, retriever.provenance
                if dense:
                    dense.embedder.encode([q["question"] for q in cases])
            else:
                retriever = Retrieval(chunks, config, dense=dense)
            retriever.provenance = {**(provenance or {}), "query_cache_policy": "original test queries prewarmed"}
            path = args.output / config.name
            job = run_benchmark(cases, chunks, retriever, config, path, split="test", client=client,
                                asset_root=args.corpus, frozen=frozen)
            print(config.name, job["state"], len(job["records"]), flush=True)
            for retry in range(args.rate_retries):
                if job["state"] != "paused_quota" or "429" not in (job.get("pending") or {}).get("reason", ""):
                    break
                print(f"Saved HTTP 429 checkpoint; wait 60s ({retry + 1}/{args.rate_retries})", flush=True)
                time.sleep(60)
                job = run_benchmark(cases, chunks, retriever, config, path, split="test", client=client,
                                    asset_root=args.corpus, frozen=frozen)
                print(config.name, job["state"], len(job["records"]), flush=True)
            if job["state"] != "complete":
                break
    finally:
        client.close()


if __name__ == "__main__":
    main()
