CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  display_name TEXT NOT NULL,
  auth_mode TEXT NOT NULL,
  default_workspace_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_memberships (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  PRIMARY KEY (user_id, workspace_id)
);

CREATE TABLE IF NOT EXISTS papers (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  authors JSONB NOT NULL DEFAULT '[]'::jsonb,
  publication_year INTEGER,
  status TEXT NOT NULL,
  source_filename TEXT,
  source_sha256 TEXT,
  analysis_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  storage_backend TEXT,
  storage_key TEXT
);

CREATE TABLE IF NOT EXISTS paper_relationships (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  source_paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  target_paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL,
  status TEXT NOT NULL,
  visible_strength INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  batch_id TEXT,
  job_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL,
  progress_label TEXT NOT NULL,
  completed_steps INTEGER NOT NULL DEFAULT 0,
  total_steps INTEGER NOT NULL DEFAULT 0,
  retryable BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS upload_batches (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  source_kind TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  job_id TEXT,
  total_items INTEGER NOT NULL DEFAULT 0,
  accepted_items INTEGER NOT NULL DEFAULT 0,
  rejected_items INTEGER NOT NULL DEFAULT 0,
  papers_analyzed INTEGER NOT NULL DEFAULT 0,
  pairwise_completed INTEGER NOT NULL DEFAULT 0,
  pairwise_pending INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS upload_batch_items (
  id BIGSERIAL PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES upload_batches(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  media_type TEXT,
  size_bytes BIGINT,
  storage_backend TEXT,
  storage_key TEXT,
  sha256 TEXT,
  status TEXT NOT NULL,
  message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  claim_type TEXT,
  evidence_type TEXT,
  evidence_strength TEXT,
  evidence_reasoning TEXT,
  key_variables JSONB NOT NULL DEFAULT '[]'::jsonb,
  context TEXT NOT NULL DEFAULT '',
  search_text TEXT NOT NULL DEFAULT '',
  search_embedding JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS claim_relationships (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  source_claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  target_claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL,
  strength TEXT,
  explanation TEXT,
  methodological_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_papers_workspace_id ON papers(workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_workspace_sha256
  ON papers(workspace_id, source_sha256)
  WHERE source_sha256 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_workspace_id ON jobs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_upload_batches_workspace_id ON upload_batches(workspace_id);
CREATE INDEX IF NOT EXISTS idx_paper_relationships_workspace_id ON paper_relationships(workspace_id);
CREATE INDEX IF NOT EXISTS idx_claims_workspace_id ON claims(workspace_id);
CREATE INDEX IF NOT EXISTS idx_claims_workspace_paper_id ON claims(workspace_id, paper_id);
CREATE INDEX IF NOT EXISTS idx_claims_search_text
  ON claims USING GIN (to_tsvector('simple', search_text));
