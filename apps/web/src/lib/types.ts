export type RelationshipStatus = "ready" | "pending";

export type GraphNode = {
  id: string;
  label: string;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  status: RelationshipStatus;
  visible_strength: number;
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type WorkspaceSummary = {
  workspace_id: string;
  name: string;
  paper_count: number;
  active_batch_count: number;
  active_job_count: number;
};

export type WorkspaceAccessSummary = {
  workspace_id: string;
  name: string;
  role: string;
};

export type ViewerSummary = {
  user_id: string;
  email: string;
  display_name: string;
  auth_mode: string;
  default_workspace_id: string;
  workspaces: WorkspaceAccessSummary[];
};

export type WorkspaceGraphResponse = {
  workspace_id: string;
  graph: GraphPayload;
};

export type PaperSummary = {
  paper_id: string;
  title: string;
  authors: string[];
  year: number | null;
  status: string;
  source_filename: string | null;
};

export type WorkspacePaperListResponse = {
  workspace_id: string;
  papers: PaperSummary[];
};

export type MethodologyCheck = {
  check: string;
  status: string;
  detail: string;
};

export type HealthScoreSummary = {
  overall_score: string;
  checks: MethodologyCheck[];
};

export type ClaimDetail = {
  claim_id: string;
  text: string;
  claim_type: string;
  evidence_type: string;
  evidence_strength: string;
  evidence_reasoning: string;
  key_variables: string[];
  context: string;
};

export type PaperDetail = {
  paper_id: string;
  title: string;
  authors: string[];
  year: number | null;
  status: string;
  source_filename: string | null;
  ingestion_mode: string | null;
  page_count: number | null;
  file_size_mb: number | null;
  health_score: HealthScoreSummary;
  claims: ClaimDetail[];
};

export type PaperDetailResponse = {
  workspace_id: string;
  paper: PaperDetail;
};

export type JobSummary = {
  job_id: string;
  workspace_id: string;
  batch_id: string | null;
  job_type: string;
  status: string;
  progress_label: string;
  completed_steps: number;
  total_steps: number;
  retryable: boolean;
  created_at: string;
};

export type WorkspaceJobListResponse = {
  workspace_id: string;
  jobs: JobSummary[];
};

export type UploadItemResult = {
  filename: string;
  media_type: string | null;
  size_bytes: number | null;
  status: "accepted" | "rejected";
  message: string;
};

export type UploadBatchProgress = {
  total_items: number;
  accepted_items: number;
  rejected_items: number;
  papers_analyzed: number;
  pairwise_completed: number;
  pairwise_pending: number;
};

export type UploadBatchSummary = {
  batch_id: string;
  workspace_id: string;
  source_kind: "pdf_batch" | "zip_import";
  status: string;
  created_at: string;
  job_id: string | null;
  progress: UploadBatchProgress;
  items: UploadItemResult[];
};

export type WorkspaceBatchListResponse = {
  workspace_id: string;
  batches: UploadBatchSummary[];
};

export type RelationshipAggregate = {
  supports: number;
  contradicts: number;
  extends: number;
  qualifies: number;
  total: number;
  dominant: string | null;
};

export type ClaimRelationshipDetail = {
  claim_relationship_id: string;
  source_claim_id: string;
  source_claim_text: string;
  target_claim_id: string;
  target_claim_text: string;
  relationship: string;
  relationship_strength: string;
  explanation: string;
  methodological_note: string;
};

export type RelationshipAttempt = {
  job_id: string;
  status: string;
  progress_label: string;
  retryable: boolean;
  created_at: string;
  error_kind: string | null;
};

export type PaperRelationshipDetail = {
  relationship_id: string;
  workspace_id: string;
  relationship_type: string;
  status: RelationshipStatus;
  visible_strength: number;
  source_paper: PaperSummary;
  target_paper: PaperSummary;
  aggregate: RelationshipAggregate;
  claim_relationships: ClaimRelationshipDetail[];
  last_attempt: RelationshipAttempt | null;
};

export type PaperRelationshipDetailResponse = {
  workspace_id: string;
  relationship: PaperRelationshipDetail;
};

export type APIMetaResponse = {
  name: string;
  version: string;
  environment: string;
  auth_strategy: string;
  storage_strategy: string;
  active_storage_backend: string;
  storage_detail: string;
};

export type WorkspaceBundle = {
  meta: APIMetaResponse;
  viewer: ViewerSummary;
  summary: WorkspaceSummary;
  graph: WorkspaceGraphResponse;
  papers: WorkspacePaperListResponse;
  jobs: WorkspaceJobListResponse;
  batches: WorkspaceBatchListResponse;
};
