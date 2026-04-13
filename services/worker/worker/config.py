from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_repo_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return str(path.resolve())


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://hypatia:hypatia@127.0.0.1:5432/hypatia",
    )
    poll_interval_seconds: float = float(os.getenv("HYPATIA_WORKER_POLL_SECONDS", "2.0"))
    upload_storage_backend: str = os.getenv("HYPATIA_UPLOAD_STORAGE_BACKEND", "local")
    upload_storage_root: str = _resolve_repo_path(
        os.getenv("HYPATIA_UPLOAD_STORAGE_ROOT", "data/v2-uploads")
    )
    upload_storage_s3_bucket: str = os.getenv("HYPATIA_UPLOAD_STORAGE_S3_BUCKET", "")
    upload_storage_s3_region: str = os.getenv("HYPATIA_UPLOAD_STORAGE_S3_REGION", "")
    upload_storage_s3_endpoint_url: str = os.getenv(
        "HYPATIA_UPLOAD_STORAGE_S3_ENDPOINT_URL", ""
    )
    upload_storage_s3_access_key_id: str = os.getenv(
        "HYPATIA_UPLOAD_STORAGE_S3_ACCESS_KEY_ID", ""
    )
    upload_storage_s3_secret_access_key: str = os.getenv(
        "HYPATIA_UPLOAD_STORAGE_S3_SECRET_ACCESS_KEY", ""
    )
    upload_storage_s3_prefix: str = os.getenv("HYPATIA_UPLOAD_STORAGE_S3_PREFIX", "uploads")
    upload_storage_s3_force_path_style: bool = (
        os.getenv("HYPATIA_UPLOAD_STORAGE_S3_FORCE_PATH_STYLE", "0") == "1"
    )
    search_embedding_provider: str = os.getenv("HYPATIA_SEARCH_EMBEDDING_PROVIDER", "auto")
    search_embedding_model: str = os.getenv(
        "HYPATIA_SEARCH_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )
    search_embedding_dimensions: int = int(
        os.getenv("HYPATIA_SEARCH_EMBEDDING_DIMENSIONS", "256")
    )
    search_embedding_openai_api_key: str = (
        os.getenv("HYPATIA_SEARCH_EMBEDDING_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY", "")
    )
    search_embedding_openai_base_url: str = os.getenv(
        "HYPATIA_SEARCH_EMBEDDING_OPENAI_BASE_URL",
        "https://api.openai.com/v1",
    )


settings = WorkerSettings()
