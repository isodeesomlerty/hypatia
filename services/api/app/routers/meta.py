from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.models import APIMetaResponse
from app.store import get_active_repository_info

router = APIRouter(prefix="/v1", tags=["meta"])


@router.get("/meta", response_model=APIMetaResponse)
def get_meta() -> APIMetaResponse:
    repository_info = get_active_repository_info()
    return APIMetaResponse(
        name=settings.app_name,
        version="0.1.0",
        environment=settings.environment,
        auth_strategy="Clerk + Google OAuth (development header fallback enabled)",
        storage_strategy="Postgres + object storage + workers",
        active_storage_backend=repository_info.backend,
        storage_detail=repository_info.detail,
    )
