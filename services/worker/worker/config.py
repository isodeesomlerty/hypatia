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
    upload_storage_root: str = _resolve_repo_path(
        os.getenv("HYPATIA_UPLOAD_STORAGE_ROOT", "data/v2-uploads")
    )


settings = WorkerSettings()
