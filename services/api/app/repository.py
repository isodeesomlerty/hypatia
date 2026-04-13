from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException

from app.auth import ViewerContext
from app.config import settings
from app.models import (
    BatchStatus,
    GraphEdge,
    GraphNode,
    GraphPayload,
    JobStatus,
    JobSummary,
    PaperStatus,
    PaperSummary,
    RelationshipStatus,
    UploadBatchCreateRequest,
    UploadBatchCreateResponse,
    UploadBatchProgress,
    UploadBatchSummary,
    UploadItemResult,
    UploadItemStatus,
    UploadSourceKind,
    ViewerSummary,
    WorkspaceAccessSummary,
    WorkspaceBatchListResponse,
    WorkspaceGraphResponse,
    WorkspaceJobListResponse,
    WorkspacePaperListResponse,
    WorkspaceSummary,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional in local scaffold
    psycopg = None
    dict_row = None


@dataclass(frozen=True)
class RepositoryInfo:
    backend: str
    detail: str


class WorkspaceRepository(Protocol):
    def info(self) -> RepositoryInfo: ...

    def get_viewer_summary(self, viewer: ViewerContext) -> ViewerSummary: ...

    def get_workspace_summary(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceSummary: ...

    def get_workspace_graph(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceGraphResponse: ...

    def get_workspace_papers(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspacePaperListResponse: ...

    def list_workspace_jobs(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceJobListResponse: ...

    def list_workspace_batches(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceBatchListResponse: ...

    def get_job(self, job_id: str, viewer: ViewerContext) -> JobSummary: ...

    def get_upload_batch(
        self, batch_id: str, viewer: ViewerContext
    ) -> UploadBatchSummary: ...

    def create_upload_batch(
        self, request: UploadBatchCreateRequest, viewer: ViewerContext
    ) -> UploadBatchCreateResponse: ...


class InMemoryWorkspaceRepository:
    def __init__(self) -> None:
        self._workspaces: dict[str, str] = {
            "demo": "Behavioral AI Research",
            "cognitive-lab": "Cognitive Influence Lab",
        }
        self._workspace_memberships: dict[str, dict[str, str]] = {
            "demo-user": {
                "demo": "owner",
                "cognitive-lab": "member",
            }
        }
        self._papers: dict[str, list[PaperSummary]] = {
            "demo": [
                PaperSummary(
                    paper_id="paper-1",
                    title="Biased AI writing assistants shift users' attitudes on societal issues",
                    authors=["Kobe Xie", "Robert Mahari"],
                    year=2026,
                    status=PaperStatus.READY,
                    source_filename="biased-writing-assistants.pdf",
                ),
                PaperSummary(
                    paper_id="paper-2",
                    title="Sycophantic AI decreases prosocial intentions and promotes dependence",
                    authors=["Myra Cheng", "Dan Jurafsky"],
                    year=2026,
                    status=PaperStatus.PAIRWISE_PENDING,
                    source_filename="sycophantic-ai.pdf",
                ),
                PaperSummary(
                    paper_id="paper-3",
                    title="Using Large Language Models in Behavioral Science",
                    authors=["Lena Park", "Jonah Everett"],
                    year=2025,
                    status=PaperStatus.READY,
                    source_filename="llms-behavioral-science.pdf",
                ),
            ],
            "cognitive-lab": [
                PaperSummary(
                    paper_id="paper-4",
                    title="How AI can fuel confirmation bias",
                    authors=["Steve Rathje", "Jay Van Bavel"],
                    year=2025,
                    status=PaperStatus.ANALYZING,
                    source_filename="confirmation-bias.pdf",
                )
            ],
        }
        self._graphs: dict[str, GraphPayload] = {
            "demo": GraphPayload(
                nodes=[
                    GraphNode(id="paper-1", label="Biased AI assistants"),
                    GraphNode(id="paper-2", label="Sycophantic AI"),
                    GraphNode(id="paper-3", label="LLMs in behavioral science"),
                ],
                edges=[
                    GraphEdge(
                        id="edge-1",
                        source="paper-1",
                        target="paper-2",
                        relationship_type="supports",
                        visible_strength=9,
                    ),
                    GraphEdge(
                        id="edge-2",
                        source="paper-2",
                        target="paper-3",
                        relationship_type="contradicts",
                        status=RelationshipStatus.PENDING,
                        visible_strength=2,
                    ),
                ],
            ),
            "cognitive-lab": GraphPayload(
                nodes=[GraphNode(id="paper-4", label="Confirmation bias study")],
                edges=[],
            ),
        }
        self._jobs: dict[str, JobSummary] = {
            "job-demo-ingest": JobSummary(
                job_id="job-demo-ingest",
                workspace_id="demo",
                batch_id="batch-demo-ingest",
                job_type="batch_ingestion",
                status=JobStatus.IN_PROGRESS,
                progress_label="2 of 3 papers analyzed; pairwise comparisons queued",
                completed_steps=2,
                total_steps=5,
                created_at=datetime(2026, 4, 12, 13, 30, tzinfo=UTC),
            ),
            "job-demo-search": JobSummary(
                job_id="job-demo-search",
                workspace_id="demo",
                batch_id=None,
                job_type="graph_rebuild",
                status=JobStatus.QUEUED,
                progress_label="Waiting for current ingestion batch to finish",
                completed_steps=0,
                total_steps=1,
                created_at=datetime(2026, 4, 12, 13, 42, tzinfo=UTC),
            ),
            "job-cognitive-analyze": JobSummary(
                job_id="job-cognitive-analyze",
                workspace_id="cognitive-lab",
                batch_id="batch-cognitive-ingest",
                job_type="paper_ingestion",
                status=JobStatus.IN_PROGRESS,
                progress_label="Extracting claims from one newly added paper",
                completed_steps=1,
                total_steps=3,
                created_at=datetime(2026, 4, 12, 14, 10, tzinfo=UTC),
            ),
        }
        self._batches: dict[str, UploadBatchSummary] = {
            "batch-demo-ingest": UploadBatchSummary(
                batch_id="batch-demo-ingest",
                workspace_id="demo",
                source_kind=UploadSourceKind.PDF_BATCH,
                status=BatchStatus.IN_PROGRESS,
                created_at=datetime(2026, 4, 12, 13, 30, tzinfo=UTC),
                job_id="job-demo-ingest",
                progress=UploadBatchProgress(
                    total_items=4,
                    accepted_items=3,
                    rejected_items=1,
                    papers_analyzed=2,
                    pairwise_completed=1,
                    pairwise_pending=2,
                ),
                items=[
                    UploadItemResult(
                        filename="biased-writing-assistants.pdf",
                        media_type="application/pdf",
                        size_bytes=4_100_000,
                        status=UploadItemStatus.ACCEPTED,
                        message="Claim extraction completed.",
                    ),
                    UploadItemResult(
                        filename="sycophantic-ai.pdf",
                        media_type="application/pdf",
                        size_bytes=5_600_000,
                        status=UploadItemStatus.ACCEPTED,
                        message="Pairwise comparison backlog is still running.",
                    ),
                    UploadItemResult(
                        filename="behavioral-llms.pdf",
                        media_type="application/pdf",
                        size_bytes=6_200_000,
                        status=UploadItemStatus.ACCEPTED,
                        message="Queued for paper analysis.",
                    ),
                    UploadItemResult(
                        filename="notes.txt",
                        media_type="text/plain",
                        size_bytes=900,
                        status=UploadItemStatus.REJECTED,
                        message="Unsupported file type. Batch ingestion accepts PDFs or a ZIP archive.",
                    ),
                ],
            ),
            "batch-cognitive-ingest": UploadBatchSummary(
                batch_id="batch-cognitive-ingest",
                workspace_id="cognitive-lab",
                source_kind=UploadSourceKind.ZIP_IMPORT,
                status=BatchStatus.IN_PROGRESS,
                created_at=datetime(2026, 4, 12, 14, 10, tzinfo=UTC),
                job_id="job-cognitive-analyze",
                progress=UploadBatchProgress(
                    total_items=1,
                    accepted_items=1,
                    rejected_items=0,
                    papers_analyzed=0,
                    pairwise_completed=0,
                    pairwise_pending=0,
                ),
                items=[
                    UploadItemResult(
                        filename="cognitive-import.zip",
                        media_type="application/zip",
                        size_bytes=7_200_000,
                        status=UploadItemStatus.ACCEPTED,
                        message="Archive queued for expansion and de-duplication.",
                    )
                ],
            ),
        }

    def info(self) -> RepositoryInfo:
        return RepositoryInfo(
            backend="in_memory",
            detail="Using in-memory demo repository fallback.",
        )

    def _workspace_memberships_for(self, user_id: str) -> dict[str, str]:
        memberships = self._workspace_memberships.get(user_id)
        if memberships is not None:
            return memberships
        self._workspace_memberships[user_id] = {"demo": "viewer"}
        return self._workspace_memberships[user_id]

    def _ensure_workspace(self, workspace_id: str, viewer: ViewerContext) -> None:
        if workspace_id not in self._workspaces:
            self._workspaces[workspace_id] = f"Workspace {workspace_id}"
        memberships = self._workspace_memberships_for(viewer.user_id)
        memberships.setdefault(workspace_id, "owner")
        self._papers.setdefault(workspace_id, [])
        self._graphs.setdefault(workspace_id, GraphPayload())

    def _assert_workspace_access(self, workspace_id: str, viewer: ViewerContext) -> str:
        memberships = self._workspace_memberships_for(viewer.user_id)
        role = memberships.get(workspace_id)
        if role is None:
            raise HTTPException(status_code=403, detail="Workspace access denied")
        return role

    def get_viewer_summary(self, viewer: ViewerContext) -> ViewerSummary:
        memberships = self._workspace_memberships_for(viewer.user_id)
        access = [
            WorkspaceAccessSummary(
                workspace_id=workspace_id,
                name=self._workspaces.get(workspace_id, f"Workspace {workspace_id}"),
                role=role,
            )
            for workspace_id, role in memberships.items()
        ]
        return ViewerSummary(
            user_id=viewer.user_id,
            email=viewer.email,
            display_name=viewer.display_name,
            auth_mode=viewer.auth_mode,
            default_workspace_id=viewer.default_workspace_id,
            workspaces=access,
        )

    def get_workspace_summary(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceSummary:
        self._ensure_workspace(workspace_id, viewer)
        self._assert_workspace_access(workspace_id, viewer)
        active_batches = [
            batch
            for batch in self._batches.values()
            if batch.workspace_id == workspace_id
            and batch.status in {BatchStatus.QUEUED, BatchStatus.IN_PROGRESS}
        ]
        active_jobs = [
            job
            for job in self._jobs.values()
            if job.workspace_id == workspace_id
            and job.status in {JobStatus.QUEUED, JobStatus.IN_PROGRESS}
        ]
        return WorkspaceSummary(
            workspace_id=workspace_id,
            name=self._workspaces[workspace_id],
            paper_count=len(self._papers.get(workspace_id, [])),
            active_batch_count=len(active_batches),
            active_job_count=len(active_jobs),
        )

    def get_workspace_graph(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceGraphResponse:
        self._ensure_workspace(workspace_id, viewer)
        self._assert_workspace_access(workspace_id, viewer)
        return WorkspaceGraphResponse(workspace_id=workspace_id, graph=self._graphs[workspace_id])

    def get_workspace_papers(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspacePaperListResponse:
        self._ensure_workspace(workspace_id, viewer)
        self._assert_workspace_access(workspace_id, viewer)
        return WorkspacePaperListResponse(
            workspace_id=workspace_id,
            papers=self._papers[workspace_id],
        )

    def list_workspace_jobs(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceJobListResponse:
        self._ensure_workspace(workspace_id, viewer)
        self._assert_workspace_access(workspace_id, viewer)
        jobs = sorted(
            (job for job in self._jobs.values() if job.workspace_id == workspace_id),
            key=lambda job: job.created_at,
            reverse=True,
        )
        return WorkspaceJobListResponse(workspace_id=workspace_id, jobs=jobs)

    def list_workspace_batches(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceBatchListResponse:
        self._ensure_workspace(workspace_id, viewer)
        self._assert_workspace_access(workspace_id, viewer)
        batches = sorted(
            (batch for batch in self._batches.values() if batch.workspace_id == workspace_id),
            key=lambda batch: batch.created_at,
            reverse=True,
        )
        return WorkspaceBatchListResponse(workspace_id=workspace_id, batches=batches)

    def get_job(self, job_id: str, viewer: ViewerContext) -> JobSummary:
        job = self._jobs[job_id]
        self._assert_workspace_access(job.workspace_id, viewer)
        return job

    def get_upload_batch(self, batch_id: str, viewer: ViewerContext) -> UploadBatchSummary:
        batch = self._batches[batch_id]
        self._assert_workspace_access(batch.workspace_id, viewer)
        return batch

    def create_upload_batch(
        self, request: UploadBatchCreateRequest, viewer: ViewerContext
    ) -> UploadBatchCreateResponse:
        self._ensure_workspace(request.workspace_id, viewer)
        self._assert_workspace_access(request.workspace_id, viewer)
        batch_id = f"batch-{uuid4().hex[:8]}"
        created_at = datetime.now(UTC)
        accepted_items = 0
        rejected_items = 0
        results: list[UploadItemResult] = []

        for index, item in enumerate(request.items):
            filename = item.filename.lower()
            if request.source_kind == UploadSourceKind.PDF_BATCH:
                is_valid = filename.endswith(".pdf")
                message = (
                    "Queued for PDF ingestion."
                    if is_valid
                    else "Rejected. Only PDF files are accepted in batch PDF mode."
                )
            else:
                is_valid = index == 0 and filename.endswith(".zip")
                message = (
                    "Archive queued for expansion and de-duplication."
                    if is_valid
                    else "Rejected. ZIP import mode expects a single .zip archive."
                )

            status = UploadItemStatus.ACCEPTED if is_valid else UploadItemStatus.REJECTED
            accepted_items += int(is_valid)
            rejected_items += int(not is_valid)
            results.append(
                UploadItemResult(
                    filename=item.filename,
                    media_type=item.media_type,
                    size_bytes=item.size_bytes,
                    status=status,
                    message=message,
                )
            )

        batch_status = BatchStatus.QUEUED if accepted_items else BatchStatus.REJECTED
        job: JobSummary | None = None
        job_id: str | None = None

        if accepted_items:
            job_id = f"job-{uuid4().hex[:8]}"
            job = JobSummary(
                job_id=job_id,
                workspace_id=request.workspace_id,
                batch_id=batch_id,
                job_type="batch_ingestion",
                status=JobStatus.QUEUED,
                progress_label=f"{accepted_items} accepted item(s) queued for ingestion.",
                completed_steps=0,
                total_steps=max(accepted_items + 2, 2),
                created_at=created_at,
            )
            self._jobs[job_id] = job

        batch = UploadBatchSummary(
            batch_id=batch_id,
            workspace_id=request.workspace_id,
            source_kind=request.source_kind,
            status=batch_status,
            created_at=created_at,
            job_id=job_id,
            progress=UploadBatchProgress(
                total_items=len(request.items),
                accepted_items=accepted_items,
                rejected_items=rejected_items,
                papers_analyzed=0,
                pairwise_completed=0,
                pairwise_pending=0,
            ),
            items=results,
        )
        self._batches[batch_id] = batch
        return UploadBatchCreateResponse(batch=batch, job=job)


class PostgresWorkspaceRepository:
    def __init__(self, database_url: str) -> None:
        if psycopg is None or dict_row is None:
            raise RuntimeError("psycopg is not installed")
        self.database_url = database_url

    def info(self) -> RepositoryInfo:
        return RepositoryInfo(
            backend="postgres",
            detail="Using Postgres repository backed by DATABASE_URL.",
        )

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def ping(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

    def _workspace_label(self, workspace_id: str) -> str:
        return workspace_id.replace("-", " ").title()

    def _ensure_viewer_seed(self, connection, viewer: ViewerContext) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (id, email, display_name, auth_mode, default_workspace_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    auth_mode = EXCLUDED.auth_mode,
                    default_workspace_id = EXCLUDED.default_workspace_id
                """,
                (
                    viewer.user_id,
                    viewer.email,
                    viewer.display_name,
                    viewer.auth_mode,
                    viewer.default_workspace_id,
                ),
            )
            cursor.execute(
                """
                INSERT INTO workspaces (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (viewer.default_workspace_id, self._workspace_label(viewer.default_workspace_id)),
            )
            cursor.execute(
                """
                INSERT INTO workspace_memberships (user_id, workspace_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, workspace_id) DO NOTHING
                """,
                (viewer.user_id, viewer.default_workspace_id, "owner"),
            )

    def _assert_workspace_access(self, connection, workspace_id: str, viewer: ViewerContext) -> str:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT role
                FROM workspace_memberships
                WHERE user_id = %s AND workspace_id = %s
                """,
                (viewer.user_id, workspace_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=403, detail="Workspace access denied")
        return row["role"]

    def _batch_items(self, connection, batch_id: str) -> list[UploadItemResult]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT filename, media_type, size_bytes, status, message
                FROM upload_batch_items
                WHERE batch_id = %s
                ORDER BY id ASC
                """,
                (batch_id,),
            )
            rows = cursor.fetchall()
        return [
            UploadItemResult(
                filename=row["filename"],
                media_type=row["media_type"],
                size_bytes=row["size_bytes"],
                status=row["status"],
                message=row["message"],
            )
            for row in rows
        ]

    def _batch_from_row(self, connection, row) -> UploadBatchSummary:
        return UploadBatchSummary(
            batch_id=row["id"],
            workspace_id=row["workspace_id"],
            source_kind=row["source_kind"],
            status=row["status"],
            created_at=row["created_at"],
            job_id=row["job_id"],
            progress=UploadBatchProgress(
                total_items=row["total_items"],
                accepted_items=row["accepted_items"],
                rejected_items=row["rejected_items"],
                papers_analyzed=row["papers_analyzed"],
                pairwise_completed=row["pairwise_completed"],
                pairwise_pending=row["pairwise_pending"],
            ),
            items=self._batch_items(connection, row["id"]),
        )

    def get_viewer_summary(self, viewer: ViewerContext) -> ViewerSummary:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT wm.workspace_id, wm.role, w.name
                    FROM workspace_memberships wm
                    JOIN workspaces w ON w.id = wm.workspace_id
                    WHERE wm.user_id = %s
                    ORDER BY w.name ASC
                    """,
                    (viewer.user_id,),
                )
                rows = cursor.fetchall()
        return ViewerSummary(
            user_id=viewer.user_id,
            email=viewer.email,
            display_name=viewer.display_name,
            auth_mode=viewer.auth_mode,
            default_workspace_id=viewer.default_workspace_id,
            workspaces=[
                WorkspaceAccessSummary(
                    workspace_id=row["workspace_id"],
                    name=row["name"],
                    role=row["role"],
                )
                for row in rows
            ],
        )

    def get_workspace_summary(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceSummary:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            self._assert_workspace_access(connection, workspace_id, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM workspaces WHERE id = %s",
                    (workspace_id,),
                )
                workspace = cursor.fetchone()
                if workspace is None:
                    raise HTTPException(status_code=404, detail="Workspace not found")
                cursor.execute(
                    "SELECT COUNT(*) AS count FROM papers WHERE workspace_id = %s",
                    (workspace_id,),
                )
                paper_count = cursor.fetchone()["count"]
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM upload_batches
                    WHERE workspace_id = %s AND status IN ('queued', 'in_progress')
                    """,
                    (workspace_id,),
                )
                batch_count = cursor.fetchone()["count"]
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM jobs
                    WHERE workspace_id = %s AND status IN ('queued', 'in_progress')
                    """,
                    (workspace_id,),
                )
                job_count = cursor.fetchone()["count"]
        return WorkspaceSummary(
            workspace_id=workspace_id,
            name=workspace["name"],
            paper_count=paper_count,
            active_batch_count=batch_count,
            active_job_count=job_count,
        )

    def get_workspace_graph(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceGraphResponse:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            self._assert_workspace_access(connection, workspace_id, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, title
                    FROM papers
                    WHERE workspace_id = %s
                    ORDER BY title ASC
                    """,
                    (workspace_id,),
                )
                nodes = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT id, source_paper_id, target_paper_id, relationship_type, status, visible_strength
                    FROM paper_relationships
                    WHERE workspace_id = %s
                    ORDER BY id ASC
                    """,
                    (workspace_id,),
                )
                edges = cursor.fetchall()
        return WorkspaceGraphResponse(
            workspace_id=workspace_id,
            graph=GraphPayload(
                nodes=[
                    GraphNode(id=row["id"], label=row["title"])
                    for row in nodes
                ],
                edges=[
                    GraphEdge(
                        id=row["id"],
                        source=row["source_paper_id"],
                        target=row["target_paper_id"],
                        relationship_type=row["relationship_type"],
                        status=row["status"],
                        visible_strength=row["visible_strength"],
                    )
                    for row in edges
                ],
            ),
        )

    def get_workspace_papers(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspacePaperListResponse:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            self._assert_workspace_access(connection, workspace_id, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, title, authors, publication_year, status, source_filename
                    FROM papers
                    WHERE workspace_id = %s
                    ORDER BY publication_year DESC NULLS LAST, title ASC
                    """,
                    (workspace_id,),
                )
                rows = cursor.fetchall()
        return WorkspacePaperListResponse(
            workspace_id=workspace_id,
            papers=[
                PaperSummary(
                    paper_id=row["id"],
                    title=row["title"],
                    authors=row["authors"] or [],
                    year=row["publication_year"],
                    status=row["status"],
                    source_filename=row["source_filename"],
                )
                for row in rows
            ],
        )

    def list_workspace_jobs(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceJobListResponse:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            self._assert_workspace_access(connection, workspace_id, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, workspace_id, batch_id, job_type, status, progress_label,
                           completed_steps, total_steps, retryable, created_at
                    FROM jobs
                    WHERE workspace_id = %s
                    ORDER BY created_at DESC
                    """,
                    (workspace_id,),
                )
                rows = cursor.fetchall()
        return WorkspaceJobListResponse(
            workspace_id=workspace_id,
            jobs=[
                JobSummary(
                    job_id=row["id"],
                    workspace_id=row["workspace_id"],
                    batch_id=row["batch_id"],
                    job_type=row["job_type"],
                    status=row["status"],
                    progress_label=row["progress_label"],
                    completed_steps=row["completed_steps"],
                    total_steps=row["total_steps"],
                    retryable=row["retryable"],
                    created_at=row["created_at"],
                )
                for row in rows
            ],
        )

    def list_workspace_batches(
        self, workspace_id: str, viewer: ViewerContext
    ) -> WorkspaceBatchListResponse:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            self._assert_workspace_access(connection, workspace_id, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, workspace_id, source_kind, status, created_at, job_id,
                           total_items, accepted_items, rejected_items,
                           papers_analyzed, pairwise_completed, pairwise_pending
                    FROM upload_batches
                    WHERE workspace_id = %s
                    ORDER BY created_at DESC
                    """,
                    (workspace_id,),
                )
                rows = cursor.fetchall()
            batches = [self._batch_from_row(connection, row) for row in rows]
        return WorkspaceBatchListResponse(workspace_id=workspace_id, batches=batches)

    def get_job(self, job_id: str, viewer: ViewerContext) -> JobSummary:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, workspace_id, batch_id, job_type, status, progress_label,
                           completed_steps, total_steps, retryable, created_at
                    FROM jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError(job_id)
                self._assert_workspace_access(connection, row["workspace_id"], viewer)
        return JobSummary(
            job_id=row["id"],
            workspace_id=row["workspace_id"],
            batch_id=row["batch_id"],
            job_type=row["job_type"],
            status=row["status"],
            progress_label=row["progress_label"],
            completed_steps=row["completed_steps"],
            total_steps=row["total_steps"],
            retryable=row["retryable"],
            created_at=row["created_at"],
        )

    def get_upload_batch(self, batch_id: str, viewer: ViewerContext) -> UploadBatchSummary:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, workspace_id, source_kind, status, created_at, job_id,
                           total_items, accepted_items, rejected_items,
                           papers_analyzed, pairwise_completed, pairwise_pending
                    FROM upload_batches
                    WHERE id = %s
                    """,
                    (batch_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError(batch_id)
                self._assert_workspace_access(connection, row["workspace_id"], viewer)
                return self._batch_from_row(connection, row)

    def create_upload_batch(
        self, request: UploadBatchCreateRequest, viewer: ViewerContext
    ) -> UploadBatchCreateResponse:
        with self._connect() as connection:
            self._ensure_viewer_seed(connection, viewer)
            self._assert_workspace_access(connection, request.workspace_id, viewer)
            batch_id = f"batch-{uuid4().hex[:8]}"
            created_at = datetime.now(UTC)
            accepted_items = 0
            rejected_items = 0
            results: list[UploadItemResult] = []

            for index, item in enumerate(request.items):
                filename = item.filename.lower()
                if request.source_kind == UploadSourceKind.PDF_BATCH:
                    is_valid = filename.endswith(".pdf")
                    message = (
                        "Queued for PDF ingestion."
                        if is_valid
                        else "Rejected. Only PDF files are accepted in batch PDF mode."
                    )
                else:
                    is_valid = index == 0 and filename.endswith(".zip")
                    message = (
                        "Archive queued for expansion and de-duplication."
                        if is_valid
                        else "Rejected. ZIP import mode expects a single .zip archive."
                    )
                status = UploadItemStatus.ACCEPTED if is_valid else UploadItemStatus.REJECTED
                accepted_items += int(is_valid)
                rejected_items += int(not is_valid)
                results.append(
                    UploadItemResult(
                        filename=item.filename,
                        media_type=item.media_type,
                        size_bytes=item.size_bytes,
                        status=status,
                        message=message,
                    )
                )

            batch_status = BatchStatus.QUEUED if accepted_items else BatchStatus.REJECTED
            job: JobSummary | None = None
            job_id: str | None = None

            with connection.cursor() as cursor:
                if accepted_items:
                    job_id = f"job-{uuid4().hex[:8]}"
                    cursor.execute(
                        """
                        INSERT INTO jobs (
                          id, workspace_id, batch_id, job_type, status, progress_label,
                          completed_steps, total_steps, retryable, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            job_id,
                            request.workspace_id,
                            batch_id,
                            "batch_ingestion",
                            JobStatus.QUEUED,
                            f"{accepted_items} accepted item(s) queued for ingestion.",
                            0,
                            max(accepted_items + 2, 2),
                            True,
                            created_at,
                        ),
                    )
                    job = JobSummary(
                        job_id=job_id,
                        workspace_id=request.workspace_id,
                        batch_id=batch_id,
                        job_type="batch_ingestion",
                        status=JobStatus.QUEUED,
                        progress_label=f"{accepted_items} accepted item(s) queued for ingestion.",
                        completed_steps=0,
                        total_steps=max(accepted_items + 2, 2),
                        created_at=created_at,
                    )

                cursor.execute(
                    """
                    INSERT INTO upload_batches (
                      id, workspace_id, source_kind, status, created_at, job_id,
                      total_items, accepted_items, rejected_items,
                      papers_analyzed, pairwise_completed, pairwise_pending
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        batch_id,
                        request.workspace_id,
                        request.source_kind,
                        batch_status,
                        created_at,
                        job_id,
                        len(request.items),
                        accepted_items,
                        rejected_items,
                        0,
                        0,
                        0,
                    ),
                )
                for result in results:
                    cursor.execute(
                        """
                        INSERT INTO upload_batch_items (
                          batch_id, filename, media_type, size_bytes, status, message
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            batch_id,
                            result.filename,
                            result.media_type,
                            result.size_bytes,
                            result.status,
                            result.message,
                        ),
                    )
            connection.commit()

        batch = UploadBatchSummary(
            batch_id=batch_id,
            workspace_id=request.workspace_id,
            source_kind=request.source_kind,
            status=batch_status,
            created_at=created_at,
            job_id=job_id,
            progress=UploadBatchProgress(
                total_items=len(request.items),
                accepted_items=accepted_items,
                rejected_items=rejected_items,
                papers_analyzed=0,
                pairwise_completed=0,
                pairwise_pending=0,
            ),
            items=results,
        )
        return UploadBatchCreateResponse(batch=batch, job=job)

def get_repository_info() -> RepositoryInfo:
    return _select_repository()[1]


@lru_cache(maxsize=1)
def _select_repository() -> tuple[WorkspaceRepository, RepositoryInfo]:
    backend = settings.storage_backend.lower()
    allow_fallback = settings.allow_demo_fallback

    if backend == "memory":
        repo = InMemoryWorkspaceRepository()
        return repo, repo.info()

    if backend == "postgres" or (backend == "auto" and settings.database_url):
        if not settings.database_url:
            if allow_fallback:
                repo = InMemoryWorkspaceRepository()
                return repo, RepositoryInfo(
                    backend="in_memory",
                    detail="DATABASE_URL not set; using in-memory demo repository.",
                )
            raise RuntimeError("DATABASE_URL is required for Postgres storage backend")

        try:
            repo = PostgresWorkspaceRepository(settings.database_url)
            repo.ping()
            return repo, repo.info()
        except Exception as exc:
            if allow_fallback:
                demo = InMemoryWorkspaceRepository()
                return demo, RepositoryInfo(
                    backend="in_memory",
                    detail=f"Postgres unavailable ({exc}); using in-memory demo repository.",
                )
            raise

    repo = InMemoryWorkspaceRepository()
    return repo, repo.info()


def get_repository() -> WorkspaceRepository:
    return _select_repository()[0]
