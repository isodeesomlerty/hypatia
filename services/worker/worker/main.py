from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import psycopg
from psycopg.rows import dict_row

from research_graph.cache import load_manifest
from research_graph.config import CACHE_DIR as RG_CACHE_DIR
from research_graph.graph import aggregate_paper_edges
from research_graph.pipeline import (
    ClaudeAPIError,
    ResearchGraphError,
    _classify_pairwise_failure,
    analyze_pdf,
    compare_papers,
)
from worker.config import settings
from worker.storage import get_upload_materializer


SUPPORTED_JOB_TYPES = [
    "batch_ingestion",
    "paper_ingestion",
    "pairwise_comparison",
    "graph_rebuild",
    "replication_run",
]

PAIRWISE_RESOLUTION_TYPES = (
    "supports",
    "qualifies",
    "extends",
    "contradicts",
)


class SourceArtifactUnavailableError(ResearchGraphError):
    """Raised when V2 has no way to reconstruct a real paper record."""


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[_-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "Untitled upload"
    return cleaned.title()


def _connect():
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def _claim_job(connection, *, job_type: str, progress_label: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, workspace_id, batch_id, total_steps, payload
            FROM jobs
            WHERE job_type = %s AND status = 'queued'
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (job_type,),
        )
        job = cursor.fetchone()
        if job is None:
            return None
        cursor.execute(
            """
            UPDATE jobs
            SET status = 'in_progress',
                progress_label = %s,
                completed_steps = 0
            WHERE id = %s AND status = 'queued'
            """,
            (progress_label, job["id"]),
        )
        if cursor.rowcount != 1:
            return None
    connection.commit()
    return job


def _claim_batch_job(connection):
    return _claim_job(
        connection,
        job_type="batch_ingestion",
        progress_label="Worker claimed batch ingestion job.",
    )


def _claim_pairwise_job(connection):
    return _claim_job(
        connection,
        job_type="pairwise_comparison",
        progress_label="Worker claimed pairwise comparison job.",
    )


def _accepted_batch_items(connection, batch_id: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, filename, media_type, size_bytes, storage_backend, storage_key, sha256
            FROM upload_batch_items
            WHERE batch_id = %s AND status = 'accepted'
            ORDER BY id ASC
            """,
            (batch_id,),
        )
        return cursor.fetchall()


def _paper_exists(connection, workspace_id: str, sha256: str | None):
    if not sha256:
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM papers
            WHERE workspace_id = %s AND source_sha256 = %s
            """,
            (workspace_id, sha256),
        )
        return cursor.fetchone()


def _insert_paper(
    connection,
    workspace_id: str,
    item,
    analyzed_paper: dict | None = None,
) -> str:
    paper_id = f"paper-{uuid4().hex[:10]}"
    title = analyzed_paper.get("title") if analyzed_paper else None
    authors = analyzed_paper.get("authors") if analyzed_paper else []
    year = analyzed_paper.get("year") if analyzed_paper else None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO papers (
              id, workspace_id, title, authors, publication_year, status,
              source_filename, source_sha256, storage_backend, storage_key
            )
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
            """,
            (
                paper_id,
                workspace_id,
                title or _title_from_filename(item["filename"]),
                json.dumps(authors or []),
                year,
                "ready",
                item["filename"],
                item["sha256"],
                item["storage_backend"],
                item["storage_key"],
            ),
        )
    return paper_id


def _existing_relationship_pairs(connection, workspace_id: str) -> set[tuple[str, str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT source_paper_id, target_paper_id
            FROM paper_relationships
            WHERE workspace_id = %s
            """,
            (workspace_id,),
        )
        rows = cursor.fetchall()
    return {
        tuple(sorted((row["source_paper_id"], row["target_paper_id"])))
        for row in rows
    }


