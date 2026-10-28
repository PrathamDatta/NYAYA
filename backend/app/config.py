"""Configuration. Every value can be overridden with a NYAYA_-prefixed environment variable or a .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NYAYA_", env_file=str(ROOT / ".env"), extra="ignore")

    env: str = "development"  # development | production | test
    data_dir: Path = ROOT / "data"
    database_url: str = ""  # default: sqlite file inside data_dir
    secret_key: str = "dev-only-change-me"  # used to derive CSRF/session hashing salt
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:8000"])
    cookie_secure: bool = False  # set true when served over HTTPS
    serve_frontend: bool = True
    frontend_dist: Path = ROOT / "frontend" / "dist"

    # limits
    max_upload_mb: int = 15
    max_pages: int = 300
    rate_limit_per_minute: int = 60
    auth_rate_limit_per_minute: int = 10
    request_timeout_s: int = 120
    session_ttl_hours: int = 24 * 7

    # ML runtime
    model_dir: Path | None = None  # HF cache directory; default data_dir/models
    hf_token: str | None = None
    device: str = "cpu"  # cpu | cuda | auto
    memory_budget_mb: int = 8000  # models are loaded lazily and the least-recently-used are unloaded to stay within this
    max_loaded_models: int = 8
    max_seq_len: int = 512
    encode_batch_size: int = 8
    offline_models: bool = True  # never hit the network at request time; use `python -m app.cli download-models`
    translation_quantize_int8: bool = False  # dynamic int8 of Linear layers (CPU); lowers RAM, may lower quality

    # RAG
    generator_backend: str = "extractive"  # extractive | local_llm
    local_llm_repo: str = "Qwen/Qwen2.5-1.5B-Instruct"
    local_llm_revision: str = ""  # pin a commit SHA when enabling local_llm
    retrieval_top_k: int = 6
    min_query_coverage: float = 0.5  # IDF-weighted share of query terms found in the retrieved passages; tuned by eval/run_eval.py
    include_synthetic_corpus: bool = False  # tests only: synthetic fixtures are never searchable in production

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'nyaya.db').as_posix()}"

    @property
    def models_path(self) -> Path:
        p = self.model_dir or (self.data_dir / "models")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def upload_path(self) -> Path:
        p = self.data_dir / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def is_prod(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod and s.secret_key == "dev-only-change-me":
        raise RuntimeError("NYAYA_SECRET_KEY must be set in production")
    return s
