import type {
  APIMetaResponse,
  GraphPayload,
  JobSummary,
  UploadBatchSummary,
  ViewerSummary,
  WorkspaceBatchListResponse,
  WorkspaceBundle,
  WorkspaceGraphResponse,
  WorkspaceJobListResponse,
  WorkspacePaperListResponse,
  WorkspaceSummary,
} from "./types";

export const visibleLayers = [
  "Supports",
  "Contradicts",
  "Extends",
  "Qualifies",
  "Pending",
];

export const uploadModes = [
  {
    title: "Batch PDF upload",
    description:
      "Upload many academic PDFs at once and let the worker queue analyze them asynchronously.",
    note: "Best for a researcher’s local paper folder.",
  },
  {
    title: "ZIP import",
    description:
      "Drop a single archive and let Hypatia expand, validate, and de-duplicate it before processing.",
    note: "Best for a shared export or reading list bundle.",
  },
  {
    title: "Google Drive later",
    description:
      "Drive import is planned after the local folder and ZIP workflow feels solid and reliable.",
    note: "Not in the first production milestone.",
  },
] as const;

export function buildDemoMeta(): APIMetaResponse {
  return {
    name: "Hypatia API",
    version: "0.1.0",
    environment: "development",
    auth_strategy: "Clerk + Google OAuth (development header fallback enabled)",
    storage_strategy: "Postgres + object storage + workers",
    active_storage_backend: "in_memory",
    storage_detail: "Using in-memory demo repository fallback.",
  };
}

function buildGraph(): GraphPayload {
  return {
    nodes: [
      { id: "paper-1", label: "Biased AI assistants" },
      { id: "paper-2", label: "Sycophantic AI" },
      { id: "paper-3", label: "LLMs in behavioral science" },
    ],
    edges: [
      {
        id: "edge-1",
        source: "paper-1",
        target: "paper-2",
        relationship_type: "supports",
        status: "ready",
        visible_strength: 9,
      },
      {
        id: "edge-2",
        source: "paper-2",
        target: "paper-3",
        relationship_type: "contradicts",
        status: "pending",
        visible_strength: 2,
      },
    ],
  };
}

function buildJobs(workspaceId: string): JobSummary[] {
  return [
    {
      job_id: "job-demo-ingest",
      workspace_id: workspaceId,
      batch_id: "batch-demo-ingest",
      job_type: "batch_ingestion",
      status: "in_progress",
      progress_label:
        "2 of 3 accepted papers analyzed; graph rebuild queued after pairwise pass.",
      completed_steps: 2,
      total_steps: 5,
      retryable: true,
      created_at: "2026-04-12T13:30:00Z",
    },
    {
      job_id: "job-demo-pairwise",
      workspace_id: workspaceId,
      batch_id: "batch-demo-ingest",
      job_type: "pairwise_comparison",
      status: "queued",
      progress_label:
        "Retryable failures stay pending and visible instead of disappearing from the graph.",
      completed_steps: 0,
      total_steps: 2,
      retryable: true,
      created_at: "2026-04-12T13:42:00Z",
    },
    {
      job_id: "job-demo-rebuild",
      workspace_id: workspaceId,
      batch_id: null,
      job_type: "graph_rebuild",
      status: "queued",
      progress_label:
        "Visible once the worker updates paper and relationship aggregates.",
      completed_steps: 0,
      total_steps: 1,
      retryable: true,
      created_at: "2026-04-12T13:50:00Z",
    },
  ];
}

function buildBatch(workspaceId: string): UploadBatchSummary {
  return {
    batch_id: "batch-demo-ingest",
    workspace_id: workspaceId,
    source_kind: "pdf_batch",
    status: "in_progress",
    created_at: "2026-04-12T13:30:00Z",
    job_id: "job-demo-ingest",
    progress: {
      total_items: 4,
      accepted_items: 3,
      rejected_items: 1,
      papers_analyzed: 2,
      pairwise_completed: 1,
      pairwise_pending: 2,
    },
    items: [
      {
        filename: "biased-writing-assistants.pdf",
        media_type: "application/pdf",
        size_bytes: 4100000,
        status: "accepted",
        message: "Claim extraction completed.",
      },
      {
        filename: "sycophantic-ai.pdf",
        media_type: "application/pdf",
        size_bytes: 5600000,
        status: "accepted",
        message: "Pairwise comparison backlog is still running.",
      },
      {
        filename: "behavioral-llms.pdf",
        media_type: "application/pdf",
        size_bytes: 6200000,
        status: "accepted",
        message: "Queued for paper analysis.",
      },
      {
        filename: "notes.txt",
        media_type: "text/plain",
        size_bytes: 900,
        status: "rejected",
        message: "Unsupported file type.",
      },
    ],
  };
}

export function buildDemoWorkspaceBundle(workspaceId: string): WorkspaceBundle {
  const graph = buildGraph();
  const jobs = buildJobs(workspaceId);
  const batch = buildBatch(workspaceId);
  const viewer: ViewerSummary = {
    user_id: "demo-user",
    email: "demo@hypatia.app",
    display_name: "Hypatia Demo User",
    auth_mode: "development",
    default_workspace_id: "demo",
    workspaces: [
      {
        workspace_id: "demo",
        name: "Behavioral AI Research",
        role: "owner",
      },
      {
        workspace_id: "cognitive-lab",
        name: "Cognitive Influence Lab",
        role: "member",
      },
    ],
  };

  const summary: WorkspaceSummary = {
    workspace_id: workspaceId,
    name: "Behavioral AI Research",
    paper_count: 3,
    active_batch_count: 1,
    active_job_count: 3,
  };

  const papers: WorkspacePaperListResponse = {
    workspace_id: workspaceId,
    papers: [
      {
        paper_id: "paper-1",
        title: "Biased AI writing assistants shift users' attitudes on societal issues",
        authors: ["Kobe Xie", "Robert Mahari"],
        year: 2026,
        status: "ready",
        source_filename: "biased-writing-assistants.pdf",
      },
      {
        paper_id: "paper-2",
        title: "Sycophantic AI decreases prosocial intentions and promotes dependence",
        authors: ["Myra Cheng", "Dan Jurafsky"],
        year: 2026,
        status: "pairwise_pending",
        source_filename: "sycophantic-ai.pdf",
      },
      {
        paper_id: "paper-3",
        title: "Using Large Language Models in Behavioral Science",
        authors: ["Lena Park", "Jonah Everett"],
        year: 2025,
        status: "ready",
        source_filename: "behavioral-llms.pdf",
      },
    ],
  };

  const graphResponse: WorkspaceGraphResponse = {
    workspace_id: workspaceId,
    graph,
  };

  const jobsResponse: WorkspaceJobListResponse = {
    workspace_id: workspaceId,
    jobs,
  };

  const batchesResponse: WorkspaceBatchListResponse = {
    workspace_id: workspaceId,
    batches: [batch],
  };

  return {
    meta: buildDemoMeta(),
    viewer,
    summary,
    graph: graphResponse,
    papers,
    jobs: jobsResponse,
    batches: batchesResponse,
  };
}
