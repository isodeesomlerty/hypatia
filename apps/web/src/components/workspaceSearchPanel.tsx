"use client";

import { useEffect, useState, useTransition } from "react";

import type { WorkspaceSearchResponse } from "../lib/types";

type WorkspaceSearchPanelProps = {
  workspaceId: string;
  onResultChange?: (result: WorkspaceSearchResponse | null) => void;
};

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function paperHref(workspaceId: string, paperId: string) {
  return `/workspaces/${workspaceId}?paper=${encodeURIComponent(paperId)}`;
}

function paperMeta(match: WorkspaceSearchResponse["matches"][number]) {
  const bits = [];
  if (match.paper_authors.length) {
    bits.push(match.paper_authors.join(", "));
  }
  if (match.paper_year) {
    bits.push(String(match.paper_year));
  }
  return bits.join(" · ");
}

export function WorkspaceSearchPanel({
  workspaceId,
  onResultChange,
}: WorkspaceSearchPanelProps) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<WorkspaceSearchResponse | null>(null);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    onResultChange?.(result);
  }, [onResultChange, result]);

  function clearSearch() {
    setQuery("");
    setResult(null);
    setError("");
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const trimmed = query.trim();
    if (!trimmed) {
      setResult(null);
      return;
    }

    startTransition(async () => {
      const response = await fetch(`/api/workspaces/${workspaceId}/search`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          query: trimmed,
          limit: 8,
        }),
      });
      const payload = (await response.json()) as WorkspaceSearchResponse | { detail?: string };
      if (!response.ok) {
        setResult(null);
        setError(
          "detail" in payload && payload.detail
            ? payload.detail
            : "Hypatia could not complete that search.",
        );
        return;
      }
      if (!("matches" in payload)) {
        setResult(null);
        setError("The search response was not recognized.");
        return;
      }
      setResult(payload);
    });
  }

  return (
    <div className="detail-card search-panel">
      <div className="detail-heading">Search the workspace</div>
      <p>
        Ask for a topic, claim, or concept and Hypatia will hybrid-rank the most
        relevant extracted claims across your current corpus.
      </p>
      <form className="search-form" onSubmit={handleSubmit}>
        <input
          className="search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search claims, methods, or topics..."
        />
        <button type="submit" className="upload-submit" disabled={isPending}>
          {isPending ? "Searching..." : "Search"}
        </button>
        {result || query ? (
          <button
            type="button"
            className="search-clear"
            onClick={clearSearch}
            disabled={isPending}
          >
            Clear
          </button>
        ) : null}
      </form>

      {error ? <div className="upload-error">{error}</div> : null}

      {result ? (
        <div className="search-results">
          <div className="badge-row">
            <span className="status-pill status-pill--queue">
              {formatLabel(result.search_mode)}
            </span>
            <span className="status-pill status-pill--paper">
              {result.matches.length} match{result.matches.length === 1 ? "" : "es"}
            </span>
          </div>
          <p className="panel-note">{result.summary}</p>
          <p className="panel-note">Matching papers are highlighted in the graph while this result set is active.</p>
          {result.matches.length ? (
            <div className="search-result-list">
              {result.matches.map((match) => (
                <a
                  className="search-result-card"
                  href={paperHref(workspaceId, match.paper_id)}
                  key={match.claim_id}
                >
                  <div className="search-result-header">
                    <strong>{match.paper_title}</strong>
                    <span>Score {match.score.toFixed(2)}</span>
                  </div>
                  {paperMeta(match) ? (
                    <div className="search-result-meta">{paperMeta(match)}</div>
                  ) : null}
                  <p>{match.claim_text}</p>
                  <div className="badge-row">
                    <span className="status-pill status-pill--paper">
                      {formatLabel(match.claim_type)}
                    </span>
                    <span className="status-pill status-pill--queue">
                      {formatLabel(match.evidence_strength)}
                    </span>
                  </div>
                  {match.context ? (
                    <div className="search-result-context">{match.context}</div>
                  ) : null}
                </a>
              ))}
            </div>
          ) : (
            <p className="empty-note">
              No ranked claims matched yet. Try a narrower concept or add more papers to the
              workspace.
            </p>
          )}
        </div>
      ) : (
        <p className="panel-note">
          Search works across extracted claim text, paper titles, evidence language,
          claim context, and persisted claim vectors from your uploaded papers.
        </p>
      )}
    </div>
  );
}
