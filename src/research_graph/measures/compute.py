"""
Network measures for paper prioritisation.

All algorithms are implemented from scratch (no NetworkX dependency) and
operate on the undirected weighted graph of paper–paper relationships that
Hypatia already computes (paper_edges).

Public API
----------
compute_measures(papers, paper_edges) -> dict[paper_id, measures]

Measures per paper
------------------
pagerank        float   weighted PageRank on the relationship graph
degree          int     raw count of connected papers
priority_score  float   composite used to rank the read-next list
"""
from __future__ import annotations

from collections import defaultdict


def _build_weighted_adjacency(
    paper_ids: list[str],
    paper_edges: dict[tuple[str, str], dict],
) -> dict[str, list[tuple[str, float]]]:
    """Return adjacency list with edge weight = total relationship count."""
    adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
    paper_id_set = set(paper_ids)
    for (pa, pb), agg in paper_edges.items():
        if pa not in paper_id_set or pb not in paper_id_set:
            continue
        w = float(agg.get("total_weight", 1))
        adj[pa].append((pb, w))
        adj[pb].append((pa, w))
    return dict(adj)


def _pagerank(
    paper_ids: list[str],
    adj: dict[str, list[tuple[str, float]]],
    damping: float = 0.85,
    iterations: int = 60,
) -> dict[str, float]:
    """Weighted PageRank via power iteration on the undirected relationship graph.

    Edge weight is the total count of pairwise relationships between two papers,
    so papers with many high-weight connections earn more rank.
    """
    n = len(paper_ids)
    if n == 0:
        return {}

    pr: dict[str, float] = {pid: 1.0 / n for pid in paper_ids}

    # Sum of weights leaving each node (undirected: both directions)
    out_w: dict[str, float] = {pid: sum(w for _, w in adj.get(pid, [])) for pid in paper_ids}

    for _ in range(iterations):
        new_pr: dict[str, float] = {}
        for pid in paper_ids:
            incoming = sum(
                pr[nbr] * w / out_w[nbr]
                for nbr, w in adj.get(pid, [])
                if out_w.get(nbr, 0) > 0
            )
            new_pr[pid] = (1.0 - damping) / n + damping * incoming
        pr = new_pr

    return pr


_HEALTH_TIER = {"healthy": 3, "caution": 2, "concern": 1}


def compute_measures(
    papers: dict[str, dict],
    paper_edges: dict[tuple[str, str], dict],
) -> dict[str, dict]:
    """Compute network measures for all papers.

    Parameters
    ----------
    papers:
        The full papers dict from session state.
    paper_edges:
        The aggregated undirected paper-pair edges from session state.

    Returns
    -------
    dict mapping paper_id -> {pagerank, degree, health_tier, priority_score}
    """
    paper_ids = list(papers.keys())
    n = len(paper_ids)

    if n == 0:
        return {}

    adj = _build_weighted_adjacency(paper_ids, paper_edges)

    # --- Degree (raw connection count) ---
    degree: dict[str, int] = {pid: len(adj.get(pid, [])) for pid in paper_ids}

    # --- PageRank ---
    pr = _pagerank(paper_ids, adj)

    # Normalise PageRank 0-1 for combining with health tier
    pr_lo = min(pr.values())
    pr_hi = max(pr.values())
    pr_span = pr_hi - pr_lo or 1.0
    pr_norm: dict[str, float] = {pid: (pr[pid] - pr_lo) / pr_span for pid in paper_ids}

    # --- Health tier (primary sort key) ---
    def _health_tier(pid: str) -> int:
        score = papers[pid].get("health_score", {}).get("overall_score", "caution")
        return _HEALTH_TIER.get(score, 2)

    # --- Priority score: health dominates (0–3 scaled to 0–1), PageRank secondary ---
    # health weight 0.65, pagerank weight 0.35
    priority: dict[str, float] = {
        pid: round(0.65 * (_health_tier(pid) / 3.0) + 0.35 * pr_norm[pid], 4)
        for pid in paper_ids
    }

    return {
        pid: {
            "pagerank": round(pr[pid], 6),
            "pagerank_norm": round(pr_norm[pid], 3),
            "degree": degree[pid],
            "health_tier": _health_tier(pid),
            "priority_score": priority[pid],
        }
        for pid in paper_ids
    }
