from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import ViewerContext, get_viewer_context
from app.models import (
    WorkspaceBatchListResponse,
    WorkspaceGraphResponse,
    WorkspaceJobListResponse,
    WorkspacePaperListResponse,
    WorkspaceSummary,
)
from app.store import (
    list_workspace_batches,
    get_workspace_graph,
    get_workspace_papers,
    get_workspace_summary,
    list_workspace_jobs,
)

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.get("/{workspace_id}", response_model=WorkspaceSummary)
def get_workspace(
    workspace_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> WorkspaceSummary:
    return get_workspace_summary(workspace_id, viewer)


@router.get("/{workspace_id}/graph", response_model=WorkspaceGraphResponse)
def get_workspace_graph_payload(
    workspace_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> WorkspaceGraphResponse:
    return get_workspace_graph(workspace_id, viewer)


@router.get("/{workspace_id}/papers", response_model=WorkspacePaperListResponse)
def get_workspace_paper_list(
    workspace_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> WorkspacePaperListResponse:
    return get_workspace_papers(workspace_id, viewer)


@router.get("/{workspace_id}/jobs", response_model=WorkspaceJobListResponse)
def get_workspace_job_list(
    workspace_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> WorkspaceJobListResponse:
    return list_workspace_jobs(workspace_id, viewer)


@router.get("/{workspace_id}/batches", response_model=WorkspaceBatchListResponse)
def get_workspace_batch_list(
    workspace_id: str, viewer: ViewerContext = Depends(get_viewer_context)
) -> WorkspaceBatchListResponse:
    return list_workspace_batches(workspace_id, viewer)
