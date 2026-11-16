"""A declared page-filtered vision integration check, not an accuracy benchmark."""

import argparse
from dataclasses import replace
from pathlib import Path

from day7_rag.agent import run_agent
from day7_rag.config import Experiment, Settings
from day7_rag.io import load_json, save_json
from day7_rag.providers import create_client
from day7_rag.retrieval import Retrieval


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["openrouter", "groq"], required=True)
    parser.add_argument("--output", type=Path, default=Path("work/chat/vision-smoke.json"))
    args = parser.parse_args()
    root = Path("work/corpora/wdr2023")
    # The page and visual-only scope are explicitly part of this functional
    # check. No held-out question, test label or test-derived filter is used.
    chunks = [c for c in load_json(root / "chunks.json") if c.get("image") and
              c.get("content_type") in {"image", "chart", "diagram", "table"}]
    config = Experiment(name="vision-functional-smoke", method="bm25", top_k=1, context_budget=3000,
                        max_searches=1, max_views=1)
    question = ("Kiểm tra hình Figure O.1 ở trang PDF 33 của WDR 2023. "
                "Hãy dùng view_image đọc hình gốc và cho biết đơn vị của Population và Age. "
                "Trả lời bằng tiếng Việt kèm citation; không suy đoán khi chưa xem ảnh.")
    client = create_client(replace(Settings.from_env(), provider=args.provider))
    try:
        client.preflight()
        old = load_json(args.output) if args.output.exists() else None
        if old and old["status"] != "pending":
            raise ValueError("Smoke output already completed")
        result = run_agent(question, client, Retrieval(chunks, config), config, filters={"page": 33},
                           asset_root=root, checkpoint=old["checkpoint"] if old else None)
        save_json(args.output, {"evaluation_scope": "functional_smoke_only_not_benchmark", "question": question,
                               "declared_filters": {"page": 33}, "corpus_scope": "visual/table regions only",
                               "model": client.model_info, **result})
        print({"status": result["status"], "events": [e["event"] for e in result.get("events", [])],
               "answer": result.get("answer"), "reason": result.get("reason")})
    finally:
        client.close()


if __name__ == "__main__":
    main()
