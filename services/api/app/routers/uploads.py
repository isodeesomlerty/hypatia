from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import ViewerContext, get_viewer_context
from app.models import (
    UploadBatchCreateRequest,
    UploadBatchCreateResponse,
    UploadBatchSummary,
)
from app.store import create_upload_batch, get_upload_batch

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


@router.post("/batch", response_model=UploadBatchCreateResponse)
def create_batch_upload(
    request: UploadBatchCreateRequest,
    viewer: ViewerContext = Depends(get_viewer_context),
) -> UploadBatchCreateResponse:
    return create_upload_batch(request, viewer)


@router.get("/batch/{batch_id}", response_model=UploadBatchSummary)
def get_batch_upload(
    batch_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> UploadBatchSummary:
    try:
        return get_upload_batch(batch_id, viewer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Upload batch not found") from exc
