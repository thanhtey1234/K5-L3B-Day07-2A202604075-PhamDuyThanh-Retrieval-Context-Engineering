"""Reproducible downloads and the inspected Day 6 paragraph splitter.

Paragraph splitting follows thanh tey's Day 6 chunking.py at the pinned commit;
IDs and whitespace are retained so the original pgvector index can be reused.
"""

import json
from pathlib import Path
import re
import unicodedata
import urllib.request

from .io import file_hash, load_json, save_json

DAY6_REPO = "thanhtey1234/K5-L3B-Day06_PhamDuyThanh-2A202604075-DataIngestionEngineering"
DAY6_COMMIT = "663df9fa1c0f7c5bafcb1e21f47433e5137d3057"
DAY6_RAW = f"https://raw.githubusercontent.com/{DAY6_REPO}/{DAY6_COMMIT}/starter/data/"
WDR_URL = "https://mapa.do.undp.org/files/publications/World%20Development%20Report%202023.%20Migrants,%20Refugees%20and%20Societies.pdf"
DAY6_PAGES_SHA256 = "a840fa8229b024404b4fedf748ca808e3101012f6901bde64c4bd39e188f3e64"
WDR_SHA256 = "9577adf6a2849918eaf406aa975082b278b26cd880277b4d4e87336f6200ee84"


def download(url, destination, expected_sha256=None):
    destination = Path(destination)
    if destination.exists():
        if expected_sha256 and file_hash(destination) != expected_sha256:
            raise ValueError("Existing download checksum mismatch")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Day7-RAG-Lab/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                out.write(block)
        if expected_sha256 and file_hash(temporary) != expected_sha256:
            raise ValueError("Download checksum mismatch")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def normalize_day6(text):
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\t", " ")
    text = "\n".join(re.sub(r"[ ]{2,}", " ", line).strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def paragraph_pieces(text, size=500):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    group = ""
    for paragraph in paragraphs:
        if len(paragraph) > size:
            if group:
                yield group
                group = ""
            sub = ""
            for sentence in re.split(r"(?<=[.?!;\n])\s+", paragraph):
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(sub) + len(sentence) + 1 <= size:
                    sub = f"{sub} {sentence}".strip()
                else:
                    if sub:
                        yield sub
                    if len(sentence) > size:
                        yield from (sentence[i:i+size].strip() for i in range(0, len(sentence), size) if sentence[i:i+size].strip())
                        sub = ""
                    else:
                        sub = sentence
            if sub:
                yield sub
        elif not group or len(group) + 2 + len(paragraph) <= size:
            group = group + "\n\n" + paragraph if group else paragraph
        else:
            yield group
            group = paragraph
    if group:
        yield group


def prepare_day6(output):
    output = Path(output)
    pages_path = download(DAY6_RAW + "pages.jsonl", output / "pages.jsonl", DAY6_PAGES_SHA256)
    upstream = load_json(download(DAY6_RAW + "manifest.json", output / "upstream_manifest.json"))
    source_id = upstream["source_id"]
    chunks, pages = [], []
    for line in pages_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pages.append(row)
        text = normalize_day6(row["text"])
        chapter = next(label for limit, label in ((7, "Chương I"), (12, "Chương II"), (22, "Chương III"),
                         (25, "Chương IV"), (26, "Chương V"), (30, "Chương VI"), (33, "Chương VII"),
                         (9999, "Chương VIII")) if row["page"] <= limit)
        metadata = {k: v for k, v in row.items() if k not in {"text", "content"}}
        metadata.update(char_count=len(text), document_id=source_id, source_id=source_id, chapter=chapter)
        for i, piece in enumerate(paragraph_pieces(text)):
            chunks.append({"id": f"{source_id}_p{row['page']}_para_{i:03d}", "source_id": source_id,
                           "source": source_id, "page": row["page"], "text": piece,
                           "content_type": "text", "metadata": {**metadata, "chunk_strategy": "by_paragraph",
                                                                   "char_length": len(piece)}})
    save_json(output / "chunks.json", chunks)
    manifest = {"source_id": source_id, "source_url": upstream["source_path_or_url"],
                "title": upstream["title"], "license": upstream["license_or_permission"],
                "upstream_repo": DAY6_REPO, "upstream_commit": DAY6_COMMIT,
                "pages_sha256": file_hash(pages_path), "chunks_sha256": file_hash(output / "chunks.json"),
                "physical_pages": len(pages), "chunk_count": len(chunks),
                "embedding_model": "AITeamVN/Vietnamese_Embedding", "embedding_dimensions": 1024,
                "strategy": "strategy_b", "notes": "OCR errors retained; compare with original PDF."}
    save_json(output / "manifest.json", manifest)
    return manifest


def prepare_wdr(output):
    output = Path(output)
    pdf = download(WDR_URL, output / "source.pdf", WDR_SHA256)
    manifest = {"source_id": "wdr2023", "title": "World Development Report 2023: Migrants, Refugees, and Societies",
                "source_url": "https://www.worldbank.org/en/publication/wdr2023", "download_url": WDR_URL,
                "license": "CC BY 3.0 IGO; third-party components may have separate rights",
                "attribution": "World Bank. 2023. World Development Report 2023: Migrants, Refugees, and Societies. doi:10.1596/978-1-4648-1941-4.",
                "adaptation_notice": "This is an adaptation of an original work by The World Bank. Views and opinions expressed in the adaptation are the sole responsibility of the author or authors of the adaptation and are not endorsed by The World Bank.",
                "translation_notice": "This translation was not created by The World Bank and should not be considered an official World Bank translation. The World Bank shall not be liable for any content or error in this translation.",
                "sha256": file_hash(pdf), "pdf": "source.pdf", "expected_physical_pages": 348,
                "visual_rights_policy": "Do not redistribute separately credited photographs; review component credit lines before sharing crops."}
    save_json(output / "manifest.json", manifest)
    return manifest
