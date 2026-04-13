import type {
  GraphPayload,
  JobSummary,
  PaperDetailResponse,
  PaperRelationshipDetailResponse,
  PaperSummary,
} from "../lib/types";

type KnowledgePanelProps = {
  workspaceId: string;
  papers: PaperSummary[];
  graph: GraphPayload;
  jobs: JobSummary[];
  selectedPaper: PaperDetailResponse | null;
  selectedRelationship: PaperRelationshipDetailResponse | null;
};

const HEALTH_COPY: Record<string, string> = {
  healthy: "Healthy",
  caution: "Caution",
  concern: "Concern",
};

const RELATIONSHIP_COPY: Record<string, string> = {
  supports: "Supports",
  contradicts: "Contradicts",
  extends: "Extends",
  qualifies: "Qualifies",
  pending: "Pending",
};

function formatLabel(value: string | null | undefined) {
  if (!value) {
    return "Unknown";
  }
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function paperHref(workspaceId: string, paperId: string) {
  return `/workspaces/${workspaceId}?paper=${encodeURIComponent(paperId)}`;
}

function relationshipHref(workspaceId: string, relationshipId: string) {
  return `/workspaces/${workspaceId}?relationship=${encodeURIComponent(relationshipId)}`;
}

function clearHref(workspaceId: string) {
  return `/workspaces/${workspaceId}`;
}

function paperMeta(paper: {
  authors?: string[];
  year?: number | null;
  source_filename?: string | null;
}) {
  const bits = [];
  if (paper.authors?.length) {
    bits.push(paper.authors.join(", "));
  }
  if (paper.year) {
    bits.push(String(paper.year));
  }
  if (paper.source_filename) {
    bits.push(paper.source_filename);
  }
  return bits.join(" · ");
}

function relationshipTitle(
  edgeId: string,
  graph: GraphPayload,
  papersById: Map<string, PaperSummary>,
) {
  const edge = graph.edges.find((item) => item.id === edgeId);
  if (!edge) {
    return "Paper relationship";
  }
  const source = papersById.get(edge.source)?.title ?? edge.source;
  const target = papersById.get(edge.target)?.title ?? edge.target;
  return `${source} ↔ ${target}`;
}

export function KnowledgePanel({
  workspaceId,
  papers,
  graph,
  jobs,
  selectedPaper,
  selectedRelationship,
}: KnowledgePanelProps) {
  const papersById = new Map(papers.map((paper) => [paper.paper_id, paper]));

  return (
    <aside className="workspace-panel detail-panel">
      <div className="section-label">Knowledge panel</div>

      {selectedRelationship ? (
        <>
          <div className="detail-card detail-card--hero">
            <div className="detail-kicker">Paper relationship</div>
            <div className="detail-heading detail-heading--compact">
              {selectedRelationship.relationship.source_paper.title}
            </div>
            <p className="detail-bridge">Compared with</p>
            <div className="detail-heading detail-heading--compact">
              {selectedRelationship.relationship.target_paper.title}
            </div>
            <div className="badge-row">
              <span
                className={`status-pill status-pill--relationship status-pill--${
                  selectedRelationship.relationship.status === "pending"
                    ? "pending"
                    : selectedRelationship.relationship.aggregate.dominant ?? "supports"
                }`}
              >
                {selectedRelationship.relationship.status === "pending"
                  ? "Pending"
                  : `${selectedRelationship.relationship.aggregate.total} ${
                      RELATIONSHIP_COPY[
                        selectedRelationship.relationship.aggregate.dominant ?? "supports"
                      ] ?? "Links"
                    }`}
              </span>
              <span className="status-pill status-pill--paper">
                {formatLabel(selectedRelationship.relationship.status)}
              </span>
              <a className="status-pill status-pill--ghost" href={clearHref(workspaceId)}>
                Clear selection
              </a>
            </div>
            <div className="comparison-grid">
              <div className="comparison-card">
                <div className="detail-kicker">Paper A</div>
                <strong>{selectedRelationship.relationship.source_paper.title}</strong>
                <span>{paperMeta(selectedRelationship.relationship.source_paper)}</span>
              </div>
              <div className="comparison-card">
                <div className="detail-kicker">Paper B</div>
                <strong>{selectedRelationship.relationship.target_paper.title}</strong>
                <span>{paperMeta(selectedRelationship.relationship.target_paper)}</span>
              </div>
            </div>
          </div>

          <div className="detail-card">
            <div className="detail-heading">Aggregate relationship</div>
            <div className="relationship-stat-grid">
              {(["supports", "contradicts", "extends", "qualifies"] as const).map((key) => (
                <div className={`relationship-stat relationship-stat--${key}`} key={key}>
                  <span>{RELATIONSHIP_COPY[key]}</span>
                  <strong>{selectedRelationship.relationship.aggregate[key]}</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="detail-card">
            <div className="detail-heading">Claim relationships</div>
            {selectedRelationship.relationship.claim_relationships.length ? (
              <div className="claim-link-list">
                {selectedRelationship.relationship.claim_relationships.map((relationship) => (
                  <article className="claim-link-card" key={relationship.claim_relationship_id}>
                    <div className="badge-row">
                      <span
                        className={`status-pill status-pill--relationship status-pill--${relationship.relationship}`}
                      >
                        {RELATIONSHIP_COPY[relationship.relationship] ??
                          formatLabel(relationship.relationship)}
                      </span>
                      <span className="status-pill status-pill--queue">
                        {formatLabel(relationship.relationship_strength)}
                      </span>
                    </div>
                    <p className="claim-link-explainer">{relationship.explanation}</p>
                    <div className="claim-link-pair">
                      <div>
                        <strong>Source claim</strong>
                        <span>{relationship.source_claim_text}</span>
                      </div>
                      <div>
                        <strong>Target claim</strong>
                        <span>{relationship.target_claim_text}</span>
                      </div>
                    </div>
                    {relationship.methodological_note ? (
                      <div className="method-note">
                        <strong>Method note</strong>
                        <span>{relationship.methodological_note}</span>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-note">
                Claim-level links will appear here once the comparison completes.
              </p>
            )}
          </div>

          <div className="detail-card">
            <div className="detail-heading">Method notes</div>
            {selectedRelationship.relationship.last_attempt ? (
              <div className="method-note">
                <strong>Last attempt</strong>
                <span>{selectedRelationship.relationship.last_attempt.progress_label}</span>
                <span className="meta-line">
                  {formatLabel(selectedRelationship.relationship.last_attempt.status)}
                  {selectedRelationship.relationship.last_attempt.error_kind
                    ? ` · ${selectedRelationship.relationship.last_attempt.error_kind}`
                    : ""}
                  {selectedRelationship.relationship.last_attempt.retryable
                    ? " · retryable"
                    : ""}
                </span>
              </div>
            ) : (
              <div className="method-note">
                <strong>Methodology context</strong>
                <span>
                  Explicit disagreement notes are attached to individual claim relationships when
                  the worker extracts them.
                </span>
              </div>
            )}
          </div>
        </>
      ) : selectedPaper ? (
        <>
          <div className="detail-card detail-card--hero">
            <div className="detail-kicker">Paper</div>
            <div className="detail-heading">{selectedPaper.paper.title}</div>
            <p>{paperMeta(selectedPaper.paper)}</p>
            <div className="badge-row">
              <span
                className={`status-pill status-pill--health status-pill--${
                  selectedPaper.paper.health_score.overall_score
                }`}
              >
                {HEALTH_COPY[selectedPaper.paper.health_score.overall_score] ??
                  formatLabel(selectedPaper.paper.health_score.overall_score)}
              </span>
              <span className="status-pill status-pill--paper">
                {selectedPaper.paper.claims.length} claims
              </span>
              <span className="status-pill status-pill--queue">
                {formatLabel(selectedPaper.paper.status)}
              </span>
              <a className="status-pill status-pill--ghost" href={clearHref(workspaceId)}>
                Clear selection
              </a>
            </div>
          </div>

          <div className="detail-card">
            <div className="detail-heading">Methodology</div>
            <div className="method-check-list">
              {selectedPaper.paper.health_score.checks.length ? (
                selectedPaper.paper.health_score.checks.map((check) => (
                  <div className="method-check" key={`${check.check}-${check.status}`}>
                    <div className="badge-row">
                      <strong>{formatLabel(check.check)}</strong>
                      <span
                        className={`status-pill status-pill--health status-pill--${
                          check.status === "pass"
                            ? "healthy"
                            : check.status === "fail"
                              ? "concern"
                              : "caution"
                        }`}
                      >
                        {formatLabel(check.status)}
                      </span>
                    </div>
                    <p>{check.detail}</p>
                  </div>
                ))
              ) : (
                <p className="empty-note">
                  No methodology checks are stored for this paper yet.
                </p>
              )}
            </div>
          </div>

          <div className="detail-card">
            <div className="detail-heading">Extracted claims</div>
            <div className="claim-list">
              {selectedPaper.paper.claims.map((claim) => (
                <article className="claim-card" key={claim.claim_id}>
                  <div className="badge-row">
                    <span className="status-pill status-pill--queue">
                      {formatLabel(claim.claim_type)}
                    </span>
                    <span className="status-pill status-pill--paper">
                      {formatLabel(claim.evidence_strength)}
                    </span>
                  </div>
                  <strong>{claim.text}</strong>
                  <div className="meta-line">
                    {formatLabel(claim.evidence_type)}
                    {claim.key_variables.length
                      ? ` · ${claim.key_variables.join(", ")}`
                      : ""}
                  </div>
                  {claim.context ? <p>{claim.context}</p> : null}
                </article>
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="detail-card detail-card--hero">
          <div className="detail-kicker">Browse the map</div>
          <div className="detail-heading">Select a paper or paper relationship</div>
          <p>
            Click any node to inspect extracted claims and methodology, or click an edge to inspect
            the aggregate relationship and the underlying claim links.
          </p>
        </div>
      )}

      <div className="detail-card">
        <div className="detail-heading">Papers in this workspace</div>
        <ul className="paper-list paper-list--interactive">
          {papers.map((paper) => (
            <li className="paper-row" key={paper.paper_id}>
              <a className="paper-link" href={paperHref(workspaceId, paper.paper_id)}>
                <div>
                  <strong>{paper.title}</strong>
                  <span>{paperMeta(paper)}</span>
                </div>
                <span className="status-pill status-pill--paper">{formatLabel(paper.status)}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>

      <div className="detail-card">
        <div className="detail-heading">Visible relationships</div>
        <ul className="paper-list paper-list--interactive">
          {graph.edges.length ? (
            graph.edges.map((edge) => (
              <li className="paper-row" key={edge.id}>
                <a className="paper-link" href={relationshipHref(workspaceId, edge.id)}>
                  <div>
                    <strong>{relationshipTitle(edge.id, graph, papersById)}</strong>
                    <span>
                      {RELATIONSHIP_COPY[edge.relationship_type] ?? formatLabel(edge.relationship_type)}
                    </span>
                  </div>
                  <span
                    className={`status-pill status-pill--relationship status-pill--${
                      edge.status === "pending" ? "pending" : edge.relationship_type
                    }`}
                  >
                    {formatLabel(edge.status)}
                  </span>
                </a>
              </li>
            ))
          ) : (
            <li className="paper-row">
              <div>
                <strong>No relationships yet</strong>
                <span>The graph will get richer as more papers are analyzed.</span>
              </div>
            </li>
          )}
        </ul>
      </div>

      <div className="detail-card">
        <div className="detail-heading">Recent jobs</div>
        <ul className="job-list">
          {jobs.map((job) => (
            <li className="job-row" key={job.job_id}>
              <div>
                <strong>{formatLabel(job.job_type)}</strong>
                <span>{job.progress_label}</span>
              </div>
              <span className="status-pill status-pill--queue">{formatLabel(job.status)}</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
