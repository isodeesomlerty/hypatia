from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.config import settings


@dataclass(frozen=True)
class StoredUpload:
    filename: str
    media_type: str | None
    size_bytes: int
    sha256: str
    storage_backend: str
    storage_key: str


class UploadStorage(Protocol):
    def store_bytes(
        self,
        *,
        workspace_id: str,
        filename: str,
        media_type: str | None,
        content: bytes,
    ) -> StoredUpload: ...


def _slugify_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-")
    return normalized or "upload.bin"


class LocalUploadStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def store_bytes(
        self,
        *,
        workspace_id: str,
        filename: str,
        media_type: str | None,
        content: bytes,
    ) -> StoredUpload:
        digest = hashlib.sha256(content).hexdigest()
        safe_name = _slugify_filename(filename)
        object_key = f"{workspace_id}/{uuid4().hex[:10]}-{safe_name}"
        destination = self.root / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredUpload(
            filename=filename,
            media_type=media_type,
            size_bytes=len(content),
            sha256=digest,
            storage_backend="local",
            storage_key=object_key,
        )


def get_upload_storage() -> UploadStorage:
    backend = settings.upload_storage_backend.lower()
    if backend == "local":
        return LocalUploadStorage(settings.upload_storage_root)
    raise RuntimeError(f"Unsupported upload storage backend: {settings.upload_storage_backend}")
