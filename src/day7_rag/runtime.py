from .contracts import validate_chunks
from .embedding import Embedder
from .io import load_json
from .retrieval import Retrieval
from .store import PgRetriever


def build_runtime(corpus_dir, settings, experiment, *, index_id=None):
    from pathlib import Path
    root = Path(corpus_dir)
    chunks = load_json(root / "chunks.json")
    validate_chunks(chunks)
    dense = None
    if experiment.method != "bm25":
        manifest = load_json(root / "manifest.json")
        is_day6 = manifest["source_id"] == "luat_an_ninh_mang_116-2025"
        embedder = Embedder(settings.day6_model if is_day6 else settings.advanced_model,
                            revision=settings.day6_revision if is_day6 else settings.advanced_revision,
                            device=settings.device, cache_dir=settings.work_dir / "embedding_cache")
        index_path = root / "index.json"
        if not index_id and index_path.exists():
            index_id = load_json(index_path)["index_id"]
        if not is_day6 and not index_id:
            raise ValueError("Chạy lệnh index cho corpus nâng cao trước khi dùng dense/hybrid")
        dense = PgRetriever(settings.database_url, embedder, strategy=settings.day6_strategy, index_id=index_id)
        dense.inspect()
        database_chunks = dense.load_chunks()
        expected = {(c["id"], c["text"], c["source_id"], c["page"]) for c in chunks}
        actual = {(c["id"], c["text"], c["source_id"], c["page"]) for c in database_chunks}
        if expected != actual:
            raise ValueError("Corpus export and vector index differ; export Day 6 or rebuild the versioned index")
        # The corpus export is the reproducibility boundary. Declared filter
        # values must agree in both stores; auxiliary DB-only fields are ignored.
        database_by_id = {c["id"]: c for c in database_chunks}
        for c in chunks:
            for key, value in c["metadata"].items():
                actual = database_by_id[c["id"]]["metadata"]
                if key in actual and actual[key] != value:
                    raise ValueError("Corpus metadata differs from vector store; export Day 6 again")
    retriever = Retrieval(chunks, experiment, dense=dense)
    retriever.provenance = {"store": "postgresql/pgvector" if dense else "in-memory BM25",
                            "index_id": index_id, "day6_strategy": settings.day6_strategy if dense and not index_id else None,
                            "embedding": dense.embedder.identity if dense else None}
    return chunks, retriever
