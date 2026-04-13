import { AuthControls } from "../../../components/authControls";
import { ResearchGraph } from "../../../components/researchGraph";
import { getWorkspaceBundle } from "../../../lib/api";
import { uploadModes, visibleLayers } from "../../../lib/demoWorkspace";
import { getViewerRequestHeaders } from "../../../lib/viewer";

type WorkspacePageProps = {
  params: Promise<{ workspaceId: string }>;
};

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatBackendLabel(backend: string) {
  return backend.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

export default async function WorkspacePage({ params }: WorkspacePageProps) {
  const { workspaceId } = await params;
  const authHeaders = await getViewerRequestHeaders();
  const workspace = await getWorkspaceBundle(workspaceId, authHeaders);
  const activeBatch = workspace.batches.batches[0] ?? null;

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
          <button type="button">Upload PDF batch</button>
          <button type="button" className="secondary-button">
            Import ZIP archive
          </button>
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
          <div className="option-grid">
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
          <ResearchGraph graph={workspace.graph.graph} />
          <p className="panel-note">
            In V2, this graph will update from durable workspace state rather
            than Streamlit session memory, so batch processing progress and
            pending relationships survive reloads and retries.
          </p>
        </article>

        <article className="workspace-panel detail-panel">
          <div className="section-label">Corpus details</div>
          <div className="detail-card">
            <div className="detail-heading">Accessible workspaces</div>
            <ul className="workspace-access-list">
              {workspace.viewer.workspaces.map((entry) => (
                <li className="workspace-access-row" key={entry.workspace_id}>
                  <div>
                    <strong>{entry.name}</strong>
                    <span>{entry.workspace_id}</span>
                  </div>
                  <span className="status-pill status-pill--queue">
                    {formatStatus(entry.role)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="detail-card">
            <div className="detail-heading">Workspace papers</div>
            <ul className="paper-list">
              {workspace.papers.papers.map((paper) => (
                <li className="paper-row" key={paper.paper_id}>
                  <div>
                    <strong>{paper.title}</strong>
                    <span>{paper.year}</span>
                  </div>
                  <span className="status-pill status-pill--paper">
                    {formatStatus(paper.status)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="detail-card">
            <div className="detail-heading">Recent jobs</div>
            <ul className="job-list">
              {workspace.jobs.jobs.map((job) => (
                <li className="job-row" key={job.job_id}>
                  <div>
                    <strong>{formatStatus(job.job_type)}</strong>
                    <span>{job.progress_label}</span>
                  </div>
                  <span className="status-pill status-pill--queue">
                    {formatStatus(job.status)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </article>
      </section>
    </main>
  );
}
