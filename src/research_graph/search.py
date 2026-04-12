from __future__ import annotations

import re
from collections import Counter


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def build_claim_search_text(paper: dict, claim: dict) -> str:
    parts = [
        paper.get("title", ""),
        " ".join(paper.get("authors", [])),
        claim.get("claim", ""),
        " ".join(claim.get("key_variables", [])),
        claim.get("context", ""),
        claim.get("evidence_type", ""),
        claim.get("evidence_strength", ""),
    ]
    return " ".join(part for part in parts if part).strip()


def fallback_search(query: str, papers: dict[str, dict], limit: int = 12) -> dict:
    query_tokens = tokenize(query)
    query_counts = Counter(query_tokens)
    scored_claims: list[tuple[float, dict, dict]] = []

    if not query_tokens:
        return {
            "matching_claim_ids": [],
            "summary": "No search terms were provided, so the local fallback search did not rank any claims.",
            "paper_ids": [],
            "used_fallback": True,
            "fallback_error": "",
        }

    for paper in papers.values():
        for claim in paper.get("claims", []):
            haystack = build_claim_search_text(paper, claim)
            haystack_tokens = tokenize(haystack)
            haystack_counts = Counter(haystack_tokens)
            score = 0.0

            for token, weight in query_counts.items():
                score += min(haystack_counts.get(token, 0), 3) * weight

            lowered_text = haystack.lower()
            if query.lower().strip() and query.lower().strip() in lowered_text:
                score += 5.0

            if claim.get("evidence_strength") == "strong":
                score += 0.25

            if score > 0:
                scored_claims.append((score, paper, claim))

    scored_claims.sort(
        key=lambda item: (
            -item[0],
            item[1].get("year") or 0,
            item[1].get("title", ""),
        )
    )
    top_matches = scored_claims[:limit]
    matching_claim_ids = [claim["claim_id"] for _, _, claim in top_matches]
    paper_ids = list(dict.fromkeys(paper["paper_id"] for _, paper, _ in top_matches))

    if not top_matches:
        return {
            "matching_claim_ids": [],
            "summary": "Local fallback search did not find any claims with meaningful token overlap for that query.",
            "paper_ids": [],
            "used_fallback": True,
            "fallback_error": "",
        }

    claim_preview = "; ".join(
        claim["claim"][:120].rstrip(".") for _, _, claim in top_matches[:3]
    )
    summary = (
        f"Local fallback search surfaced {len(matching_claim_ids)} claims across "
        f"{len(paper_ids)} papers. Top matches include: {claim_preview}."
    )

    return {
        "matching_claim_ids": matching_claim_ids,
        "summary": summary,
        "paper_ids": paper_ids,
        "used_fallback": True,
        "fallback_error": "",
    }
