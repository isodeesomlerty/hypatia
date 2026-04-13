from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator
from uuid import uuid4

import boto3
from botocore.config import Config as BotoConfig

from worker.config import settings


@dataclass(frozen=True)
class StoredUpload:
    filename: str
    media_type: str | None
    size_bytes: int
    sha256: str
    storage_backend: str
    storage_key: str


def _slugify_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-")
    return normalized or "upload.bin"


class UploadMaterializer:
    def __init__(self) -> None:
        self.local_root = Path(settings.upload_storage_root)
        self.s3_bucket = settings.upload_storage_s3_bucket
        self.s3_prefix = settings.upload_storage_s3_prefix.strip("/")
        session = boto3.session.Session(
            aws_access_key_id=settings.upload_storage_s3_access_key_id or None,
            aws_secret_access_key=settings.upload_storage_s3_secret_access_key or None,
            region_name=settings.upload_storage_s3_region or None,
        )
        self.s3_client = session.client(
            "s3",
            endpoint_url=settings.upload_storage_s3_endpoint_url or None,
            config=BotoConfig(
                s3={
                    "addressing_style": (
                        "path" if settings.upload_storage_s3_force_path_style else "auto"
                    ),
                }
            ),
        )

    @contextmanager
    def materialize(
        self,
        *,
        storage_backend: str | None,
        storage_key: str | None,
    ) -> Iterator[Path]:
        if not storage_backend or not storage_key:
            raise FileNotFoundError("Stored file reference is incomplete.")

        backend = storage_backend.lower()
        if backend == "local":
            path = self.local_root / storage_key
            if not path.exists():
                raise FileNotFoundError(f"Local upload storage is missing {storage_key}.")
            yield path
            return

        if backend == "s3":
            if not self.s3_bucket:
                raise RuntimeError(
                    "HYPATIA_UPLOAD_STORAGE_S3_BUCKET is required for S3-backed worker reads."
                )
            suffix = Path(storage_key).suffix or ".bin"
            temporary = NamedTemporaryFile(delete=False, suffix=suffix)
            temporary_path = Path(temporary.name)
            try:
                with temporary:
                    self.s3_client.download_fileobj(
                        Bucket=self.s3_bucket,
                        Key=storage_key,
                        Fileobj=temporary,
                    )
                yield temporary_path
            finally:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            return

        raise RuntimeError(f"Unsupported upload storage backend: {storage_backend}")

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

        backend = settings.upload_storage_backend.lower()
        if backend == "local":
            destination = self.local_root / object_key
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

        if backend == "s3":
            if settings.upload_storage_s3_prefix.strip("/"):
                object_key = f"{settings.upload_storage_s3_prefix.strip('/')}/{object_key}"
            if not self.s3_bucket:
                raise RuntimeError(
                    "HYPATIA_UPLOAD_STORAGE_S3_BUCKET is required for S3-backed worker writes."
                )
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=object_key,
                Body=content,
                ContentType=media_type or "application/octet-stream",
                Metadata={
                    "sha256": digest,
                    "original-filename": filename,
                },
            )
            return StoredUpload(
                filename=filename,
                media_type=media_type,
                size_bytes=len(content),
                sha256=digest,
                storage_backend="s3",
                storage_key=object_key,
            )

        raise RuntimeError(f"Unsupported upload storage backend: {settings.upload_storage_backend}")


_MATERIALIZER = UploadMaterializer()


def get_upload_materializer() -> UploadMaterializer:
    return _MATERIALIZER
