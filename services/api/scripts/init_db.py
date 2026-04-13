from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:  # pragma: no cover - local bootstrap guard
    psycopg = None


DEFAULT_DATABASE_URL = "postgresql://hypatia:hypatia@127.0.0.1:5432/hypatia"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "app" / "schema.sql"
EMBEDDING_DIMENSIONS = int(os.getenv("HYPATIA_SEARCH_EMBEDDING_DIMENSIONS", "256"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply the initial Hypatia V2 Postgres schema.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="Postgres connection string. Defaults to DATABASE_URL or the local v2 compose database.",
    )
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Insert a small demo workspace, papers, edges, jobs, and upload batch after applying the schema.",
    )
    return parser.parse_args()


def iter_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    for line in script.splitlines():
        if not line.strip():
            continue
        buffer.append(line)
        if line.strip().endswith(";"):
            statements.append("\n".join(buffer))
            buffer = []
    if buffer:
        statements.append("\n".join(buffer))
    return statements


def apply_schema(connection) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = iter_sql_statements(schema_sql)
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
        cursor.execute(
            """
            ALTER TABLE papers
            ADD COLUMN IF NOT EXISTS source_sha256 TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE papers
            ADD COLUMN IF NOT EXISTS analysis_payload JSONB NOT NULL DEFAULT '{}'::jsonb
            """
        )
        cursor.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb
            """
        )
        cursor.execute(
            """
            ALTER TABLE papers
            ADD COLUMN IF NOT EXISTS storage_backend TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE papers
            ADD COLUMN IF NOT EXISTS storage_key TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE upload_batch_items
            ADD COLUMN IF NOT EXISTS storage_backend TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE upload_batch_items
            ADD COLUMN IF NOT EXISTS storage_key TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE upload_batch_items
            ADD COLUMN IF NOT EXISTS sha256 TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE claims
            ADD COLUMN IF NOT EXISTS evidence_type TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE claims
            ADD COLUMN IF NOT EXISTS evidence_strength TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE claims
            ADD COLUMN IF NOT EXISTS evidence_reasoning TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE claims
            ADD COLUMN IF NOT EXISTS key_variables JSONB NOT NULL DEFAULT '[]'::jsonb
            """
        )
        cursor.execute(
            """
            ALTER TABLE claims
            ADD COLUMN IF NOT EXISTS context TEXT NOT NULL DEFAULT ''
            """
        )
        cursor.execute(
            """
            ALTER TABLE claims
            ADD COLUMN IF NOT EXISTS search_text TEXT NOT NULL DEFAULT ''
            """
        )
        cursor.execute(
            """
            ALTER TABLE claims
            ADD COLUMN IF NOT EXISTS search_embedding JSONB NOT NULL DEFAULT '[]'::jsonb
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_workspace_sha256
            ON papers(workspace_id, source_sha256)
            WHERE source_sha256 IS NOT NULL
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_claims_workspace_id
            ON claims(workspace_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_claims_workspace_paper_id
            ON claims(workspace_id, paper_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_claims_search_text
            ON claims USING GIN (to_tsvector('simple', search_text))
            """
        )
        cursor.execute("SAVEPOINT hypatia_vector_setup")
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                """
                ALTER TABLE claims
                ADD COLUMN IF NOT EXISTS search_embedding_vector VECTOR(%s)
                """
                % EMBEDDING_DIMENSIONS
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_claims_search_embedding_vector
                ON claims USING hnsw (search_embedding_vector vector_cosine_ops)
                """
            )
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT hypatia_vector_setup")
        finally:
            cursor.execute("RELEASE SAVEPOINT hypatia_vector_setup")


def seed_demo_data(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO workspaces (id, name)
            VALUES
              ('demo', 'Behavioral AI Research'),
              ('cognitive-lab', 'Cognitive Influence Lab')
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name
            """
        )
        cursor.execute(
            """
            INSERT INTO users (id, email, display_name, auth_mode, default_workspace_id)
            VALUES ('demo-user', 'demo@hypatia.app', 'Hypatia Demo User', 'development', 'demo')
            ON CONFLICT (id) DO UPDATE
            SET email = EXCLUDED.email,
                display_name = EXCLUDED.display_name,
                auth_mode = EXCLUDED.auth_mode,
                default_workspace_id = EXCLUDED.default_workspace_id
            """
        )
        cursor.execute(
            """
            INSERT INTO workspace_memberships (user_id, workspace_id, role)
            VALUES
              ('demo-user', 'demo', 'owner'),
              ('demo-user', 'cognitive-lab', 'member')
            ON CONFLICT (user_id, workspace_id) DO UPDATE
            SET role = EXCLUDED.role
            """
        )
        cursor.execute(
            """
            INSERT INTO papers (id, workspace_id, title, authors, publication_year, status, source_filename)
            VALUES
              (
                'paper-1',
                'demo',
                'Biased AI writing assistants shift users'' attitudes on societal issues',
                '["Kobe Xie", "Robert Mahari"]'::jsonb,
                2026,
                'ready',
                'biased-writing-assistants.pdf'
              ),
              (
                'paper-2',
                'demo',
                'Sycophantic AI decreases prosocial intentions and promotes dependence',
                '["Myra Cheng", "Dan Jurafsky"]'::jsonb,
                2026,
                'pairwise_pending',
                'sycophantic-ai.pdf'
              ),
              (
                'paper-3',
                'demo',
                'Using Large Language Models in Behavioral Science',
                '["Lena Park", "Jonah Everett"]'::jsonb,
                2025,
                'ready',
                'behavioral-llms.pdf'
              ),
              (
                'paper-4',
                'cognitive-lab',
                'How AI can fuel confirmation bias',
                '["Steve Rathje", "Jay Van Bavel"]'::jsonb,
                2025,
                'analyzing',
                'confirmation-bias.pdf'
              )
            ON CONFLICT (id) DO UPDATE
            SET workspace_id = EXCLUDED.workspace_id,
                title = EXCLUDED.title,
                authors = EXCLUDED.authors,
                publication_year = EXCLUDED.publication_year,
                status = EXCLUDED.status,
                source_filename = EXCLUDED.source_filename
            """
        )
        cursor.execute(
            """
            INSERT INTO paper_relationships (
              id, workspace_id, source_paper_id, target_paper_id,
              relationship_type, status, visible_strength
            )
            VALUES
              ('edge-1', 'demo', 'paper-1', 'paper-2', 'supports', 'ready', 9),
              ('edge-2', 'demo', 'paper-2', 'paper-3', 'contradicts', 'pending', 2)
            ON CONFLICT (id) DO UPDATE
            SET workspace_id = EXCLUDED.workspace_id,
                source_paper_id = EXCLUDED.source_paper_id,
                target_paper_id = EXCLUDED.target_paper_id,
                relationship_type = EXCLUDED.relationship_type,
                status = EXCLUDED.status,
                visible_strength = EXCLUDED.visible_strength
            """
        )
        cursor.execute(
            """
            INSERT INTO jobs (
              id, workspace_id, batch_id, job_type, status, progress_label,
              completed_steps, total_steps, retryable, created_at
            )
            VALUES
              (
                'job-demo-ingest',
                'demo',
                'batch-demo-ingest',
                'batch_ingestion',
                'in_progress',
                '2 of 3 papers analyzed; pairwise comparisons queued',
                2,
                5,
                TRUE,
                '2026-04-12T13:30:00Z'
              ),
              (
                'job-demo-search',
                'demo',
                NULL,
                'graph_rebuild',
                'queued',
                'Waiting for current ingestion batch to finish',
                0,
                1,
                TRUE,
                '2026-04-12T13:42:00Z'
              ),
              (
                'job-cognitive-analyze',
                'cognitive-lab',
                'batch-cognitive-ingest',
                'paper_ingestion',
                'in_progress',
                'Extracting claims from one newly added paper',
                1,
                3,
                TRUE,
                '2026-04-12T14:10:00Z'
              )
            ON CONFLICT (id) DO UPDATE
            SET workspace_id = EXCLUDED.workspace_id,
                batch_id = EXCLUDED.batch_id,
                job_type = EXCLUDED.job_type,
                status = EXCLUDED.status,
                progress_label = EXCLUDED.progress_label,
                completed_steps = EXCLUDED.completed_steps,
                total_steps = EXCLUDED.total_steps,
                retryable = EXCLUDED.retryable,
                created_at = EXCLUDED.created_at
            """
        )
        cursor.execute(
            """
            INSERT INTO upload_batches (
              id, workspace_id, source_kind, status, created_at, job_id,
              total_items, accepted_items, rejected_items,
              papers_analyzed, pairwise_completed, pairwise_pending
            )
            VALUES
              (
                'batch-demo-ingest',
                'demo',
                'pdf_batch',
                'in_progress',
                '2026-04-12T13:30:00Z',
                'job-demo-ingest',
                4,
                3,
                1,
                2,
                1,
                2
              ),
              (
                'batch-cognitive-ingest',
                'cognitive-lab',
                'zip_import',
                'in_progress',
                '2026-04-12T14:10:00Z',
                'job-cognitive-analyze',
                1,
                1,
                0,
                0,
                0,
                0
              )
            ON CONFLICT (id) DO UPDATE
            SET workspace_id = EXCLUDED.workspace_id,
                source_kind = EXCLUDED.source_kind,
                status = EXCLUDED.status,
                created_at = EXCLUDED.created_at,
                job_id = EXCLUDED.job_id,
                total_items = EXCLUDED.total_items,
                accepted_items = EXCLUDED.accepted_items,
                rejected_items = EXCLUDED.rejected_items,
                papers_analyzed = EXCLUDED.papers_analyzed,
                pairwise_completed = EXCLUDED.pairwise_completed,
                pairwise_pending = EXCLUDED.pairwise_pending
            """
        )
        cursor.execute(
            """
            DELETE FROM upload_batch_items
            WHERE batch_id IN ('batch-demo-ingest', 'batch-cognitive-ingest')
            """
        )
        cursor.execute(
            """
            INSERT INTO upload_batch_items (
              batch_id, filename, media_type, size_bytes, status, message
            )
            VALUES
              (
                'batch-demo-ingest',
                'biased-writing-assistants.pdf',
                'application/pdf',
                4100000,
                'accepted',
                'Claim extraction completed.'
              ),
              (
                'batch-demo-ingest',
                'sycophantic-ai.pdf',
                'application/pdf',
                5600000,
                'accepted',
                'Pairwise comparison backlog is still running.'
              ),
              (
                'batch-demo-ingest',
                'behavioral-llms.pdf',
                'application/pdf',
                6200000,
                'accepted',
                'Queued for paper analysis.'
              ),
              (
                'batch-demo-ingest',
                'notes.txt',
                'text/plain',
                900,
                'rejected',
                'Unsupported file type. Batch ingestion accepts PDFs or a ZIP archive.'
              ),
              (
                'batch-cognitive-ingest',
                'cognitive-import.zip',
                'application/zip',
                7200000,
                'accepted',
                'Archive queued for expansion and de-duplication.'
              )
            """
        )


def main() -> int:
    args = parse_args()
    if psycopg is None:
        print("psycopg is not installed. Install the API dependencies first.", file=sys.stderr)
        return 1

    if not args.database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 1

    with psycopg.connect(args.database_url) as connection:
        apply_schema(connection)
        if args.seed_demo:
            seed_demo_data(connection)
        connection.commit()

    print(f"Applied schema from {SCHEMA_PATH}.")
    if args.seed_demo:
        print("Seeded demo workspace data.")
    print(f"Connected database: {args.database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
