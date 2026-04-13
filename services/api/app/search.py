from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


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


@dataclass(frozen=True)
class SearchMatch:
    score: float
    paper: dict
    claim: dict


def search_workspace_claims(
    query: str,
    papers: list[dict],
    *,
    limit: int = 12,
) -> dict:
    query_tokens = tokenize(query)
    query_counts = Counter(query_tokens)
    scored_claims: list[SearchMatch] = []

    if not query_tokens:
        return {
            "summary": "No search terms were provided, so Hypatia did not rank any claims yet.",
            "matches": [],
            "paper_ids": [],
            "matching_claim_ids": [],
            "used_fallback": True,
            "search_mode": "local_claim_ranking",
        }

    normalized_query = query.lower().strip()
    for paper in papers:
        for claim in paper.get("claims", []):
            haystack = build_claim_search_text(paper, claim)
            haystack_tokens = tokenize(haystack)
            haystack_counts = Counter(haystack_tokens)
            score = 0.0

            for token, weight in query_counts.items():
                score += min(haystack_counts.get(token, 0), 3) * weight

            lowered_text = haystack.lower()
            if normalized_query and normalized_query in lowered_text:
                score += 5.0

            if claim.get("evidence_strength") == "strong":
                score += 0.25

            if score > 0:
                scored_claims.append(SearchMatch(score=score, paper=paper, claim=claim))

    scored_claims.sort(
        key=lambda item: (
            -item.score,
            item.paper.get("year") or 0,
            item.paper.get("title", ""),
        )
    )

    top_matches = scored_claims[:limit]
    matching_claim_ids = [match.claim["claim_id"] for match in top_matches]
    paper_ids = list(dict.fromkeys(match.paper["paper_id"] for match in top_matches))

    if not top_matches:
        return {
            "summary": "Hypatia did not find any claims with meaningful token overlap for that query.",
            "matches": [],
            "paper_ids": [],
            "matching_claim_ids": [],
            "used_fallback": True,
            "search_mode": "local_claim_ranking",
        }

    claim_preview = "; ".join(
        match.claim["claim"][:120].rstrip(".") for match in top_matches[:3]
    )
    summary = (
        f"Hypatia surfaced {len(matching_claim_ids)} claims across "
        f"{len(paper_ids)} papers. Top matches include: {claim_preview}."
    )

    return {
        "summary": summary,
        "matches": [
            {
                "paper_id": match.paper["paper_id"],
                "paper_title": match.paper.get("title", ""),
                "paper_authors": match.paper.get("authors", []),
                "paper_year": match.paper.get("year"),
                "claim_id": match.claim["claim_id"],
                "claim_text": match.claim.get("claim", ""),
                "claim_type": match.claim.get("claim_type", "descriptive"),
                "evidence_strength": match.claim.get("evidence_strength", "moderate"),
                "context": match.claim.get("context", ""),
                "score": match.score,
            }
            for match in top_matches
        ],
        "paper_ids": paper_ids,
        "matching_claim_ids": matching_claim_ids,
        "used_fallback": True,
        "search_mode": "local_claim_ranking",
    }
