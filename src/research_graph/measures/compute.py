"""
Graph measures for a typed citation network.

Each paper is scored on influence, controversy, and structural role using
only the standard library — no external graph dependencies required.

Directed edge: source_paper → target_paper means the source paper's claim
relates to (supports, extends, contradicts, or qualifies) the target paper's
claim.  Papers with many in-edges from important sources rank highest.
"""

from __future__ import annotations

from collections import defaultdict, deque

# Weights used when building the directed graph for PageRank / HITS.
# Controversy (contradicts) is given a non-zero weight because being
# challenged by many papers is itself a signal of importance.
_EDGE_WEIGHTS: dict[str, float] = {
    "supports": 1.0,
    "extends": 0.8,
    "qualifies": 0.4,
    "contradicts": 0.6,
}

_VISUAL_RELATIONS = tuple(_EDGE_WEIGHTS)

# Weights for the composite priority score (must sum to 1.0).
_PRIORITY_WEIGHTS = {
    "pagerank": 0.35,
    "authority": 0.25,
    "betweenness": 0.20,
    "controversy_score": 0.10,
    "foundational_score": 0.10,
}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _claim_to_paper_lookup(papers: dict[str, dict]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for paper_id, paper in papers.items():
        for claim in paper.get("claims", []):
            lookup[claim["claim_id"]] = paper_id
    return lookup


def _build_directed_graph(
    papers: dict[str, dict],
    relationships: list[dict],
) -> tuple[
    dict[str, dict[str, float]],  # out_edges[src][tgt] = weight
    dict[str, dict[str, float]],  # in_edges[tgt][src]  = weight
    dict[str, dict[str, int]],    # counts_in[tgt][rel_type] = count
]:
    claim_lookup = _claim_to_paper_lookup(papers)
    paper_ids = set(papers)

    out_edges: dict[str, dict[str, float]] = {pid: {} for pid in paper_ids}
    in_edges: dict[str, dict[str, float]] = {pid: {} for pid in paper_ids}
    counts_in: dict[str, dict[str, int]] = {pid: defaultdict(int) for pid in paper_ids}

    for rel in relationships:
        rel_type = rel.get("relationship")
        if rel_type not in _EDGE_WEIGHTS:
            continue

        src = claim_lookup.get(rel.get("source_claim_id", ""))
        tgt = claim_lookup.get(rel.get("target_claim_id", ""))

        if not src or not tgt or src == tgt:
            continue
        if src not in paper_ids or tgt not in paper_ids:
            continue

        weight = _EDGE_WEIGHTS[rel_type]
        out_edges[src][tgt] = out_edges[src].get(tgt, 0.0) + weight
        in_edges[tgt][src] = in_edges[tgt].get(src, 0.0) + weight
        counts_in[tgt][rel_type] += 1

    return out_edges, in_edges, counts_in


# ---------------------------------------------------------------------------
# Algorithm implementations
# ---------------------------------------------------------------------------

def _pagerank(
    nodes: set[str],
    out_edges: dict[str, dict[str, float]],
    in_edges: dict[str, dict[str, float]],
    damping: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> dict[str, float]:
    n = len(nodes)
    if n == 0:
        return {}

    rank = {node: 1.0 / n for node in nodes}
    out_totals = {node: sum(out_edges.get(node, {}).values()) for node in nodes}

    for _ in range(max_iter):
        dangling = sum(rank[node] for node in nodes if out_totals[node] == 0.0)
        new_rank: dict[str, float] = {}

        for node in nodes:
            in_score = sum(
                rank[src] * weight / out_totals[src]
                for src, weight in in_edges.get(node, {}).items()
                if out_totals.get(src, 0.0) > 0.0
            )
            in_score += dangling / n
            new_rank[node] = (1.0 - damping) / n + damping * in_score

        err = sum(abs(new_rank[node] - rank[node]) for node in nodes)
        rank = new_rank
        if err < tol:
            break

    return rank


def _hits(
    nodes: set[str],
    out_edges: dict[str, dict[str, float]],
    max_iter: int = 100,
    tol: float = 1e-6,
) -> tuple[dict[str, float], dict[str, float]]:
    """Returns (hub_scores, authority_scores)."""
    if not nodes:
        return {}, {}

    hub = {n: 1.0 for n in nodes}
    auth = {n: 1.0 for n in nodes}

    for _ in range(max_iter):
        # auth[v] = sum of hub[u] for all u → v
        new_auth: dict[str, float] = {n: 0.0 for n in nodes}
        for src, targets in out_edges.items():
            for tgt, weight in targets.items():
                if tgt in new_auth:
                    new_auth[tgt] += hub.get(src, 0.0) * weight

        auth_norm = sum(v * v for v in new_auth.values()) ** 0.5 or 1.0
        new_auth = {n: v / auth_norm for n, v in new_auth.items()}

        # hub[u] = sum of auth[v] for all u → v
        new_hub: dict[str, float] = {n: 0.0 for n in nodes}
        for src, targets in out_edges.items():
            if src in new_hub:
                for tgt, weight in targets.items():
                    new_hub[src] += new_auth.get(tgt, 0.0) * weight

        hub_norm = sum(v * v for v in new_hub.values()) ** 0.5 or 1.0
        new_hub = {n: v / hub_norm for n, v in new_hub.items()}

        auth_err = sum(abs(new_auth[n] - auth.get(n, 0.0)) for n in nodes)
        hub_err = sum(abs(new_hub[n] - hub.get(n, 0.0)) for n in nodes)
        auth, hub = new_auth, new_hub
        if auth_err + hub_err < tol:
            break

    return hub, auth


def _betweenness(
    nodes: set[str],
    out_edges: dict[str, dict[str, float]],
) -> dict[str, float]:
    """Brandes algorithm for directed betweenness centrality (unweighted paths)."""
    node_list = list(nodes)
    between: dict[str, float] = {n: 0.0 for n in node_list}

    for source in node_list:
        stack: list[str] = []
        pred: dict[str, list[str]] = {n: [] for n in node_list}
        sigma: dict[str, float] = {n: 0.0 for n in node_list}
        sigma[source] = 1.0
        dist: dict[str, int] = {n: -1 for n in node_list}
        dist[source] = 0
        queue: deque[str] = deque([source])

        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in out_edges.get(v, {}):
                if w not in dist:
                    continue
                if dist[w] < 0:
                    queue.append(w)
                    dist[w] = dist[v] + 1
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)

        delta: dict[str, float] = {n: 0.0 for n in node_list}
        while stack:
            w = stack.pop()
            for v in pred[w]:
                if sigma[w] > 0.0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != source:
                between[w] += delta[w]

    n = len(node_list)
    if n > 2:
        scale = 1.0 / ((n - 1) * (n - 2))
        between = {node: v * scale for node, v in between.items()}

    return between


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _minmax(values: dict[str, float]) -> dict[str, float]:
    """Scale all values to [0, 1] using min-max normalisation."""
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    span = hi - lo
    if span == 0.0:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / span for k, v in values.items()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_measures(
    papers: dict[str, dict],
    relationships: list[dict],
    paper_edges: dict,  # kept for a consistent call signature; not used directly
) -> dict[str, dict]:
    """
    Compute graph influence measures for every paper.

    Returns a mapping of paper_id → measure dict with the keys:

    Raw graph measures
    ------------------
    pagerank          Weighted PageRank — rewards in-links from important papers.
    authority         HITS authority — papers cited by strong hubs.
    hub               HITS hub — papers that point to strong authorities.
    betweenness       Normalised betweenness — bridges between research clusters.
    in_degree         Total weighted in-edge sum (citation-equivalent count).
    out_degree        Total weighted out-edge sum.

    Per-type in-counts (integer)
    ----------------------------
    supports_in, extends_in, contradicts_in, qualifies_in

    Derived semantic scores (0–1 float)
    ------------------------------------
    controversy_score   contradicts_in / total_in  — actively debated work.
    foundational_score  extends_in (raw count, normalised for priority).
    consensus_score     supports_in / total_in — established findings.

    Composite
    ---------
    priority_score  Weighted blend of normalised measures.
                    Higher = more important to read first.
    """
    if not papers:
        return {}

    out_edges, in_edges, counts_in = _build_directed_graph(papers, relationships)
    nodes = set(papers)

    # --- Degree ---
    in_degree = {pid: sum(in_edges[pid].values()) for pid in nodes}
    out_degree = {pid: sum(out_edges[pid].values()) for pid in nodes}

    # --- Per-type in-counts ---
    per_type: dict[str, dict[str, int]] = {}
    for pid in nodes:
        raw = counts_in.get(pid, {})
        per_type[pid] = {rt: raw.get(rt, 0) for rt in _VISUAL_RELATIONS}

    # --- Semantic scores ---
    controversy: dict[str, float] = {}
    foundational: dict[str, float] = {}
    consensus: dict[str, float] = {}
    for pid in nodes:
        total_in = sum(per_type[pid].values())
        controversy[pid] = per_type[pid]["contradicts"] / total_in if total_in else 0.0
        foundational[pid] = float(per_type[pid]["extends"])
        consensus[pid] = per_type[pid]["supports"] / total_in if total_in else 0.0

    # --- Graph algorithms ---
    pagerank = _pagerank(nodes, out_edges, in_edges)
    hub, authority = _hits(nodes, out_edges)
    betweenness = _betweenness(nodes, out_edges)

    # --- Priority score (normalised components) ---
    norm_pr = _minmax(pagerank)
    norm_auth = _minmax(authority)
    norm_bet = _minmax(betweenness)
    norm_cont = _minmax(controversy)
    norm_found = _minmax(foundational)

    priority: dict[str, float] = {
        pid: (
            _PRIORITY_WEIGHTS["pagerank"] * norm_pr.get(pid, 0.0)
            + _PRIORITY_WEIGHTS["authority"] * norm_auth.get(pid, 0.0)
            + _PRIORITY_WEIGHTS["betweenness"] * norm_bet.get(pid, 0.0)
            + _PRIORITY_WEIGHTS["controversy_score"] * norm_cont.get(pid, 0.0)
            + _PRIORITY_WEIGHTS["foundational_score"] * norm_found.get(pid, 0.0)
        )
        for pid in nodes
    }

    return {
        pid: {
            # raw graph measures
            "pagerank": round(pagerank.get(pid, 0.0), 6),
            "authority": round(authority.get(pid, 0.0), 6),
            "hub": round(hub.get(pid, 0.0), 6),
            "betweenness": round(betweenness.get(pid, 0.0), 6),
            "in_degree": round(in_degree.get(pid, 0.0), 3),
            "out_degree": round(out_degree.get(pid, 0.0), 3),
            # per-type in-counts
            "supports_in": per_type[pid]["supports"],
            "extends_in": per_type[pid]["extends"],
            "contradicts_in": per_type[pid]["contradicts"],
            "qualifies_in": per_type[pid]["qualifies"],
            # semantic scores
            "controversy_score": round(controversy.get(pid, 0.0), 4),
            "foundational_score": round(foundational.get(pid, 0.0), 3),
            "consensus_score": round(consensus.get(pid, 0.0), 4),
            # composite
            "priority_score": round(priority.get(pid, 0.0), 4),
        }
        for pid in nodes
    }
