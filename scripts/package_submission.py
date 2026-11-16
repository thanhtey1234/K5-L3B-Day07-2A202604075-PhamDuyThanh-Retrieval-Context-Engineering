"""Package the reproducible submission, excluding keys, caches and source downloads."""

from pathlib import Path
import zipfile

from day7_rag.config import Settings
from day7_rag.evaluation import package_hash
from day7_rag.io import file_hash, fingerprint, load_json, save_json


def main():
    root = Path(__file__).resolve().parents[1]
    frozen = load_json(root / "artifacts/frozen-basic-ai.json")
    if frozen["code_hash"] != package_hash() or frozen["human_verified"] is not False:
        raise ValueError("Inference changed after freeze or evaluation provenance is inconsistent")
    for split in ("dev", "test"):
        for config in ("A-dense", "D-context"):
            folder = root / "artifacts/runs" / f"basic-agent-groq-{split}" / config
            job, summary = load_json(folder / "run.json"), load_json(folder / "audit_summary.ai.json")
            if (job["state"] != "complete" or summary["run_hash"] != fingerprint(job)
                    or summary["review_hash"] != fingerprint(load_json(folder / "reviews.ai.json"))
                    or job["manifest"]["code_hash"] != frozen["code_hash"]):
                raise ValueError("Packaged run/review/hash mismatch")
            if split == "test" and job["manifest"]["cases_hash"] != frozen["test_hash"]:
                raise ValueError("Packaged test differs from frozen cases")
    folders = ("src", "scripts", "app_pages", "configs", "data/benchmarks", "artifacts",
               "report", "docs", "assets", "starter", "tests", ".github")
    paths = [p for folder in folders for p in (root / folder).rglob("*") if p.is_file()]
    paths += list(root.glob("*.md"))
    paths += [p for p in (root / "data").iterdir() if p.is_file() and p.suffix in {".json", ".md"}]
    paths += [root / name for name in (".gitignore", ".env.example", "pyproject.toml", "requirements.lock.txt",
                                      "docker-compose.yml", "streamlit_app.py", ".streamlit/config.toml")]
    excluded_parts = {"__pycache__", ".venv", ".git", ".cache", ".pytest_cache", ".ruff_cache", "work", "output"}
    paths = sorted({p for p in paths if p.exists() and not (excluded_parts & set(p.relative_to(root).parts))
                    and not any(part.endswith(".egg-info") for part in p.relative_to(root).parts)
                    and p.suffix not in {".pyc", ".tmp"}
                    and p.name != "SUBMISSION_FILES.json"
                    and not (p.name.startswith(".env") and p.name != ".env.example")
                    and p.relative_to(root).as_posix() not in {".streamlit/secrets.toml"}
                    and not p.is_relative_to(root / "starter/data")
                    and not p.is_relative_to(root / "starter/results")})
    settings = Settings.from_env()
    for path in paths:
        data = path.read_bytes()
        if any(key and key.encode() in data for key in (settings.api_key, settings.groq_key)):
            raise ValueError(f"Secret found in {path.relative_to(root)}; package was not created")
    inventory = root / "artifacts/SUBMISSION_FILES.json"
    save_json(inventory, {"files_excluding_this_manifest": [
        {"path": p.relative_to(root).as_posix(), "sha256": file_hash(p), "bytes": p.stat().st_size} for p in paths],
        "inference_code_hash": package_hash(), "evaluation_mode": frozen["evaluation_mode"],
        "excluded": [".env/keys", "Git metadata", "work downloads and model cache", "virtualenvs", "compiled files"]})
    paths.append(inventory)
    destination = root / "output/Day7_2A202604075_PhamDuyThanh_submission.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            archive.write(path, path.relative_to(root).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity verification failed")
        if any(name == ".env" or name.startswith(("work/", ".git/", ".venv/")) for name in archive.namelist()):
            raise ValueError("Unexpected private/runtime content")
    print({"archive": str(destination), "files": len(paths), "bytes": destination.stat().st_size,
           "sha256": file_hash(destination), "actual_api_keys_found": False})


if __name__ == "__main__":
    main()
