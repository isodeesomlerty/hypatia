from __future__ import annotations

import os
from dataclasses import dataclass


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


settings = APISettings()
