from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RelationshipStatus(StrEnum):
    READY = "ready"
    PENDING = "pending"


class UploadSourceKind(StrEnum):
    PDF_BATCH = "pdf_batch"
    ZIP_IMPORT = "zip_import"


class UploadItemStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class BatchStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    REJECTED = "rejected"


class JobStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PaperStatus(StrEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    READY = "ready"
    PAIRWISE_PENDING = "pairwise_pending"


class GraphNode(BaseModel):
    id: str
    label: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    status: RelationshipStatus = RelationshipStatus.READY
    visible_strength: int = 1


class GraphPayload(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class WorkspaceSummary(BaseModel):
    workspace_id: str
    name: str
    paper_count: int = 0
    active_batch_count: int = 0
    active_job_count: int = 0


class WorkspaceAccessSummary(BaseModel):
    workspace_id: str
    name: str
    role: str


class ViewerSummary(BaseModel):
    user_id: str
    email: str
    display_name: str
    auth_mode: str
    default_workspace_id: str
    workspaces: list[WorkspaceAccessSummary] = Field(default_factory=list)


class WorkspaceGraphResponse(BaseModel):
    workspace_id: str
    graph: GraphPayload


class PaperSummary(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    status: PaperStatus = PaperStatus.READY
    source_filename: str | None = None


class MethodologyCheck(BaseModel):
    check: str
    status: str
    detail: str


class HealthScoreSummary(BaseModel):
    overall_score: str = "caution"
    checks: list[MethodologyCheck] = Field(default_factory=list)


class ClaimDetail(BaseModel):
    claim_id: str
    text: str
    claim_type: str = "descriptive"
    evidence_type: str = "other"
    evidence_strength: str = "moderate"
    evidence_reasoning: str = ""
    key_variables: list[str] = Field(default_factory=list)
    context: str = ""


class PaperDetail(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    status: PaperStatus = PaperStatus.READY
    source_filename: str | None = None
    ingestion_mode: str | None = None
    page_count: int | None = None
    file_size_mb: float | None = None
    health_score: HealthScoreSummary = Field(default_factory=HealthScoreSummary)
    claims: list[ClaimDetail] = Field(default_factory=list)


class PaperDetailResponse(BaseModel):
    workspace_id: str
    paper: PaperDetail


class WorkspacePaperListResponse(BaseModel):
    workspace_id: str
    papers: list[PaperSummary] = Field(default_factory=list)


class JobSummary(BaseModel):
    job_id: str
    workspace_id: str
    batch_id: str | None = None
    job_type: str
    status: JobStatus
    progress_label: str
    completed_steps: int = 0
    total_steps: int = 0
    retryable: bool = True
    created_at: datetime


class WorkspaceJobListResponse(BaseModel):
    workspace_id: str
    jobs: list[JobSummary] = Field(default_factory=list)


class UploadItemInput(BaseModel):
    filename: str
    media_type: str | None = None
    size_bytes: int | None = None
    storage_backend: str | None = None
    storage_key: str | None = None
    sha256: str | None = None
    validation_error: str | None = None


class UploadItemResult(BaseModel):
    filename: str
    media_type: str | None = None
    size_bytes: int | None = None
    status: UploadItemStatus
    message: str


class UploadBatchProgress(BaseModel):
    total_items: int = 0
    accepted_items: int = 0
    rejected_items: int = 0
    papers_analyzed: int = 0
    pairwise_completed: int = 0
    pairwise_pending: int = 0


class UploadBatchSummary(BaseModel):
    batch_id: str
    workspace_id: str
    source_kind: UploadSourceKind
    status: BatchStatus
    created_at: datetime
    job_id: str | None = None
    progress: UploadBatchProgress
    items: list[UploadItemResult] = Field(default_factory=list)


class WorkspaceBatchListResponse(BaseModel):
    workspace_id: str
    batches: list[UploadBatchSummary] = Field(default_factory=list)


class RelationshipAggregate(BaseModel):
    supports: int = 0
    contradicts: int = 0
    extends: int = 0
    qualifies: int = 0
    total: int = 0
    dominant: str | None = None


class ClaimRelationshipDetail(BaseModel):
    claim_relationship_id: str
    source_claim_id: str
    source_claim_text: str = ""
    target_claim_id: str
    target_claim_text: str = ""
    relationship: str
    relationship_strength: str = ""
    explanation: str = ""
    methodological_note: str = ""


class RelationshipAttempt(BaseModel):
    job_id: str
    status: JobStatus
    progress_label: str
    retryable: bool = True
    created_at: datetime
    error_kind: str | None = None


class PaperRelationshipDetail(BaseModel):
    relationship_id: str
    workspace_id: str
    relationship_type: str
    status: RelationshipStatus = RelationshipStatus.READY
    visible_strength: int = 1
    source_paper: PaperSummary
    target_paper: PaperSummary
    aggregate: RelationshipAggregate = Field(default_factory=RelationshipAggregate)
    claim_relationships: list[ClaimRelationshipDetail] = Field(default_factory=list)
    last_attempt: RelationshipAttempt | None = None


class PaperRelationshipDetailResponse(BaseModel):
    workspace_id: str
    relationship: PaperRelationshipDetail


class UploadBatchCreateRequest(BaseModel):
    workspace_id: str
    source_kind: UploadSourceKind
    items: list[UploadItemInput] = Field(default_factory=list)


class UploadBatchCreateResponse(BaseModel):
    batch: UploadBatchSummary
    job: JobSummary | None = None


class APIMetaResponse(BaseModel):
    name: str
    version: str
    environment: str
    auth_strategy: str
    storage_strategy: str
    active_storage_backend: str
    storage_detail: str
