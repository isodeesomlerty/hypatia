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
class APISettings:
    app_name: str = "Hypatia API"
    api_prefix: str = "/v1"
    environment: str = os.getenv("HYPATIA_ENV", "development")
    clerk_issuer: str = os.getenv("CLERK_ISSUER", "")
    clerk_jwks_url: str = os.getenv("CLERK_JWKS_URL", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    storage_backend: str = os.getenv("HYPATIA_STORAGE_BACKEND", "auto")
    allow_demo_fallback: bool = os.getenv("HYPATIA_ALLOW_DEMO_FALLBACK", "1") != "0"
    allow_dev_auth: bool = os.getenv("HYPATIA_ALLOW_DEV_AUTH", "1") != "0"
    upload_storage_backend: str = os.getenv("HYPATIA_UPLOAD_STORAGE_BACKEND", "local")
    upload_storage_root: str = _resolve_repo_path(
        os.getenv("HYPATIA_UPLOAD_STORAGE_ROOT", "data/v2-uploads")
    )


settings = APISettings()
