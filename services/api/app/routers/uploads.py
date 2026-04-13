from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import ViewerContext, get_viewer_context
from app.models import (
    UploadBatchCreateRequest,
    UploadBatchCreateResponse,
    UploadItemInput,
    UploadSourceKind,
    UploadBatchSummary,
)
from app.store import create_upload_batch, get_upload_batch
from app.storage import get_upload_storage

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


def _validation_error(
    source_kind: UploadSourceKind,
    filename: str,
    position: int,
    duplicate_in_batch: bool,
) -> str | None:
    lowered = filename.lower()
    if source_kind == UploadSourceKind.PDF_BATCH:
        if not lowered.endswith(".pdf"):
            return "Rejected. Only PDF files are accepted in batch PDF mode."
    else:
        if position > 0:
            return "Rejected. ZIP import mode expects a single .zip archive."
        if not lowered.endswith(".zip"):
            return "Rejected. ZIP import mode expects a single .zip archive."

    if duplicate_in_batch:
        return "Rejected. This file is a duplicate of another file in the same batch."

    return None


@router.post("/batch", response_model=UploadBatchCreateResponse)
def create_batch_upload(
    request: UploadBatchCreateRequest,
    viewer: ViewerContext = Depends(get_viewer_context),
) -> UploadBatchCreateResponse:
    return create_upload_batch(request, viewer)


@router.post("/batch-files", response_model=UploadBatchCreateResponse)
async def create_batch_file_upload(
    workspace_id: str = Form(...),
    source_kind: UploadSourceKind = Form(...),
    files: list[UploadFile] = File(...),
    viewer: ViewerContext = Depends(get_viewer_context),
) -> UploadBatchCreateResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files were provided")

    storage = get_upload_storage()
    seen_hashes: set[str] = set()
    items: list[UploadItemInput] = []

    for index, file in enumerate(files):
        filename = file.filename or f"upload-{index}"
        payload = await file.read()
        validation_error = None
        duplicate_in_batch = False

        if payload:
            import hashlib

            digest = hashlib.sha256(payload).hexdigest()
            duplicate_in_batch = digest in seen_hashes
            validation_error = _validation_error(
                source_kind,
                filename,
                index,
                duplicate_in_batch=duplicate_in_batch,
            )
            if validation_error is None:
                stored = storage.store_bytes(
                    workspace_id=workspace_id,
                    filename=filename,
                    media_type=file.content_type,
                    content=payload,
                )
                seen_hashes.add(stored.sha256)
                items.append(
                    UploadItemInput(
                        filename=filename,
                        media_type=file.content_type,
                        size_bytes=len(payload),
                        storage_backend=stored.storage_backend,
                        storage_key=stored.storage_key,
                        sha256=stored.sha256,
                    )
                )
                continue

        if validation_error is None:
            validation_error = "Rejected. Empty files cannot be ingested."

        items.append(
            UploadItemInput(
                filename=filename,
                media_type=file.content_type,
                size_bytes=len(payload),
                validation_error=validation_error,
            )
        )

    request = UploadBatchCreateRequest(
        workspace_id=workspace_id,
        source_kind=source_kind,
        items=items,
    )
    return create_upload_batch(request, viewer)


@router.get("/batch/{batch_id}", response_model=UploadBatchSummary)
def get_batch_upload(
    batch_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> UploadBatchSummary:
    try:
        return get_upload_batch(batch_id, viewer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Upload batch not found") from exc
