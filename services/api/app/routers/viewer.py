from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import ViewerContext, get_viewer_context
from app.models import ViewerSummary
from app.store import get_viewer_summary

router = APIRouter(prefix="/v1", tags=["viewer"])


@router.get("/viewer", response_model=ViewerSummary)
def get_viewer(viewer: ViewerContext = Depends(get_viewer_context)) -> ViewerSummary:
    return get_viewer_summary(viewer)
