from __future__ import annotations

import json
from urllib import error, request

from worker.config import settings
from worker.search_index import embed_text


class EmbeddingProviderError(RuntimeError):
    pass


def active_embedding_provider() -> str:
    configured = settings.search_embedding_provider.lower()
    if configured == "local":
        return "local"
    if settings.search_embedding_openai_api_key:
        return "openai"
    return "local"


def _openai_embeddings(texts: list[str]) -> list[list[float]]:
    base_url = settings.search_embedding_openai_base_url.rstrip("/")
    payload = {
        "model": settings.search_embedding_model,
        "input": texts,
        "encoding_format": "float",
        "dimensions": settings.search_embedding_dimensions,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}/embeddings",
        data=data,
        headers={
            "Authorization": f"Bearer {settings.search_embedding_openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        raise EmbeddingProviderError(f"Embedding request failed: {exc}") from exc

    items = body.get("data", [])
    vectors = [item.get("embedding") for item in items if isinstance(item, dict)]
    if len(vectors) != len(texts):
        raise EmbeddingProviderError("Embedding response did not match the requested inputs.")
    return vectors


def embed_search_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    provider = active_embedding_provider()
    configured = settings.search_embedding_provider.lower()
    if provider == "openai":
        try:
            return _openai_embeddings(texts), "openai"
        except EmbeddingProviderError:
            if configured == "openai":
                raise
    return [embed_text(text) for text in texts], "local"


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"
