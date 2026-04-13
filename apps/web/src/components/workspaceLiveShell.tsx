"use client";

import { useEffect, useRef, useState } from "react";

import type { WorkspaceSnapshot } from "../lib/types";
import { AuthControls } from "./authControls";
import { KnowledgePanel } from "./knowledgePanel";
import { ResearchGraph } from "./researchGraph";
import { UploadBatchPanel } from "./uploadBatchPanel";
import { uploadModes, visibleLayers } from "../lib/demoWorkspace";

type WorkspaceLiveShellProps = {
  workspaceId: string;
  initialSnapshot: WorkspaceSnapshot;
};

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatBackendLabel(backend: string) {
  return backend.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function selectionQuery(snapshot: WorkspaceSnapshot) {
  if (snapshot.selectedRelationship?.relationship.relationship_id) {
    return `relationship=${encodeURIComponent(
      snapshot.selectedRelationship.relationship.relationship_id,
    )}`;
  }
  if (snapshot.selectedPaper?.paper.paper_id) {
    return `paper=${encodeURIComponent(snapshot.selectedPaper.paper.paper_id)}`;
  }
  return "";
}

function shouldPoll(snapshot: WorkspaceSnapshot) {
  const hasActiveJobs = snapshot.workspace.jobs.jobs.some(
    (job) => job.status === "queued" || job.status === "in_progress",
  );
  const hasActiveBatches = snapshot.workspace.batches.batches.some(
    (batch) => batch.status === "queued" || batch.status === "in_progress",
  );
  const selectedPaperPending =
    snapshot.selectedPaper?.paper.status === "queued" ||
    snapshot.selectedPaper?.paper.status === "analyzing" ||
    snapshot.selectedPaper?.paper.status === "pairwise_pending";
  const selectedRelationshipPending =
    snapshot.selectedRelationship?.relationship.status === "pending";

  return (
    hasActiveJobs || hasActiveBatches || selectedPaperPending || selectedRelationshipPending
  );
}

function formatPolledAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "just now";
  }
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

async function fetchSnapshot(
  workspaceId: string,
  selection: string,
): Promise<WorkspaceSnapshot> {
  const query = selection ? `?${selection}` : "";
  const response = await fetch(`/api/workspaces/${workspaceId}/snapshot${query}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Workspace refresh failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as WorkspaceSnapshot;
}

export function WorkspaceLiveShell({
  workspaceId,
  initialSnapshot,
}: WorkspaceLiveShellProps) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const intervalRef = useRef<number | null>(null);
  const refreshInFlightRef = useRef(false);

  useEffect(() => {
    setSnapshot(initialSnapshot);
  }, [initialSnapshot]);

  useEffect(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!shouldPoll(snapshot)) {
      return;
    }

    intervalRef.current = window.setInterval(async () => {
      if (refreshInFlightRef.current) {
        return;
      }
      refreshInFlightRef.current = true;
      setIsRefreshing(true);
      try {
        const next = await fetchSnapshot(workspaceId, selectionQuery(snapshot));
        setSnapshot(next);
      } catch {
        // Keep the last successful snapshot visible if refresh fails.
      } finally {
        refreshInFlightRef.current = false;
        setIsRefreshing(false);
      }
    }, 5000);

    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [snapshot, workspaceId]);

  const workspace = snapshot.workspace;
  const activeBatch = workspace.batches.batches[0] ?? null;
  const selectedPaper = snapshot.selectedPaper;
  const selectedRelationship = snapshot.selectedRelationship;

  const stats = [
    { label: "Papers in corpus", value: String(workspace.summary.paper_count) },
    { label: "Active batches", value: String(workspace.summary.active_batch_count) },
    {
      label: "Pairs completed",
      value: String(workspace.graph.graph.edges.filter((edge) => edge.status === "ready").length),
    },
    {
      label: "Pairs pending",
      value: String(workspace.graph.graph.edges.filter((edge) => edge.status === "pending").length),
    },
  ];

  return (
    <main className="workspace-page">
      <section className="workspace-header">
        <div>
          <div className="hero-kicker">Private workspace</div>
          <h1>{workspace.summary.name}</h1>
          <p className="workspace-copy">
            Bulk corpus ingestion is the default flow here: add a folder-scale batch of
            academic PDFs or a ZIP import, let background jobs process them asynchronously,
            and watch the research map become richer as papers and pairwise comparisons
            finish.
          </p>
          <div className="viewer-summary">
            <span className="viewer-chip">{workspace.viewer.display_name}</span>
            <span className="viewer-chip viewer-chip--muted">
              {workspace.viewer.auth_mode}
            </span>
            <span className="viewer-chip viewer-chip--backend">
              {formatBackendLabel(workspace.meta.active_storage_backend)}
            </span>
            <span className="viewer-chip viewer-chip--live">
              {isRefreshing || shouldPoll(snapshot)
                ? `Live updates · ${formatPolledAt(snapshot.polled_at)}`
                : `Snapshot · ${formatPolledAt(snapshot.polled_at)}`}
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
                This workspace is ready for a multi-PDF upload or a ZIP import. Once a batch
                is created, progress will appear here and refresh automatically while jobs are
                active.
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
            selectedRelationshipId={selectedRelationship?.relationship.relationship_id ?? null}
          />
          <p className="panel-note">
            This V2 graph now refreshes from durable workspace state while ingestion and
            pairwise jobs are still running, so pending relationships and newly completed
            comparisons appear without losing your place.
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
