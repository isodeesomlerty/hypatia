from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import ViewerContext, get_viewer_context
from app.models import JobSummary
from app.store import get_job

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobSummary)
def get_job_summary(
    job_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> JobSummary:
    try:
        return get_job(job_id, viewer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
