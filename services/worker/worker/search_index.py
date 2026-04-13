from __future__ import annotations

import hashlib
import math
import os
import re


TOKEN_RE = re.compile(r"[a-z0-9]+")
EMBEDDING_DIMENSIONS = int(os.getenv("HYPATIA_SEARCH_EMBEDDING_DIMENSIONS", "256"))


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def build_claim_search_text(
    *,
    paper_title: str,
    paper_authors: list[str],
    claim: dict,
) -> str:
    parts = [
        paper_title,
        " ".join(paper_authors),
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
    return [round(value / magnitude, 6) for value in vector]


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
