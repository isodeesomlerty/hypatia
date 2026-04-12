from __future__ import annotations

from collections import defaultdict
from html import escape

from .cache import pair_key
from .config import CACHE_DIR, EDGE_COLORS, HEALTH_COLORS, VISUAL_RELATIONSHIPS


def claim_to_paper_lookup(papers: dict[str, dict]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for paper_id, paper in papers.items():
        for claim in paper.get("claims", []):
            lookup[claim["claim_id"]] = paper_id
    return lookup


def paper_ids_for_claim_ids(claim_ids: list[str], papers: dict[str, dict]) -> list[str]:
    lookup = claim_to_paper_lookup(papers)
    ordered: list[str] = []
    seen: set[str] = set()
    for claim_id in claim_ids:
        paper_id = lookup.get(claim_id)
        if paper_id and paper_id not in seen:
            seen.add(paper_id)
            ordered.append(paper_id)
    return ordered


def aggregate_paper_edges(
    relationships: list[dict],
    papers: dict[str, dict],
) -> dict[tuple[str, str], dict]:
    claim_lookup = claim_to_paper_lookup(papers)
    paper_edges: dict[tuple[str, str], dict] = {}

    for relationship in relationships:
        rel_type = relationship.get("relationship")
        if rel_type not in VISUAL_RELATIONSHIPS:
            continue

        source_paper = claim_lookup.get(relationship.get("source_claim_id", ""))
        target_paper = claim_lookup.get(relationship.get("target_claim_id", ""))
        if not source_paper or not target_paper or source_paper == target_paper:
            continue

        key = tuple(sorted((source_paper, target_paper)))
        if key not in paper_edges:
            paper_edges[key] = {rel: 0 for rel in VISUAL_RELATIONSHIPS}

        paper_edges[key][rel_type] += 1

    finalized: dict[tuple[str, str], dict] = {}
    for key, counts in paper_edges.items():
        total = sum(counts.values())
        if total == 0:
            continue
        dominant = max(VISUAL_RELATIONSHIPS, key=lambda rel: (counts[rel], rel))
        finalized[key] = {
            **counts,
            "dominant": dominant,
            "total_weight": total,
        }

    return finalized


def build_relationship_index(
    relationships: list[dict],
    papers: dict[str, dict],
) -> dict[str, list[dict]]:
    claim_lookup = claim_to_paper_lookup(papers)
    index: dict[str, list[dict]] = defaultdict(list)

    for relationship in relationships:
        source_paper = claim_lookup.get(relationship.get("source_claim_id", ""))
        target_paper = claim_lookup.get(relationship.get("target_claim_id", ""))
        if not source_paper or not target_paper or source_paper == target_paper:
            continue
        index[pair_key(source_paper, target_paper)].append(relationship)

    return dict(index)


def build_pending_pair_index(
    manifest: dict,
    papers: dict[str, dict],
    pairwise_signature: str | None = None,
) -> dict[str, dict]:
    paper_ids = set(papers)
    processed_pairs = {
        key
        for key, entry in manifest.get("processed_pairs", {}).items()
        if (
            (not pairwise_signature or entry.get("pairwise_signature") == pairwise_signature)
            and entry.get("pair_cache_path")
            and (CACHE_DIR / entry["pair_cache_path"]).exists()
        )
    }
    pending: dict[str, dict] = {}
    for key, entry in manifest.get("failed_pairs", {}).items():
        if key in processed_pairs:
            continue
        left, right = key.split("||", maxsplit=1)
        if left not in paper_ids or right not in paper_ids:
            continue
        pending[key] = {
            "paper_a_id": left,
            "paper_b_id": right,
            "error": entry.get("error", ""),
            "error_kind": entry.get("error_kind", "unknown"),
            "retryable": bool(entry.get("retryable", True)),
            "updated_at": entry.get("updated_at", ""),
            "status": "pending",
        }
    return pending


def format_health_badge(paper: dict) -> str:
    score = paper.get("health_score", {}).get("overall_score", "caution")
    return score.replace("_", " ").title()


def _truncate_label(text: str, limit: int = 44) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3].rstrip() + "..."


def _tooltip_text(*lines: str) -> str:
    cleaned = [escape((line or "").strip()) for line in lines if (line or "").strip()]
    return "\n".join(cleaned)


