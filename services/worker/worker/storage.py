from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator

import boto3
from botocore.config import Config as BotoConfig

from worker.config import settings


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


_MATERIALIZER = UploadMaterializer()


def get_upload_materializer() -> UploadMaterializer:
    return _MATERIALIZER