def _workspace_paper_ids(connection, workspace_id: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM papers
            WHERE workspace_id = %s
            ORDER BY id ASC
            """,
            (workspace_id,),
        )
        rows = cursor.fetchall()
    return [row["id"] for row in rows]


def _create_pending_relationships(
    connection,
    workspace_id: str,
    new_paper_ids: list[str],
) -> list[dict[str, str]]:
    if not new_paper_ids:
        return []

    existing_pairs = _existing_relationship_pairs(connection, workspace_id)
    workspace_paper_ids = _workspace_paper_ids(connection, workspace_id)
    created: list[dict[str, str]] = []

    with connection.cursor() as cursor:
        for source_id in new_paper_ids:
            for target_id in workspace_paper_ids:
                if source_id == target_id:
                    continue
                pair = tuple(sorted((source_id, target_id)))
                if pair in existing_pairs:
                    continue
                cursor.execute(
                    """
                    INSERT INTO paper_relationships (
                      id, workspace_id, source_paper_id, target_paper_id,
                      relationship_type, status, visible_strength
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        f"edge-{uuid4().hex[:10]}",
                        workspace_id,
                        pair[0],
                        pair[1],
                        "pending",
                        "pending",
                        1,
                    ),
                )
                relationship = cursor.fetchone()
                existing_pairs.add(pair)
                created.append(
                    {
                        "relationship_id": relationship["id"],
                        "source_paper_id": pair[0],
                        "target_paper_id": pair[1],
                    }
                )
        if created:
            cursor.execute(
                """
                UPDATE papers
                SET status = 'pairwise_pending'
                WHERE workspace_id = %s AND id = ANY(%s)
                """,
                (workspace_id, new_paper_ids),
            )
    return created


def _queue_pairwise_jobs(
    connection,
    workspace_id: str,
    batch_id: str,
    relationships: list[dict[str, str]],
) -> int:
    if not relationships:
        return 0

    created_at = datetime.now(UTC)
    with connection.cursor() as cursor:
        for relationship in relationships:
            relationship_id = relationship["relationship_id"]
            source_paper_id = relationship["source_paper_id"]
            target_paper_id = relationship["target_paper_id"]
            cursor.execute(
                """
                INSERT INTO jobs (
                  id, workspace_id, batch_id, job_type, payload, status, progress_label,
                  completed_steps, total_steps, retryable, created_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                """,
                (
                    f"job-{uuid4().hex[:8]}",
                    workspace_id,
                    batch_id,
                    "pairwise_comparison",
                    json.dumps(
                        {
                            "relationship_id": relationship_id,
                            "source_paper_id": source_paper_id,
                            "target_paper_id": target_paper_id,
                        }
                    ),
                    "queued",
                    (
                        "Queued pairwise comparison for "
                        f"{source_paper_id} and {target_paper_id}."
                    ),
                    0,
                    1,
                    True,
                    created_at,
                ),
            )
    return len(relationships)


def _update_batch_item_message(connection, item_id: int, message: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE upload_batch_items
            SET message = %s
            WHERE id = %s
            """,
            (message, item_id),
        )


def _complete_job(
    connection,
    job_id: str,
    *,
    status: str,
    progress_label: str,
    completed_steps: int,
    total_steps: int,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE jobs
            SET status = %s,
                progress_label = %s,
                completed_steps = %s,
                total_steps = %s
            WHERE id = %s
            """,
            (status, progress_label, completed_steps, total_steps, job_id),
        )


def _job_payload(job) -> dict[str, str]:
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        return json.loads(payload)
    return payload


