"""Shared UI helpers. Loading a page never makes an inference request."""

from dataclasses import replace
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from .config import Experiment, Settings
from .io import load_json

ROOT = Path(__file__).resolve().parents[2]


def settings():
    value = Settings.from_env()
    # Native Streamlit secrets take precedence; environment remains convenient
    # for the shared CLI. Secrets are never placed in widget state or artifacts.
    try:
        if "OPENROUTER_API_KEY" in st.secrets:
            value = replace(value, api_key=st.secrets["OPENROUTER_API_KEY"])
        if "GROQ_API_KEY" in st.secrets:
            value = replace(value, groq_key=st.secrets["GROQ_API_KEY"])
        if "DATABASE_URL" in st.secrets:
            value = replace(value, database_url=st.secrets["DATABASE_URL"])
    except (FileNotFoundError, StreamlitSecretNotFoundError):
        pass
    return value


def corpus_root():
    return Path(st.session_state["corpus_path"])


@st.cache_data(ttl=60, max_entries=20)
def read_artifact(path, modified):
    return load_json(path)


def read(path):
    path = Path(path)
    return read_artifact(str(path), path.stat().st_mtime_ns)


@st.cache_resource(ttl=1800, max_entries=2)
def cached_runtime(corpus_dir, experiment_values, database_url, model, revision, device, work_dir, strategy, index_id):
    from .runtime import build_runtime
    cfg = Settings(database_url=database_url, day6_model=model, advanced_model=model,
                   day6_revision=revision, advanced_revision=revision, device=device,
                   work_dir=Path(work_dir), day6_strategy=strategy)
    return build_runtime(Path(corpus_dir), cfg, Experiment(**experiment_values), index_id=index_id)


def runtime(root, experiment, cfg):
    manifest = read(root / "manifest.json")
    day6 = manifest["source_id"] == "luat_an_ninh_mang_116-2025"
    index_id = read(root / "index.json")["index_id"] if (root / "index.json").exists() else None
    return cached_runtime(str(root), experiment.public(), cfg.database_url,
                          cfg.day6_model if day6 else cfg.advanced_model,
                          cfg.day6_revision if day6 else cfg.advanced_revision,
                          cfg.device, str(cfg.work_dir), cfg.day6_strategy, index_id)


def run_paths():
    paths = []
    for base in (ROOT / "artifacts" / "runs", settings().work_dir / "runs"):
        if base.exists():
            paths.extend(sorted(base.glob("**/run.json")))
    return paths
