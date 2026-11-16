from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
import re

from .io import load_json


@dataclass(frozen=True)
class Experiment:
    name: str = "A-dense"
    method: str = "dense"
    top_k: int = 3
    candidate_k: int = 10
    context_budget: int = 3000
    max_searches: int = 1
    max_views: int = 2
    rrf_k: int = 60

    def __post_init__(self):
        if not isinstance(self.name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", self.name) or self.name in {".", ".."}:
            raise ValueError("Experiment name must be a safe artifact directory name")
        if self.method not in {"dense", "bm25", "hybrid"}:
            raise ValueError("method must be dense, bm25 or hybrid")
        if any(type(v) is not int or v < 1 for v in (
            self.top_k, self.candidate_k, self.context_budget, self.max_searches, self.rrf_k
        )) or type(self.max_views) is not int or self.max_views < 0:
            raise ValueError("Invalid experiment limits")
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must cover top_k")

    @classmethod
    def read(cls, path):
        return cls(**load_json(path))

    def public(self):
        return asdict(self)


@dataclass(frozen=True)
class Settings:
    provider: str = "openrouter"
    api_key: str = field(default="", repr=False)
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "inclusionai/ling-3.2-flash:free"
    database_url: str = field(default="", repr=False)
    day6_strategy: str = "strategy_b"
    day6_model: str = "AITeamVN/Vietnamese_Embedding"
    advanced_model: str = "BAAI/bge-m3"
    day6_revision: str | None = None
    advanced_revision: str | None = None
    device: str = "cpu"
    work_dir: Path = Path("work")
    requests_per_minute: int = 10
    daily_budget: int = 45
    timeout: int = 120
    groq_key: str = field(default="", repr=False)
    groq_model: str = "qwen/qwen3.8-27b"
    groq_free_confirmed: bool = False
    groq_daily_requests: int = 900
    groq_daily_tokens: int = 180000
    groq_tokens_per_minute: int = 7200
    groq_max_output: int = 1024

    @property
    def active_key(self):
        return self.groq_key if self.provider == "groq" else self.api_key

    @property
    def active_model(self):
        return self.groq_model if self.provider == "groq" else self.model

    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv
        load_dotenv(override=False)
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openrouter"),
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url=os.getenv("OPENROUTER_BASE_URL", cls.base_url),
            model=os.getenv("OPENROUTER_MODEL", cls.model),
            database_url=os.getenv("DATABASE_URL", ""),
            day6_strategy=os.getenv("DAY6_STRATEGY", "strategy_b"),
            day6_model=os.getenv("DAY6_EMBEDDING_MODEL", cls.day6_model),
            advanced_model=os.getenv("ADVANCED_EMBEDDING_MODEL", cls.advanced_model),
            day6_revision=os.getenv("DAY6_EMBEDDING_REVISION") or None,
            advanced_revision=os.getenv("ADVANCED_EMBEDDING_REVISION") or None,
            device=os.getenv("RAG_DEVICE", "cpu"),
            work_dir=Path(os.getenv("RAG_WORK_DIR", "work")),
            requests_per_minute=int(os.getenv("OPENROUTER_REQUESTS_PER_MINUTE", "10")),
            daily_budget=int(os.getenv("OPENROUTER_DAILY_REQUEST_BUDGET", "45")),
            timeout=int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120")),
            groq_key=os.getenv("GROQ_API_KEY", ""),
            groq_model=os.getenv("GROQ_MODEL", cls.groq_model),
            groq_free_confirmed=os.getenv("GROQ_FREE_TIER_CONFIRMED", "").lower() in {"1", "true", "yes"},
            groq_daily_requests=int(os.getenv("GROQ_DAILY_REQUEST_BUDGET", "900")),
            groq_daily_tokens=int(os.getenv("GROQ_DAILY_TOKEN_BUDGET", "180000")),
            groq_tokens_per_minute=int(os.getenv("GROQ_TOKENS_PER_MINUTE", "7200")),
            groq_max_output=int(os.getenv("GROQ_MAX_OUTPUT_TOKENS", "1024")),
        )