def _node_color(base_color: str, dimmed: bool) -> dict:
    if not dimmed:
        return {
            "background": base_color,
            "border": base_color,
            "highlight": {"background": base_color, "border": base_color},
        }
    return {
        "background": "#DED4C7",
        "border": "#CBBEAF",
        "highlight": {"background": base_color, "border": base_color},
    }


def build_graph_payload(
    papers: dict[str, dict],
    paper_edges: dict[tuple[str, str], dict],
    pending_pairs: dict[str, dict] | None = None,
    highlighted_paper_ids: list[str] | None = None,
    hide_low_signal_edges: bool = False,
) -> tuple[list[dict], list[dict]]:
    highlight_set = set(highlighted_paper_ids or [])
    apply_focus = bool(highlight_set)

    nodes: list[dict] = []
    for paper_id, paper in sorted(
        papers.items(),
        key=lambda item: (item[1].get("year") or 0, item[1].get("title", "")),
    ):
        score = paper.get("health_score", {}).get("overall_score", "caution")
        base_color = HEALTH_COLORS.get(score, HEALTH_COLORS["caution"])
        dimmed = apply_focus and paper_id not in highlight_set
        authors = ", ".join(paper.get("authors", []))
        year = str(paper.get("year") or "").strip()
        author_line = " | ".join(part for part in [authors, year] if part)
        tooltip = _tooltip_text(
            paper.get("title", "Untitled paper"),
            author_line,
            f"Health: {format_health_badge(paper)}",
            f"Claims: {len(paper.get('claims', []))}",
        )
        label = _truncate_label(
            f"{paper.get('title', 'Untitled paper')} ({paper.get('year') or 'n.d.'})"
        )
        nodes.append(
            {
                "id": paper_id,
                "label": label,
                "title": tooltip,
                "shape": "dot",
                "size": 28,
                "font": {
                    "size": 16 if not dimmed else 13,
                    "color": "#221A14" if not dimmed else "#A69A8B",
                    "face": "Iowan Old Style, Palatino Linotype, Georgia",
                },
                "color": _node_color(base_color, dimmed),
                "physics": True,
            }
        )

    edges: list[dict] = []
    rendered_edge_ids: set[str] = set()
    for (paper_a, paper_b), aggregate in sorted(
        paper_edges.items(),
        key=lambda item: (-item[1].get("total_weight", 0), item[0]),
    ):
        if hide_low_signal_edges and aggregate.get("total_weight", 0) <= 1:
            continue

        dominant = aggregate["dominant"]
        dimmed = apply_focus and not ({paper_a, paper_b} <= highlight_set)
        color = "#CBBEAF" if dimmed else EDGE_COLORS[dominant]
        title = _tooltip_text(
            f"Contradicts: {aggregate.get('contradicts', 0)}",
            f"Supports: {aggregate.get('supports', 0)}",
            f"Extends: {aggregate.get('extends', 0)}",
            f"Qualifies: {aggregate.get('qualifies', 0)}",
        )
        edges.append(
            {
                "id": pair_key(paper_a, paper_b),
                "from": paper_a,
                "to": paper_b,
                "status": "ready",
                "title": title,
                "width": min(2 + aggregate.get("total_weight", 0), 10),
                "dashes": dominant in {"extends", "qualifies"},
                "color": {
                    "color": color,
                    "highlight": EDGE_COLORS[dominant],
                    "hover": EDGE_COLORS[dominant],
                    "opacity": 0.8 if not dimmed else 0.35,
                },
                "smooth": False,
            }
        )
        rendered_edge_ids.add(pair_key(paper_a, paper_b))

    for edge_id, pending in sorted((pending_pairs or {}).items()):
        if edge_id in rendered_edge_ids:
            continue
        paper_a = pending["paper_a_id"]
        paper_b = pending["paper_b_id"]
        dimmed = apply_focus and not ({paper_a, paper_b} <= highlight_set)
        color = "#B9AE9F" if not dimmed else "#D6CEC3"
        edges.append(
            {
                "id": edge_id,
                "from": paper_a,
                "to": paper_b,
                "status": "pending",
                "title": _tooltip_text("Paper relationship pending", "Click for details"),
                "width": 1.8,
                "dashes": True,
                "color": {
                    "color": color,
                    "highlight": "#B9AE9F",
                    "hover": "#B9AE9F",
                    "opacity": 0.9 if not dimmed else 0.45,
                },
                "smooth": False,
            }
        )

    return nodes, edges
