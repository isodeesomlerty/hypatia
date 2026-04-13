from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from worker.config import settings


SUPPORTED_JOB_TYPES = [
    "batch_ingestion",
    "paper_ingestion",
    "pairwise_comparison",
    "graph_rebuild",
    "replication_run",
]


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[_-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "Untitled upload"
    return cleaned.title()


def _connect():
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def _claim_batch_job(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, workspace_id, batch_id, total_steps
            FROM jobs
            WHERE job_type = 'batch_ingestion' AND status = 'queued'
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        job = cursor.fetchone()
        if job is None:
            return None
        cursor.execute(
            """
            UPDATE jobs
            SET status = 'in_progress',
                progress_label = 'Worker claimed batch ingestion job.',
                completed_steps = 0
            WHERE id = %s AND status = 'queued'
            """,
            (job["id"],),
        )
        if cursor.rowcount != 1:
            return None
    connection.commit()
    return job


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


def _insert_paper(connection, workspace_id: str, item) -> str:
    paper_id = f"paper-{uuid4().hex[:10]}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO papers (
              id, workspace_id, title, authors, publication_year, status,
              source_filename, source_sha256, storage_backend, storage_key
            )
            VALUES (%s, %s, %s, '[]'::jsonb, %s, %s, %s, %s, %s, %s)
            """,
            (
                paper_id,
                workspace_id,
                _title_from_filename(item["filename"]),
                None,
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
) -> int:
    if not new_paper_ids:
        return 0

    existing_pairs = _existing_relationship_pairs(connection, workspace_id)
    workspace_paper_ids = _workspace_paper_ids(connection, workspace_id)
    inserted = 0

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
                existing_pairs.add(pair)
                inserted += 1
        if inserted:
            cursor.execute(
                """
                UPDATE papers
                SET status = 'pairwise_pending'
                WHERE workspace_id = %s AND id = ANY(%s)
                """,
                (workspace_id, new_paper_ids),
            )
    return inserted


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


def _complete_job(connection, job_id: str, *, status: str, progress_label: str, completed_steps: int, total_steps: int) -> None:
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


def _update_batch_summary(
    connection,
    batch_id: str,
    *,
    status: str,
    papers_analyzed: int,
    pairwise_pending: int,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE upload_batches
            SET status = %s,
                papers_analyzed = %s,
                pairwise_pending = %s
            WHERE id = %s
            """,
            (status, papers_analyzed, pairwise_pending, batch_id),
        )


def process_next_batch_job() -> bool:
    with _connect() as connection:
        job = _claim_batch_job(connection)
        if job is None:
            return False

        workspace_id = job["workspace_id"]
        batch_id = job["batch_id"]
        total_steps = job["total_steps"]
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
        new_paper_ids: list[str] = []

        for item in items:
            storage_key = item["storage_key"]
            if storage_key:
                stored_path = Path(settings.upload_storage_root) / storage_key
                if not stored_path.exists():
                    missing_files += 1
                    _update_batch_item_message(
                        connection,
                        item["id"],
                        "Stored file missing from local upload storage; ingestion skipped.",
                    )
                    continue

            existing = _paper_exists(connection, workspace_id, item["sha256"])
            if existing is not None:
                duplicates += 1
                _update_batch_item_message(
                    connection,
                    item["id"],
                    f"Duplicate of existing paper {existing['id']}; not re-ingested.",
                )
                continue

            paper_id = _insert_paper(connection, workspace_id, item)
            ingested += 1
            new_paper_ids.append(paper_id)
            _update_batch_item_message(
                connection,
                item["id"],
                f"Ingested into workspace as {paper_id}.",
            )

        pairwise_pending = _create_pending_relationships(connection, workspace_id, new_paper_ids)
        batch_status = "partial_failure" if missing_files else "completed"
        summary_bits = [f"{ingested} paper(s) ingested"]
        if duplicates:
            summary_bits.append(f"{duplicates} duplicate(s) skipped")
        if missing_files:
            summary_bits.append(f"{missing_files} stored file(s) missing")
        if pairwise_pending:
            summary_bits.append(
                f"{pairwise_pending} pairwise comparison(s) remain pending"
            )

        _update_batch_summary(
            connection,
            batch_id,
            status=batch_status,
            papers_analyzed=ingested,
            pairwise_pending=pairwise_pending,
        )
        _complete_job(
            connection,
            job["id"],
            status="completed",
            progress_label=". ".join(summary_bits) + ".",
            completed_steps=total_steps,
            total_steps=total_steps,
        )
        connection.commit()
        return True


def run_loop(poll_interval_seconds: float) -> None:
    while True:
        worked = process_next_batch_job()
        if not worked:
            time.sleep(poll_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hypatia worker service placeholder.")
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the current worker responsibilities as JSON.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued batch ingestion job and exit.",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Continuously poll for queued batch ingestion jobs.",
    )
    args = parser.parse_args()

    if args.describe:
        print(
            json.dumps(
                {
                    "service": "hypatia-worker",
                    "job_types": SUPPORTED_JOB_TYPES,
                    "notes": "This service executes background ingestion now, with pairwise comparison, graph rebuild, and replication tasks to follow.",
                    "database_url": settings.database_url,
                    "upload_storage_root": settings.upload_storage_root,
                },
                indent=2,
            )
        )
        return

    if args.once:
        processed = process_next_batch_job()
        print("Processed one queued batch job." if processed else "No queued batch jobs found.")
        return

    if args.poll:
        run_loop(settings.poll_interval_seconds)
        return

    print(
        "Hypatia worker is ready. Run with --describe, --once, or --poll."
    )


if __name__ == "__main__":
    main()
