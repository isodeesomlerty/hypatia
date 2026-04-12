from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    CACHE_DIR,
    DEFAULT_MANIFEST,
    MANIFEST_PATH,
    PAIR_CACHE_DIR,
    PAPER_CACHE_DIR,
    PAPER_EDGES_PATH,
    PAPERS_PATH,
    RELATIONSHIPS_PATH,
    ensure_project_dirs,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return deepcopy(default)

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return deepcopy(default)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def load_manifest() -> dict:
    ensure_project_dirs()
    manifest = read_json(MANIFEST_PATH, DEFAULT_MANIFEST)
    if manifest is None:
        manifest = deepcopy(DEFAULT_MANIFEST)

    normalized = deepcopy(DEFAULT_MANIFEST)
    normalized.update(manifest)
    normalized["papers_by_hash"] = dict(manifest.get("papers_by_hash", {}))
    normalized["processed_pairs"] = dict(manifest.get("processed_pairs", {}))
    normalized["failed_pairs"] = dict(manifest.get("failed_pairs", {}))
    normalized["failed_files"] = dict(manifest.get("failed_files", {}))
    return normalized


def save_manifest(manifest: dict) -> None:
    write_json(MANIFEST_PATH, manifest)


def _delete_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    collapsed = re.sub(r"[^a-z0-9]+", "-", lowered)
    return collapsed.strip("-") or "paper"


def make_paper_id(title: str, source_hash: str, year: int | None = None) -> str:
    pieces = [slugify(title)[:48]]
    if year:
        pieces.append(str(year))
    pieces.append(source_hash[:8])
    return "-".join(piece for piece in pieces if piece)


def pair_key(paper_a_id: str, paper_b_id: str) -> str:
    left, right = sorted((paper_a_id, paper_b_id))
    return f"{left}||{right}"


def pair_cache_filename(paper_a_id: str, paper_b_id: str) -> str:
    left, right = sorted((paper_a_id, paper_b_id))
    return f"{left}__{right}.json"


def paper_cache_path_for_hash(source_hash: str) -> Path:
    return PAPER_CACHE_DIR / f"{source_hash}.json"


def pair_cache_path_from_key(key: str) -> Path:
    left, right = key.split("||", maxsplit=1)
    return PAIR_CACHE_DIR / pair_cache_filename(left, right)


def save_paper_record(paper: dict, manifest: dict, analysis_signature: str | None = None) -> None:
    source_hash = paper["source_hash"]
    cache_path = paper_cache_path_for_hash(source_hash)
    write_json(cache_path, paper)

    entry = {
        "paper_id": paper["paper_id"],
        "source_filename": paper["source_filename"],
        "paper_cache_path": str(cache_path.relative_to(CACHE_DIR)),
        "status": "ready",
        "ingestion_mode": paper.get("ingestion_mode"),
        "updated_at": utc_now_iso(),
    }
    if analysis_signature:
        entry["analysis_signature"] = analysis_signature
    manifest["papers_by_hash"][source_hash] = entry
    manifest["failed_files"].pop(source_hash, None)


def save_pair_relationships(
    paper_a_id: str,
    paper_b_id: str,
    relationships: list[dict],
    manifest: dict,
    pairwise_signature: str | None = None,
) -> None:
    key = pair_key(paper_a_id, paper_b_id)
    cache_path = pair_cache_path_from_key(key)
    payload = {
        "pair_key": key,
        "paper_a_id": min(paper_a_id, paper_b_id),
        "paper_b_id": max(paper_a_id, paper_b_id),
        "relationship_count": len(relationships),
        "relationships": relationships,
        "updated_at": utc_now_iso(),
    }
    write_json(cache_path, payload)
    manifest["processed_pairs"][key] = {
        "pair_cache_path": str(cache_path.relative_to(CACHE_DIR)),
        "relationship_count": len(relationships),
        "updated_at": payload["updated_at"],
    }
    if pairwise_signature:
        manifest["processed_pairs"][key]["pairwise_signature"] = pairwise_signature
    manifest.get("failed_pairs", {}).pop(key, None)


def record_failed_pair(
    paper_a_id: str,
    paper_b_id: str,
    error: str,
    manifest: dict,
    *,
    error_kind: str = "unknown",
    retryable: bool = True,
) -> None:
    key = pair_key(paper_a_id, paper_b_id)
    manifest.setdefault("failed_pairs", {})[key] = {
        "paper_a_id": min(paper_a_id, paper_b_id),
        "paper_b_id": max(paper_a_id, paper_b_id),
        "error": error,
        "error_kind": error_kind,
        "retryable": retryable,
        "updated_at": utc_now_iso(),
    }


