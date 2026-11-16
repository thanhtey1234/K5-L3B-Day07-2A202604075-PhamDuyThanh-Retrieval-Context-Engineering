"""Fetch the public, checksum-pinned scanned PDF used for AI source review."""

from pathlib import Path

import httpx

from day7_rag.io import file_hash, load_json


def main():
    root = Path("work/corpora/day6")
    source = load_json(root / "manifest.json")["source_url"]
    destination = root / "original-law.pdf"
    expected = "eded93a3e2820913c6d0801a24977b4588d65c7da1838a952e43faed9af78b08"
    if not destination.exists():
        response = httpx.get(source, timeout=120, follow_redirects=True)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise ValueError("Expected the published PDF")
        import hashlib
        if hashlib.sha256(response.content).hexdigest() != expected:
            raise ValueError("Published PDF changed; new source review is required")
        destination.write_bytes(response.content)
    if file_hash(destination) != expected:
        raise ValueError("Local original PDF checksum mismatch")
    print(destination, expected)


if __name__ == "__main__":
    main()