def _count_batch_item_failures(connection, batch_id: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM upload_batch_items
            WHERE batch_id = %s
              AND (
                message LIKE %s
                OR message LIKE %s
              )
            """,
            (
                batch_id,
                "Stored file missing%",
                "Paper analysis failed:%",
            ),
        )
        row = cursor.fetchone()
    return int(row["count"]) if row is not None else 0


def _refresh_batch_progress(
    connection,
    batch_id: str,
    *,
    papers_analyzed: int | None = None,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT papers_analyzed
            FROM upload_batches
            WHERE id = %s
            """,
            (batch_id,),
        )
        batch = cursor.fetchone()
        if batch is None:
            return

        if papers_analyzed is None:
            papers_analyzed = batch["papers_analyzed"]

        cursor.execute(
            """
            SELECT
              COUNT(*) FILTER (
                WHERE job_type = 'pairwise_comparison' AND status = 'completed'
              ) AS pairwise_completed,
              COUNT(*) FILTER (
                WHERE job_type = 'pairwise_comparison' AND status IN ('queued', 'in_progress')
              ) AS pairwise_pending,
              COUNT(*) FILTER (
                WHERE job_type = 'pairwise_comparison' AND status = 'failed'
              ) AS pairwise_failed,
              COUNT(*) FILTER (
                WHERE job_type = 'batch_ingestion' AND status IN ('queued', 'in_progress')
              ) AS ingestion_active
            FROM jobs
            WHERE batch_id = %s
            """,
            (batch_id,),
        )
        stats = cursor.fetchone()

        pending = int(stats["pairwise_pending"])
        completed = int(stats["pairwise_completed"])
        failed = int(stats["pairwise_failed"])
        active_ingestion = int(stats["ingestion_active"])
        missing_files = _count_batch_item_failures(connection, batch_id)

        if active_ingestion or pending:
            status = "in_progress"
        elif failed or missing_files:
            status = "partial_failure"
        else:
            status = "completed"

        cursor.execute(
            """
            UPDATE upload_batches
            SET status = %s,
                papers_analyzed = %s,
                pairwise_completed = %s,
                pairwise_pending = %s
            WHERE id = %s
            """,
            (status, papers_analyzed, completed, pending, batch_id),
        )


def _load_pairwise_relationship(connection, workspace_id: str, relationship_id: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              pr.id,
              pr.source_paper_id,
              pr.target_paper_id,
              pr.status,
              source_paper.title AS source_title,
              target_paper.title AS target_title
            FROM paper_relationships pr
            JOIN papers source_paper ON source_paper.id = pr.source_paper_id
            JOIN papers target_paper ON target_paper.id = pr.target_paper_id
            WHERE pr.workspace_id = %s AND pr.id = %s
            """,
            (workspace_id, relationship_id),
        )
        return cursor.fetchone()


def _resolve_placeholder_pairwise_relationship(
    source_paper_id: str,
    target_paper_id: str,
) -> tuple[str, int]:
    digest = hashlib.sha256(
        f"{source_paper_id}:{target_paper_id}".encode("utf-8")
    ).digest()
    bucket = digest[0] % 10
    if bucket < 5:
        relationship_type = PAIRWISE_RESOLUTION_TYPES[0]
    elif bucket < 7:
        relationship_type = PAIRWISE_RESOLUTION_TYPES[1]
    elif bucket < 9:
        relationship_type = PAIRWISE_RESOLUTION_TYPES[2]
    else:
        relationship_type = PAIRWISE_RESOLUTION_TYPES[3]
    visible_strength = 2 + (digest[1] % 5)
    return relationship_type, visible_strength


def _refresh_paper_statuses(
    connection,
    workspace_id: str,
    paper_ids: list[str],
) -> None:
    if not paper_ids:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE papers AS paper
            SET status = CASE
              WHEN EXISTS (
                SELECT 1
                FROM paper_relationships relationship
                WHERE relationship.workspace_id = paper.workspace_id
                  AND (
                    relationship.source_paper_id = paper.id
                    OR relationship.target_paper_id = paper.id
                  )
                  AND relationship.status = 'pending'
              )
              THEN 'pairwise_pending'
              ELSE 'ready'
            END
            WHERE paper.workspace_id = %s
              AND paper.id = ANY(%s)
            """,
            (workspace_id, paper_ids),
        )


def _load_paper_row(connection, workspace_id: str, paper_id: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              id,
              workspace_id,
              title,
              authors,
              publication_year,
              status,
              source_filename,
              source_sha256,
              analysis_payload,
              storage_backend,
              storage_key
            FROM papers
            WHERE workspace_id = %s AND id = %s
            """,
            (workspace_id, paper_id),
        )
        return cursor.fetchone()


def _load_claim_rows(connection, workspace_id: str, paper_id: str) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, text, claim_type
            FROM claims
            WHERE workspace_id = %s AND paper_id = %s
            ORDER BY id ASC
            """,
            (workspace_id, paper_id),
        )
        return cursor.fetchall()


