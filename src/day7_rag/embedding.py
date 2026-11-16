"""Real local embedding with content-addressed caches; no random-vector fallback."""

import math
from pathlib import Path

from .io import fingerprint, load_json, save_json


class Embedder:
    def __init__(self, model_name, *, revision=None, device="cpu", cache_dir=None, max_length=2048):
        from huggingface_hub import hf_hub_download
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        config_path = Path(hf_hub_download(model_name, "config.json", revision=revision or "main"))
        parts = config_path.parts
        if "snapshots" not in parts:
            raise ValueError("Could not resolve an immutable Hugging Face model revision")
        self.revision = parts[parts.index("snapshots") + 1]
        self.model = SentenceTransformer(model_name, revision=self.revision, device=device)
        self.model.max_seq_length = max_length
        self.dimensions = self.model.get_embedding_dimension()
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.identity = {"model": model_name, "revision": self.revision, "dimensions": self.dimensions,
                         "max_length": max_length, "normalized": True}

    def encode(self, texts):
        output = [None] * len(texts)
        missing = []
        for position, text in enumerate(texts):
            key = fingerprint({"embedding": self.identity, "text": text})
            path = self.cache_dir / f"{key}.json" if self.cache_dir else None
            if path and path.exists():
                vector = load_json(path)
                output[position] = vector
            else:
                missing.append((position, text, path))
        # Group similar lengths globally to avoid padding short labels to the
        # longest paragraph in every batch on a CPU-only machine.
        missing.sort(key=lambda item: len(item[1]))
        for start in range(0, len(missing), 8):
            batch = missing[start:start + 8]
            vectors = self.model.encode([text for _, text, _ in batch], batch_size=8,
                                        normalize_embeddings=True, show_progress_bar=False).tolist()
            for (position, _, path), vector in zip(batch, vectors):
                output[position] = vector
                if path:
                    save_json(path, vector)
            if len(missing) > 100 and (start == 0 or (start // 8) % 25 == 0):
                import logging
                logging.getLogger(__name__).warning("Embedding progress: %s/%s uncached chunks",
                                                    min(start + 8, len(missing)), len(missing))
        for vector in output:
            if vector is None or len(vector) != self.dimensions or not all(math.isfinite(v) for v in vector):
                raise ValueError("Invalid embedding dimensions or nonfinite vector")
        return output

    def query(self, text):
        return self.encode([text])[0]
