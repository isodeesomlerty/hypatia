from __future__ import annotations

from app.auth import ViewerContext
from app.models import (
    JobSummary,
    PaperDetailResponse,
    PaperRelationshipDetailResponse,
    UploadBatchCreateRequest,
    UploadBatchCreateResponse,
    UploadBatchSummary,
    ViewerSummary,
    WorkspaceBatchListResponse,
    WorkspaceGraphResponse,
    WorkspaceJobListResponse,
    WorkspacePaperListResponse,
    WorkspaceSummary,
)
from app.repository import RepositoryInfo, get_repository, get_repository_info


def get_active_repository_info() -> RepositoryInfo:
    return get_repository_info()


def get_viewer_summary(viewer: ViewerContext) -> ViewerSummary:
    return get_repository().get_viewer_summary(viewer)


def get_workspace_summary(workspace_id: str, viewer: ViewerContext) -> WorkspaceSummary:
    return get_repository().get_workspace_summary(workspace_id, viewer)


def get_workspace_graph(
    workspace_id: str, viewer: ViewerContext
) -> WorkspaceGraphResponse:
    return get_repository().get_workspace_graph(workspace_id, viewer)


def get_workspace_papers(
    workspace_id: str, viewer: ViewerContext
) -> WorkspacePaperListResponse:
    return get_repository().get_workspace_papers(workspace_id, viewer)


def get_paper_detail(
    workspace_id: str, paper_id: str, viewer: ViewerContext
) -> PaperDetailResponse:
    return get_repository().get_paper_detail(workspace_id, paper_id, viewer)


def get_paper_relationship_detail(
    workspace_id: str, relationship_id: str, viewer: ViewerContext
) -> PaperRelationshipDetailResponse:
    return get_repository().get_paper_relationship_detail(
        workspace_id,
        relationship_id,
        viewer,
    )


def list_workspace_jobs(
    workspace_id: str, viewer: ViewerContext
) -> WorkspaceJobListResponse:
    return get_repository().list_workspace_jobs(workspace_id, viewer)


def list_workspace_batches(
    workspace_id: str, viewer: ViewerContext
) -> WorkspaceBatchListResponse:
    return get_repository().list_workspace_batches(workspace_id, viewer)


def get_job(job_id: str, viewer: ViewerContext) -> JobSummary:
    return get_repository().get_job(job_id, viewer)


def get_upload_batch(batch_id: str, viewer: ViewerContext) -> UploadBatchSummary:
    return get_repository().get_upload_batch(batch_id, viewer)


def create_upload_batch(
    request: UploadBatchCreateRequest, viewer: ViewerContext
) -> UploadBatchCreateResponse:
    return get_repository().create_upload_batch(request, viewer)