def _load_cached_analysis(source_sha256: str | None) -> dict | None:
    if not source_sha256:
        return None
    manifest = load_manifest()
    entry = manifest.get("papers_by_hash", {}).get(source_sha256)
    if not entry:
        return None
    relative_path = entry.get("paper_cache_path")
    if not relative_path:
        return None
    cache_path = RG_CACHE_DIR / relative_path
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_stored_analysis_payload(paper_row) -> dict | None:
    payload = paper_row.get("analysis_payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        return None
    return payload


def _stored_pdf_path_context(paper_row):
    storage_backend = paper_row.get("storage_backend")
    storage_key = paper_row.get("storage_key")
    if not storage_backend or not storage_key:
        return nullcontext(None)
    return get_upload_materializer().materialize(
        storage_backend=storage_backend,
        storage_key=storage_key,
    )


def _paper_record_from_claim_rows(paper_row, claim_rows: list[dict]) -> dict:
    return {
        "paper_id": paper_row["id"],
        "title": paper_row["title"],
        "authors": paper_row.get("authors") or [],
        "year": paper_row.get("publication_year"),
        "source_filename": paper_row.get("source_filename"),
        "claims": [
            {
                "claim_id": row["id"],
                "claim": row["text"],
                "claim_type": row.get("claim_type") or "descriptive",
                "evidence_type": "other",
                "evidence_strength": "moderate",
                "evidence_reasoning": "",
                "key_variables": [],
                "context": "",
            }
            for row in claim_rows
        ],
    }


def _sync_paper_analysis(
    connection,
    workspace_id: str,
    paper_id: str,
    analyzed_paper: dict,
    *,
    refresh_claims: bool,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE papers
            SET title = %s,
                authors = %s::jsonb,
                publication_year = %s,
                analysis_payload = %s::jsonb
            WHERE workspace_id = %s AND id = %s
            """,
            (
                analyzed_paper.get("title") or "Untitled paper",
                json.dumps(analyzed_paper.get("authors", [])),
                analyzed_paper.get("year"),
                json.dumps(analyzed_paper),
                workspace_id,
                paper_id,
            ),
        )

        if not refresh_claims:
            return

        cursor.execute(
            """
            DELETE FROM claims
            WHERE workspace_id = %s AND paper_id = %s
            """,
            (workspace_id, paper_id),
        )
        for claim in analyzed_paper.get("claims", []):
            cursor.execute(
                """
                INSERT INTO claims (id, workspace_id, paper_id, text, claim_type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    claim.get("claim_id"),
                    workspace_id,
                    paper_id,
                    claim.get("claim", "").strip(),
                    claim.get("claim_type", "descriptive"),
                ),
            )


def _should_refresh_claims(
    existing_claim_rows: list[dict],
    analyzed_paper: dict,
) -> bool:
    existing_ids = {row["id"] for row in existing_claim_rows}
    analyzed_ids = {
        claim.get("claim_id")
        for claim in analyzed_paper.get("claims", [])
        if claim.get("claim_id")
    }
    return existing_ids != analyzed_ids


def _load_runtime_paper_record(
    connection,
    workspace_id: str,
    paper_id: str,
) -> dict:
    paper_row = _load_paper_row(connection, workspace_id, paper_id)
    if paper_row is None:
        raise ResearchGraphError(f"Paper {paper_id} was not found in workspace {workspace_id}.")

    claim_rows = _load_claim_rows(connection, workspace_id, paper_id)
    stored_analysis = _load_stored_analysis_payload(paper_row)
    if stored_analysis is not None:
        _sync_paper_analysis(
            connection,
            workspace_id,
            paper_id,
            stored_analysis,
            refresh_claims=_should_refresh_claims(claim_rows, stored_analysis),
        )
        return stored_analysis

    cached_analysis = _load_cached_analysis(paper_row.get("source_sha256"))
    if cached_analysis is not None:
        _sync_paper_analysis(
            connection,
            workspace_id,
            paper_id,
            cached_analysis,
            refresh_claims=_should_refresh_claims(claim_rows, cached_analysis),
        )
        return cached_analysis

    try:
        with _stored_pdf_path_context(paper_row) as stored_path:
            if stored_path is not None:
                analyzed = analyze_pdf(
                    stored_path,
                    manifest=load_manifest(),
                    persist=False,
                    progress_callback=None,
                )
                _sync_paper_analysis(
                    connection,
                    workspace_id,
                    paper_id,
                    analyzed,
                    refresh_claims=_should_refresh_claims(claim_rows, analyzed),
                )
                return analyzed
    except (FileNotFoundError, RuntimeError):
        pass

    if claim_rows:
        return _paper_record_from_claim_rows(paper_row, claim_rows)

    raise SourceArtifactUnavailableError(
        f"Paper {paper_id} has no cached analysis, no stored source PDF, and no saved claims."
    )


def _replace_claim_relationships(
    connection,
    workspace_id: str,
    source_paper_id: str,
    target_paper_id: str,
    relationships: list[dict],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM claim_relationships
            WHERE workspace_id = %s
              AND source_claim_id IN (
                SELECT id FROM claims WHERE workspace_id = %s AND paper_id = %s
              )
              AND target_claim_id IN (
                SELECT id FROM claims WHERE workspace_id = %s AND paper_id = %s
              )
            """,
            (
                workspace_id,
                workspace_id,
                source_paper_id,
                workspace_id,
                target_paper_id,
            ),
        )
        for relationship in relationships:
            cursor.execute(
                """
                INSERT INTO claim_relationships (
                  id,
                  workspace_id,
                  source_claim_id,
                  target_claim_id,
                  relationship_type,
                  strength,
                  explanation,
                  methodological_note
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    f"claim-rel-{uuid4().hex[:10]}",
                    workspace_id,
                    relationship.get("source_claim_id"),
                    relationship.get("target_claim_id"),
                    relationship.get("relationship"),
                    relationship.get("relationship_strength"),
                    relationship.get("explanation", "").strip(),
                    relationship.get("methodological_note", "").strip(),
                ),
            )


def _aggregate_visual_relationship(
    source_paper_id: str,
    target_paper_id: str,
    source_paper: dict,
    target_paper: dict,
    relationships: list[dict],
) -> dict | None:
    aggregated = aggregate_paper_edges(
        relationships,
        {
            source_paper_id: {"claims": source_paper.get("claims", [])},
            target_paper_id: {"claims": target_paper.get("claims", [])},
        },
    )
    return aggregated.get(tuple(sorted((source_paper_id, target_paper_id))))


def process_next_batch_job() -> bool:
    with _connect() as connection:
        job = _claim_batch_job(connection)
        if job is None:
            return False

        workspace_id = job["workspace_id"]
        batch_id = job["batch_id"]
        total_steps = max(job["total_steps"], 1)
        if batch_id is None:
            _complete_job(
                connection,
                job["id"],
                status="failed",
                progress_label="Batch ingestion job was missing a batch reference.",
                completed_steps=0,
                total_steps=total_steps,
            )
            connection.commit()
            return True

        items = _accepted_batch_items(connection, batch_id)
        ingested = 0
        duplicates = 0
        missing_files = 0
        analysis_failures = 0
        new_paper_ids: list[str] = []
        analysis_manifest = load_manifest()

        for item in items:
            if not item["storage_key"] or not item["storage_backend"]:
                analysis_failures += 1
                _update_batch_item_message(
                    connection,
                    item["id"],
                    "Paper analysis failed: accepted item had no stored file reference.",
                )
                continue

            try:
                with get_upload_materializer().materialize(
                    storage_backend=item["storage_backend"],
                    storage_key=item["storage_key"],
                ) as stored_path:
                    existing = _paper_exists(connection, workspace_id, item["sha256"])
                    if existing is not None:
                        duplicates += 1
                        _update_batch_item_message(
                            connection,
                            item["id"],
                            f"Duplicate of existing paper {existing['id']}; not re-ingested.",
                        )
                        continue

                    analyzed_paper = analyze_pdf(
                        stored_path,
                        manifest=analysis_manifest,
                        persist=False,
                        progress_callback=None,
                    )
            except FileNotFoundError:
                missing_files += 1
                _update_batch_item_message(
                    connection,
                    item["id"],
                    "Stored file missing from configured upload storage; ingestion skipped.",
                )
                continue
            except Exception as exc:
                analysis_failures += 1
                _update_batch_item_message(
                    connection,
                    item["id"],
                    f"Paper analysis failed: {exc}",
                )
                continue

            paper_id = _insert_paper(
                connection,
                workspace_id,
                item,
                analyzed_paper=analyzed_paper,
            )
            _sync_paper_analysis(
                connection,
                workspace_id,
                paper_id,
                analyzed_paper,
                refresh_claims=True,
            )
            ingested += 1
            new_paper_ids.append(paper_id)
            _update_batch_item_message(
                connection,
                item["id"],
                f"Analyzed and ingested into workspace as {paper_id}.",
            )

        created_relationships = _create_pending_relationships(
            connection,
            workspace_id,
            new_paper_ids,
        )
        queued_pairwise_jobs = _queue_pairwise_jobs(
            connection,
            workspace_id,
            batch_id,
            created_relationships,
        )

        summary_bits = [f"{ingested} paper(s) ingested"]
        if duplicates:
            summary_bits.append(f"{duplicates} duplicate(s) skipped")
        if missing_files:
            summary_bits.append(f"{missing_files} stored file(s) missing")
        if analysis_failures:
            summary_bits.append(f"{analysis_failures} analysis failure(s)")
        if queued_pairwise_jobs:
            summary_bits.append(
                f"{queued_pairwise_jobs} pairwise comparison job(s) queued"
            )

        _complete_job(
            connection,
            job["id"],
            status="completed",
            progress_label=". ".join(summary_bits) + ".",
            completed_steps=total_steps,
            total_steps=total_steps,
        )
        _refresh_batch_progress(
            connection,
            batch_id,
            papers_analyzed=ingested,
        )
        connection.commit()
        return True


def process_next_pairwise_job() -> bool:
    with _connect() as connection:
        job = _claim_pairwise_job(connection)
        if job is None:
            return False

        total_steps = max(job["total_steps"], 1)
        batch_id = job["batch_id"]
        payload = _job_payload(job)
        relationship_id = payload.get("relationship_id")
        source_paper_id = payload.get("source_paper_id")
        target_paper_id = payload.get("target_paper_id")

        if not relationship_id or not source_paper_id or not target_paper_id:
            _complete_job(
                connection,
                job["id"],
                status="failed",
                progress_label="Pairwise comparison job payload was incomplete.",
                completed_steps=0,
                total_steps=total_steps,
            )
            if batch_id:
                _refresh_batch_progress(connection, batch_id)
            connection.commit()
            return True

        relationship = _load_pairwise_relationship(
            connection,
            job["workspace_id"],
            relationship_id,
        )
        if relationship is None:
            _complete_job(
                connection,
                job["id"],
                status="failed",
                progress_label="Referenced paper relationship could not be found.",
                completed_steps=0,
                total_steps=total_steps,
            )
            if batch_id:
                _refresh_batch_progress(connection, batch_id)
            connection.commit()
            return True

        used_placeholder = False
        relationship_type = "pending"
        visible_strength = 1
        comparison_label = ""
        visual_edge: dict | None = None

        try:
            source_paper = _load_runtime_paper_record(
                connection,
                job["workspace_id"],
                source_paper_id,
            )
            target_paper = _load_runtime_paper_record(
                connection,
                job["workspace_id"],
                target_paper_id,
            )
            claim_relationships = compare_papers(source_paper, target_paper)
            _replace_claim_relationships(
                connection,
                job["workspace_id"],
                source_paper_id,
                target_paper_id,
                claim_relationships,
            )
            visual_edge = _aggregate_visual_relationship(
                source_paper_id,
                target_paper_id,
                source_paper,
                target_paper,
                claim_relationships,
            )
            if visual_edge is not None:
                relationship_type = visual_edge["dominant"]
                visible_strength = min(max(int(visual_edge.get("total_weight", 1)), 1), 10)
                comparison_label = (
                    "Resolved pairwise comparison for "
                    f"{relationship['source_title']} and {relationship['target_title']} "
                    f"as {relationship_type} from {len(claim_relationships)} claim link(s)."
                )
            else:
                comparison_label = (
                    "Compared "
                    f"{relationship['source_title']} and {relationship['target_title']} "
                    "but found no visual paper-level relationship."
                )
        except SourceArtifactUnavailableError:
            used_placeholder = True
            relationship_type, visible_strength = _resolve_placeholder_pairwise_relationship(
                source_paper_id,
                target_paper_id,
            )
            comparison_label = (
                "Resolved pairwise comparison for "
                f"{relationship['source_title']} and {relationship['target_title']} "
                "using the legacy placeholder path because one paper lacks source artifacts."
            )
        except (ResearchGraphError, ClaudeAPIError, Exception) as exc:
            error_kind, retryable = _classify_pairwise_failure(exc)
            _complete_job(
                connection,
                job["id"],
                status="failed",
                progress_label=(
                    "Pairwise comparison failed "
                    f"({error_kind}): {str(exc).strip() or 'unknown error'}"
                ),
                completed_steps=0,
                total_steps=total_steps,
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET retryable = %s
                    WHERE id = %s
                    """,
                    (retryable, job["id"]),
                )
            if batch_id:
                _refresh_batch_progress(connection, batch_id)
            connection.commit()
            return True

        with connection.cursor() as cursor:
            if visual_edge is not None or used_placeholder:
                cursor.execute(
                    """
                    UPDATE paper_relationships
                    SET relationship_type = %s,
                        status = 'ready',
                        visible_strength = %s
                    WHERE id = %s
                    """,
                    (relationship_type, visible_strength, relationship_id),
                )
            else:
                cursor.execute(
                    """
                    DELETE FROM paper_relationships
                    WHERE id = %s
                    """,
                    (relationship_id,),
                )

        _refresh_paper_statuses(
            connection,
            job["workspace_id"],
            [source_paper_id, target_paper_id],
        )
        _complete_job(
            connection,
            job["id"],
            status="completed",
            progress_label=comparison_label,
            completed_steps=total_steps,
            total_steps=total_steps,
        )
        if batch_id:
            _refresh_batch_progress(connection, batch_id)
        connection.commit()
        return True


def process_next_queued_job() -> bool:
    return process_next_batch_job() or process_next_pairwise_job()


def run_loop(poll_interval_seconds: float) -> None:
    while True:
        worked = process_next_queued_job()
        if not worked:
            time.sleep(poll_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hypatia background worker service.")
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the current worker responsibilities as JSON.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued worker job and exit.",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Continuously poll for queued worker jobs.",
    )
    args = parser.parse_args()

    if args.describe:
        print(
            json.dumps(
                {
                    "service": "hypatia-worker",
                    "job_types": SUPPORTED_JOB_TYPES,
                    "notes": (
                        "This service executes real batch ingestion and pairwise "
                        "comparison jobs when source PDFs and Anthropic access are "
                        "available, with a narrow placeholder fallback for legacy "
                        "papers that lack source artifacts."
                    ),
                    "database_url": settings.database_url,
                    "upload_storage_backend": settings.upload_storage_backend,
                    "upload_storage_root": settings.upload_storage_root,
                    "upload_storage_s3_bucket": settings.upload_storage_s3_bucket,
                },
                indent=2,
            )
        )
        return

    if args.once:
        processed = process_next_queued_job()
        print("Processed one queued worker job." if processed else "No queued worker jobs found.")
        return

    if args.poll:
        run_loop(settings.poll_interval_seconds)
        return

    print("Hypatia worker is ready. Run with --describe, --once, or --poll.")


if __name__ == "__main__":
    main()
