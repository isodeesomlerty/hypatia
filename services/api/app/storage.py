from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import boto3
from botocore.config import Config as BotoConfig

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


class S3UploadStorage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        prefix: str,
        force_path_style: bool,
    ) -> None:
        if not bucket:
            raise RuntimeError(
                "HYPATIA_UPLOAD_STORAGE_S3_BUCKET is required for S3 upload storage."
            )
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        session = boto3.session.Session(
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            region_name=region or None,
        )
        self.client = session.client(
            "s3",
            endpoint_url=endpoint_url or None,
            config=BotoConfig(
                s3={
                    "addressing_style": "path" if force_path_style else "auto",
                }
            ),
        )

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
        if self.prefix:
            object_key = f"{self.prefix}/{object_key}"
        self.client.put_object(
            Bucket=self.bucket,
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


@lru_cache(maxsize=1)
def get_upload_storage() -> UploadStorage:
    backend = settings.upload_storage_backend.lower()
    if backend == "local":
        return LocalUploadStorage(settings.upload_storage_root)
    if backend == "s3":
        return S3UploadStorage(
            bucket=settings.upload_storage_s3_bucket,
            region=settings.upload_storage_s3_region,
            endpoint_url=settings.upload_storage_s3_endpoint_url,
            access_key_id=settings.upload_storage_s3_access_key_id,
            secret_access_key=settings.upload_storage_s3_secret_access_key,
            prefix=settings.upload_storage_s3_prefix,
            force_path_style=settings.upload_storage_s3_force_path_style,
        )
    raise RuntimeError(f"Unsupported upload storage backend: {settings.upload_storage_backend}")


def describe_upload_storage() -> str:
    backend = settings.upload_storage_backend.lower()
    if backend == "local":
        return f"Upload storage is local disk at {settings.upload_storage_root}."
    if backend == "s3":
        endpoint = settings.upload_storage_s3_endpoint_url or "AWS S3 default endpoint"
        prefix = settings.upload_storage_s3_prefix.strip("/") or "(bucket root)"
        return (
            "Upload storage is S3-compatible object storage at "
            f"{endpoint} in bucket {settings.upload_storage_s3_bucket} "
            f"with prefix {prefix}."
        )
    return f"Upload storage backend {settings.upload_storage_backend} is configured."
