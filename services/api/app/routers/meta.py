from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.models import APIMetaResponse
from app.storage import describe_upload_storage
from app.store import get_active_repository_info

router = APIRouter(prefix="/v1", tags=["meta"])


@router.get("/meta", response_model=APIMetaResponse)
def get_meta() -> APIMetaResponse:
    repository_info = get_active_repository_info()
    upload_backend = settings.upload_storage_backend.lower()
    return APIMetaResponse(
        name=settings.app_name,
        version="0.1.0",
        environment=settings.environment,
        auth_strategy="Clerk bearer tokens with optional development header fallback",
        storage_strategy="Postgres + object storage + workers",
        active_storage_backend=f"{repository_info.backend}+{upload_backend}",
        storage_detail=f"{repository_info.detail} {describe_upload_storage()}",
    )
