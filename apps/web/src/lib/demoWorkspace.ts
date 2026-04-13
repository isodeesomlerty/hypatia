import type {
  APIMetaResponse,
  ClaimDetail,
  ClaimRelationshipDetail,
  GraphPayload,
  HealthScoreSummary,
  JobSummary,
  PaperDetailResponse,
  PaperRelationshipDetailResponse,
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

function buildDemoHealthScore(
  overallScore: string,
  checks: HealthScoreSummary["checks"] = [],
): HealthScoreSummary {
  return {
    overall_score: overallScore,
    checks,
  };
}

function buildDemoPaperDetails(workspaceId: string): Record<string, PaperDetailResponse> {
  const paper1Claims: ClaimDetail[] = [
    {
      claim_id: "paper-1-claim-1",
      text: "Biased writing assistants can shift user attitudes on politically charged topics without users recognizing the full extent of the influence.",
      claim_type: "causal",
      evidence_type: "observational",
      evidence_strength: "moderate",
      evidence_reasoning:
        "The paper reports measurable attitude shifts but with important external-validity caveats.",
      key_variables: ["assistant stance", "user attitude shift"],
      context: "Interactive writing-assistant setting on societal issues.",
    },
    {
      claim_id: "paper-1-claim-2",
      text: "Participants often rate the assistant positively even when its framing distorts their expressed reasoning.",
      claim_type: "descriptive",
      evidence_type: "survey",
      evidence_strength: "moderate",
      evidence_reasoning:
        "User preference and trust are measured directly, though self-report limits remain.",
      key_variables: ["trust", "assistant favorability"],
      context: "Post-task evaluation after assisted writing.",
    },
  ];

  return {
    "paper-1": {
      workspace_id: workspaceId,
      paper: {
        paper_id: "paper-1",
        title: "Biased AI writing assistants shift users' attitudes on societal issues",
        authors: ["Kobe Xie", "Robert Mahari"],
        year: 2026,
        status: "ready",
        source_filename: "biased-writing-assistants.pdf",
        ingestion_mode: "claude_pdf",
        page_count: 18,
        file_size_mb: 4.1,
        health_score: buildDemoHealthScore("caution", [
          {
            check: "sample_size",
            status: "warn",
            detail:
              "The study is suggestive, but the sample leaves limited room for subgroup analysis.",
          },
          {
            check: "effect_size_reporting",
            status: "pass",
            detail:
              "The paper reports directional shifts with interpretable quantitative support.",
          },
        ]),
        claims: paper1Claims,
      },
    },
    "paper-2": {
      workspace_id: workspaceId,
      paper: {
        paper_id: "paper-2",
        title: "Sycophantic AI decreases prosocial intentions and promotes dependence",
        authors: ["Myra Cheng", "Dan Jurafsky"],
        year: 2026,
        status: "pairwise_pending",
        source_filename: "sycophantic-ai.pdf",
        ingestion_mode: "claude_pdf",
        page_count: 22,
        file_size_mb: 5.6,
        health_score: buildDemoHealthScore("healthy", [
          {
            check: "robustness_checks",
            status: "pass",
            detail: "The paper reports follow-up analyses across multiple task framings.",
          },
        ]),
        claims: [
          {
            claim_id: "paper-2-claim-1",
            text: "Sycophantic AI can lower prosocial intentions while increasing user trust and reliance.",
            claim_type: "causal",
            evidence_type: "observational",
            evidence_strength: "strong",
            evidence_reasoning:
              "The effect appears consistently across several task conditions in the paper.",
            key_variables: ["sycophancy", "prosocial intention", "dependence"],
            context: "Social reasoning tasks with supportive assistant responses.",
          },
        ],
      },
    },
    "paper-3": {
      workspace_id: workspaceId,
      paper: {
        paper_id: "paper-3",
        title: "Using Large Language Models in Behavioral Science",
        authors: ["Lena Park", "Jonah Everett"],
        year: 2025,
        status: "ready",
        source_filename: "behavioral-llms.pdf",
        ingestion_mode: "local_text",
        page_count: 14,
        file_size_mb: 6.2,
        health_score: buildDemoHealthScore("healthy"),
        claims: [
          {
            claim_id: "paper-3-claim-1",
            text: "Large language models can accelerate behavioral-science workflows, but they introduce new validity and measurement risks.",
            claim_type: "theoretical",
            evidence_type: "systematic_review",
            evidence_strength: "moderate",
            evidence_reasoning:
              "The paper synthesizes multiple examples rather than presenting one decisive experiment.",
            key_variables: ["workflow acceleration", "validity risk"],
            context: "Behavioral-science research pipeline overview.",
          },
        ],
      },
    },
  };
}

function buildDemoRelationshipDetails(
  workspaceId: string,
): Record<string, PaperRelationshipDetailResponse> {
  const claimRelationships: ClaimRelationshipDetail[] = [
    {
      claim_relationship_id: "claim-rel-1",
      source_claim_id: "paper-1-claim-1",
      source_claim_text:
        "Biased writing assistants can shift user attitudes on politically charged topics without users recognizing the full extent of the influence.",
      target_claim_id: "paper-2-claim-1",
      target_claim_text:
        "Sycophantic AI can lower prosocial intentions while increasing user trust and reliance.",
      relationship: "supports",
      relationship_strength: "partial",
      explanation:
        "Both papers find that users can be influenced by assistant behavior while underestimating that influence.",
      methodological_note:
        "The tasks differ, but both papers rely on interactive assistant settings rather than offline annotation.",
    },
    {
      claim_relationship_id: "claim-rel-2",
      source_claim_id: "paper-1-claim-2",
      source_claim_text:
        "Participants often rate the assistant positively even when its framing distorts their expressed reasoning.",
      target_claim_id: "paper-2-claim-1",
      target_claim_text:
        "Sycophantic AI can lower prosocial intentions while increasing user trust and reliance.",
      relationship: "qualifies",
      relationship_strength: "direct",
      explanation:
        "The second paper adds a clearer downstream behavioral consequence to the trust pattern the first paper observes.",
      methodological_note:
        "The dependence outcome is more behaviorally concrete in the second paper than in the first.",
    },
  ];

  return {
    "edge-1": {
      workspace_id: workspaceId,
      relationship: {
        relationship_id: "edge-1",
        workspace_id: workspaceId,
        relationship_type: "supports",
        status: "ready",
        visible_strength: 9,
        source_paper: {
          paper_id: "paper-1",
          title: "Biased AI writing assistants shift users' attitudes on societal issues",
          authors: ["Kobe Xie", "Robert Mahari"],
          year: 2026,
          status: "ready",
          source_filename: "biased-writing-assistants.pdf",
        },
        target_paper: {
          paper_id: "paper-2",
          title: "Sycophantic AI decreases prosocial intentions and promotes dependence",
          authors: ["Myra Cheng", "Dan Jurafsky"],
          year: 2026,
          status: "pairwise_pending",
          source_filename: "sycophantic-ai.pdf",
        },
        aggregate: {
          supports: 1,
          contradicts: 0,
          extends: 0,
          qualifies: 1,
          total: 2,
          dominant: "supports",
        },
        claim_relationships: claimRelationships,
        last_attempt: null,
      },
    },
    "edge-2": {
      workspace_id: workspaceId,
      relationship: {
        relationship_id: "edge-2",
        workspace_id: workspaceId,
        relationship_type: "pending",
        status: "pending",
        visible_strength: 2,
        source_paper: {
          paper_id: "paper-2",
          title: "Sycophantic AI decreases prosocial intentions and promotes dependence",
          authors: ["Myra Cheng", "Dan Jurafsky"],
          year: 2026,
          status: "pairwise_pending",
          source_filename: "sycophantic-ai.pdf",
        },
        target_paper: {
          paper_id: "paper-3",
          title: "Using Large Language Models in Behavioral Science",
          authors: ["Lena Park", "Jonah Everett"],
          year: 2025,
          status: "ready",
          source_filename: "behavioral-llms.pdf",
        },
        aggregate: {
          supports: 0,
          contradicts: 0,
          extends: 0,
          qualifies: 0,
          total: 0,
          dominant: null,
        },
        claim_relationships: [],
        last_attempt: {
          job_id: "job-demo-pairwise",
          status: "queued",
          progress_label:
            "Retryable failures stay pending and visible instead of disappearing from the graph.",
          retryable: true,
          created_at: "2026-04-12T13:42:00Z",
          error_kind: null,
        },
      },
    },
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

export function buildDemoPaperDetail(
  workspaceId: string,
  paperId: string,
): PaperDetailResponse | null {
  return buildDemoPaperDetails(workspaceId)[paperId] ?? null;
}

export function buildDemoRelationshipDetail(
  workspaceId: string,
  relationshipId: string,
): PaperRelationshipDetailResponse | null {
  return buildDemoRelationshipDetails(workspaceId)[relationshipId] ?? null;
}
