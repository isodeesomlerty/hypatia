import { AuthControls } from "../../../components/authControls";
import { KnowledgePanel } from "../../../components/knowledgePanel";
import { ResearchGraph } from "../../../components/researchGraph";
import { UploadBatchPanel } from "../../../components/uploadBatchPanel";
import {
  getPaperDetail,
  getPaperRelationshipDetail,
  getWorkspaceBundle,
} from "../../../lib/api";
import { uploadModes, visibleLayers } from "../../../lib/demoWorkspace";
import { getViewerRequestHeaders } from "../../../lib/viewer";

type WorkspacePageProps = {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{
    paper?: string | string[];
    relationship?: string | string[];
  }>;
};

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatBackendLabel(backend: string) {
  return backend.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function firstSearchValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function WorkspacePage({
  params,
  searchParams,
}: WorkspacePageProps) {
  const { workspaceId } = await params;
  const resolvedSearchParams = await searchParams;
  const authHeaders = await getViewerRequestHeaders();
  const workspace = await getWorkspaceBundle(workspaceId, authHeaders);
  const selectedPaperId = firstSearchValue(resolvedSearchParams.paper);
  const selectedRelationshipId = firstSearchValue(resolvedSearchParams.relationship);
  const activeBatch = workspace.batches.batches[0] ?? null;
  const [selectedPaperResult, selectedRelationshipResult] = await Promise.allSettled([
    selectedPaperId
      ? getPaperDetail(workspaceId, selectedPaperId, authHeaders)
      : Promise.resolve(null),
    selectedRelationshipId
      ? getPaperRelationshipDetail(workspaceId, selectedRelationshipId, authHeaders)
      : Promise.resolve(null),
  ]);

  const selectedPaper =
    selectedPaperResult.status === "fulfilled" ? selectedPaperResult.value : null;
  const selectedRelationship =
    selectedRelationshipResult.status === "fulfilled"
      ? selectedRelationshipResult.value
      : null;

  const stats = [
    { label: "Papers in corpus", value: String(workspace.summary.paper_count) },
    { label: "Active batches", value: String(workspace.summary.active_batch_count) },
    {
      label: "Pairs completed",
      value: String(
        workspace.graph.graph.edges.filter((edge) => edge.status === "ready").length,
      ),
    },
    {
      label: "Pairs pending",
      value: String(
        workspace.graph.graph.edges.filter((edge) => edge.status === "pending").length,
      ),
    },
  ];

  return (
    <main className="workspace-page">
      <section className="workspace-header">
        <div>
          <div className="hero-kicker">Private workspace</div>
          <h1>{workspace.summary.name}</h1>
          <p className="workspace-copy">
            Bulk corpus ingestion is the default flow here: add a folder-scale
            batch of academic PDFs or a ZIP import, let background jobs process
            them asynchronously, and watch the research map become richer as
            papers and pairwise comparisons finish.
          </p>
          <div className="viewer-summary">
            <span className="viewer-chip">{workspace.viewer.display_name}</span>
            <span className="viewer-chip viewer-chip--muted">
              {workspace.viewer.auth_mode}
            </span>
            <span className="viewer-chip viewer-chip--backend">
              {formatBackendLabel(workspace.meta.active_storage_backend)}
            </span>
            <span className="viewer-meta">
              {workspace.viewer.email} · default workspace{" "}
              {workspace.viewer.default_workspace_id}
            </span>
            <span className="viewer-meta viewer-meta--stack">
              {workspace.meta.storage_detail}
            </span>
          </div>
        </div>
        <div className="workspace-actions">
          <AuthControls compact />
        </div>
      </section>

      <section className="stats-row">
        {stats.map((stat) => (
          <article className="stat-card" key={stat.label}>
            <div className="section-label">{stat.label}</div>
            <div className="stat-value">{stat.value}</div>
          </article>
        ))}
      </section>

      <section className="ingestion-grid">
        <article className="workspace-panel">
          <div className="section-label">Bulk corpus ingestion</div>
          <UploadBatchPanel workspaceId={workspaceId} />
          <div className="option-grid option-grid--supporting">
            {uploadModes.map((mode) => (
              <div className="option-card" key={mode.title}>
                <div className="detail-heading">{mode.title}</div>
                <p>{mode.description}</p>
                <div className="option-note">{mode.note}</div>
              </div>
            ))}
          </div>
        </article>

        <article className="workspace-panel">
          <div className="section-label">Current batch</div>
          {activeBatch ? (
            <div className="detail-card batch-card">
              <div className="batch-header">
                <div>
                  <div className="detail-heading">Current ingestion batch</div>
                  <p>
                    {activeBatch.source_kind === "pdf_batch"
                      ? "Multiple academic PDFs were accepted into one asynchronous ingestion job."
                      : "A ZIP archive is being expanded, validated, and prepared for ingestion."}
                  </p>
                </div>
                <span className="status-pill status-pill--progress">
                  {formatStatus(activeBatch.status)}
                </span>
              </div>
              <div className="batch-counts">
                <div className="batch-count">
                  <span>Accepted</span>
                  <strong>{activeBatch.progress.accepted_items}</strong>
                </div>
                <div className="batch-count">
                  <span>Rejected</span>
                  <strong>{activeBatch.progress.rejected_items}</strong>
                </div>
                <div className="batch-count">
                  <span>Analyzed</span>
                  <strong>{activeBatch.progress.papers_analyzed}</strong>
                </div>
                <div className="batch-count">
                  <span>Pairs complete</span>
                  <strong>{activeBatch.progress.pairwise_completed}</strong>
                </div>
              </div>
              <ul className="file-result-list">
                {activeBatch.items.map((item) => (
                  <li className="file-result" key={item.filename}>
                    <div>
                      <strong>{item.filename}</strong>
                      <span>{item.message}</span>
                    </div>
                    <span
                      className={`status-pill ${
                        item.status === "accepted"
                          ? "status-pill--accepted"
                          : "status-pill--rejected"
                      }`}
                    >
                      {formatStatus(item.status)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="detail-card batch-card">
              <div className="detail-heading">No active batch</div>
              <p>
                This workspace is ready for a multi-PDF upload or a ZIP import.
                Once a batch is created, progress will appear here.
              </p>
            </div>
          )}
        </article>
      </section>

      <section className="workspace-grid">
        <article className="workspace-panel map-panel">
          <div className="section-label">Research map</div>
          <div className="layer-row">
            {visibleLayers.map((layer) => (
              <span className="layer-chip" key={layer}>
                {layer}
              </span>
            ))}
          </div>
          <ResearchGraph
            workspaceId={workspaceId}
            graph={workspace.graph.graph}
            selectedPaperId={selectedPaper?.paper.paper_id ?? null}
            selectedRelationshipId={
              selectedRelationship?.relationship.relationship_id ?? null
            }
          />
          <p className="panel-note">
            In V2, this graph will update from durable workspace state rather
            than Streamlit session memory, so batch processing progress and
            pending relationships survive reloads and retries.
          </p>
        </article>
        <KnowledgePanel
          workspaceId={workspaceId}
          papers={workspace.papers.papers}
          graph={workspace.graph.graph}
          jobs={workspace.jobs.jobs}
          selectedPaper={selectedPaper}
          selectedRelationship={selectedRelationship}
        />
      </section>
    </main>
  );
}