def remove_paper_record(paper: dict, manifest: dict) -> None:
    source_hash = paper.get("source_hash", "")
    entry = manifest.get("papers_by_hash", {}).pop(source_hash, None)
    rel_path = None
    if entry:
        rel_path = entry.get("paper_cache_path")
    if rel_path:
        _delete_path(CACHE_DIR / rel_path)
    elif source_hash:
        _delete_path(paper_cache_path_for_hash(source_hash))
    manifest.get("failed_files", {}).pop(source_hash, None)


def remove_pair_relationships_for_paper(paper_id: str, manifest: dict) -> None:
    processed_pairs = manifest.get("processed_pairs", {})
    for key in list(processed_pairs):
        if paper_id not in key.split("||", maxsplit=1):
            continue
        entry = processed_pairs.pop(key)
        rel_path = entry.get("pair_cache_path")
        if rel_path:
            _delete_path(CACHE_DIR / rel_path)
    failed_pairs = manifest.get("failed_pairs", {})
    for key in list(failed_pairs):
        if paper_id not in key.split("||", maxsplit=1):
            continue
        failed_pairs.pop(key, None)


def clear_cached_corpus() -> dict:
    ensure_project_dirs()
    for path in (
        PAPERS_PATH,
        RELATIONSHIPS_PATH,
        PAPER_EDGES_PATH,
        MANIFEST_PATH,
    ):
        _delete_path(path)
    for directory in (PAPER_CACHE_DIR, PAIR_CACHE_DIR):
        _delete_path(directory)
        directory.mkdir(parents=True, exist_ok=True)
    manifest = deepcopy(DEFAULT_MANIFEST)
    save_manifest(manifest)
    return manifest


def record_failed_file(path: Path, source_hash: str, error: Exception, manifest: dict) -> None:
    manifest["failed_files"][source_hash] = {
        "source_filename": path.name,
        "error": str(error),
        "updated_at": utc_now_iso(),
    }


def serialize_paper_edges(paper_edges: dict[tuple[str, str], dict]) -> dict[str, dict]:
    return {pair_key(left, right): data for (left, right), data in paper_edges.items()}


def deserialize_paper_edges(payload: dict[str, dict] | None) -> dict[tuple[str, str], dict]:
    if not payload:
        return {}
    return {
        tuple(key.split("||", maxsplit=1)): value
        for key, value in payload.items()
        if "||" in key
    }


def load_all_paper_records(
    manifest: dict,
    analysis_signature: str | None = None,
) -> dict[str, dict]:
    papers: dict[str, dict] = {}
    for entry in manifest.get("papers_by_hash", {}).values():
        if analysis_signature and entry.get("analysis_signature") != analysis_signature:
            continue
        rel_path = entry.get("paper_cache_path")
        if not rel_path:
            continue
        payload = read_json(CACHE_DIR / rel_path)
        if payload:
            papers[payload["paper_id"]] = payload
    return papers


def load_all_pair_relationships(
    manifest: dict,
    pairwise_signature: str | None = None,
) -> list[dict]:
    relationships: list[dict] = []
    for entry in manifest.get("processed_pairs", {}).values():
        if pairwise_signature and entry.get("pairwise_signature") != pairwise_signature:
            continue
        rel_path = entry.get("pair_cache_path")
        if not rel_path:
            continue
        payload = read_json(CACHE_DIR / rel_path, {})
        relationships.extend(payload.get("relationships", []))
    return relationships


def save_combined_dataset(
    papers: dict[str, dict],
    relationships: list[dict],
    paper_edges: dict[tuple[str, str], dict],
    manifest: dict,
) -> None:
    write_json(PAPERS_PATH, papers)
    write_json(RELATIONSHIPS_PATH, relationships)
    write_json(PAPER_EDGES_PATH, serialize_paper_edges(paper_edges))
    save_manifest(manifest)


def load_cached_dataset(
    analysis_signature: str | None = None,
    pairwise_signature: str | None = None,
) -> tuple[dict[str, dict], list[dict], dict[tuple[str, str], dict], dict]:
    ensure_project_dirs()
    manifest = load_manifest()

    if analysis_signature or pairwise_signature:
        rebuilt_papers = load_all_paper_records(
            manifest,
            analysis_signature=analysis_signature,
        )
        rebuilt_relationships = load_all_pair_relationships(
            manifest,
            pairwise_signature=pairwise_signature,
        )
        return rebuilt_papers, rebuilt_relationships, {}, manifest

    papers = read_json(PAPERS_PATH, {})
    relationships = read_json(RELATIONSHIPS_PATH, [])
    paper_edges = deserialize_paper_edges(read_json(PAPER_EDGES_PATH, {}))
    if papers:
        return papers, relationships or [], paper_edges, manifest

    rebuilt_papers = load_all_paper_records(manifest)
    rebuilt_relationships = load_all_pair_relationships(manifest)
    return rebuilt_papers, rebuilt_relationships, paper_edges, manifest
