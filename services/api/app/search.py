from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass


TOKEN_RE = re.compile(r"[a-z0-9]+")
EMBEDDING_DIMENSIONS = 128


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
        claim.get("claim_type", ""),
    ]
    return " ".join(part for part in parts if part).strip()


def _stable_bucket(token: str) -> tuple[int, float]:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
    sign = -1.0 if digest[4] & 1 else 1.0
    return bucket, sign


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 1e-9:
        return [0.0] * len(vector)
    return [value / magnitude for value in vector]


def embed_text(text: str) -> list[float]:
    tokens = tokenize(text)
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in tokens:
        bucket, sign = _stable_bucket(token)
        vector[bucket] += sign
    for first, second in zip(tokens, tokens[1:]):
        bucket, sign = _stable_bucket(f"{first}:{second}")
        vector[bucket] += 0.6 * sign
    return _normalize(vector)


def _coerce_embedding(value) -> list[float]:
    if not isinstance(value, list):
        return []
    floats = [float(item) for item in value if isinstance(item, (int, float))]
    if len(floats) != EMBEDDING_DIMENSIONS:
        return []
    return floats


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def lexical_overlap_score(
    query_counts: Counter[str],
    haystack_counts: Counter[str],
) -> float:
    score = 0.0
    for token, weight in query_counts.items():
        score += min(haystack_counts.get(token, 0), 3) * weight
    return score


@dataclass(frozen=True)
class SearchMatch:
    score: float
    lexical_score: float
    semantic_score: float
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
    query_embedding = embed_text(query)
    scored_claims: list[SearchMatch] = []

    if not query_tokens:
        return {
            "summary": "No search terms were provided, so Hypatia did not rank any claims yet.",
            "matches": [],
            "paper_ids": [],
            "matching_claim_ids": [],
            "used_fallback": False,
            "search_mode": "hybrid_claim_ranking",
        }

    normalized_query = query.lower().strip()
    semantic_matches = 0
    for paper in papers:
        for claim in paper.get("claims", []):
            haystack = claim.get("search_text") or build_claim_search_text(paper, claim)
            haystack_tokens = tokenize(haystack)
            haystack_counts = Counter(haystack_tokens)
            lexical_score = lexical_overlap_score(query_counts, haystack_counts)
            semantic_embedding = _coerce_embedding(claim.get("search_embedding"))
            if not semantic_embedding:
                semantic_embedding = embed_text(haystack)
            semantic_score = max(cosine_similarity(query_embedding, semantic_embedding), 0.0)

            score = lexical_score + (semantic_score * 3.0)

            lowered_text = haystack.lower()
            if normalized_query and normalized_query in lowered_text:
                score += 5.0
                lexical_score += 5.0

            if claim.get("evidence_strength") == "strong":
                score += 0.25

            if semantic_score >= 0.2:
                semantic_matches += 1

            if lexical_score > 0 or semantic_score >= 0.18:
                scored_claims.append(
                    SearchMatch(
                        score=score,
                        lexical_score=lexical_score,
                        semantic_score=semantic_score,
                        paper=paper,
                        claim=claim,
                    )
                )

    scored_claims.sort(
        key=lambda item: (
            -item.score,
            -item.semantic_score,
            item.paper.get("year") or 0,
            item.paper.get("title", ""),
        )
    )

    top_matches = scored_claims[:limit]
    matching_claim_ids = [match.claim["claim_id"] for match in top_matches]
    paper_ids = list(dict.fromkeys(match.paper["paper_id"] for match in top_matches))

    if not top_matches:
        return {
            "summary": (
                "Hypatia did not find any claims with enough lexical or semantic "
                "overlap for that query yet."
            ),
            "matches": [],
            "paper_ids": [],
            "matching_claim_ids": [],
            "used_fallback": False,
            "search_mode": "hybrid_claim_ranking",
        }

    claim_preview = "; ".join(
        match.claim["claim"][:120].rstrip(".") for match in top_matches[:3]
    )
    summary = (
        f"Hypatia surfaced {len(matching_claim_ids)} claims across "
        f"{len(paper_ids)} papers with hybrid lexical + vector ranking. "
        f"Top matches include: {claim_preview}."
    )
    if semantic_matches:
        summary += f" {semantic_matches} candidate claims also showed semantic similarity."

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
                "score": round(match.score, 4),
            }
            for match in top_matches
        ],
        "paper_ids": paper_ids,
        "matching_claim_ids": matching_claim_ids,
        "used_fallback": False,
        "search_mode": "hybrid_claim_ranking",
    }
