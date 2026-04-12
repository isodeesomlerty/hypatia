from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
PAPER_CACHE_DIR = CACHE_DIR / "papers"
PAIR_CACHE_DIR = CACHE_DIR / "pairs"

MANIFEST_PATH = CACHE_DIR / "manifest.json"
PAPERS_PATH = CACHE_DIR / "papers.json"
RELATIONSHIPS_PATH = CACHE_DIR / "relationships.json"
PAPER_EDGES_PATH = CACHE_DIR / "paper_edges.json"

API_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"
FILES_API_BETA = "files-api-2025-04-14"

PAPER_ANALYSIS_MODEL = (
    os.getenv("RG_PAPER_ANALYSIS_MODEL")
    or os.getenv("RG_CLAIM_MODEL")
    or os.getenv("RG_HEALTH_MODEL")
    or "claude-sonnet-4-6"
)
PAPER_ANALYSIS_INPUT_MODE = os.getenv("RG_PAPER_ANALYSIS_INPUT_MODE", "text_first").lower()
PAPER_ANALYSIS_TEXT_CHAR_LIMIT = int(os.getenv("RG_PAPER_ANALYSIS_TEXT_CHAR_LIMIT", "36000"))
PAPER_ANALYSIS_PDF_PAGE_THRESHOLD = int(
    os.getenv("RG_PAPER_ANALYSIS_PDF_PAGE_THRESHOLD", "8")
)
SEARCH_MODEL = os.getenv("RG_SEARCH_MODEL", "claude-sonnet-4-6")
RELATIONSHIP_MODEL = os.getenv("RG_RELATIONSHIP_MODEL", "claude-haiku-4-5-20251001")

PDF_MAX_PAGES = int(os.getenv("RG_PDF_MAX_PAGES", "100"))
PDF_MAX_FILE_MB = int(os.getenv("RG_PDF_MAX_FILE_MB", "32"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("RG_REQUEST_TIMEOUT_SECONDS", "180"))
SEARCH_TIMEOUT_SECONDS = int(os.getenv("RG_SEARCH_TIMEOUT_SECONDS", "60"))
EXTRACTION_WORKERS = int(os.getenv("RG_EXTRACTION_WORKERS", "8"))
PAIRWISE_WORKERS = int(os.getenv("RG_PAIRWISE_WORKERS", "16"))
PAIRWISE_MAX_TOKENS = int(os.getenv("RG_PAIRWISE_MAX_TOKENS", "4096"))
PAIRWISE_RETRY_MAX_TOKENS = int(os.getenv("RG_PAIRWISE_RETRY_MAX_TOKENS", "6144"))
API_MAX_RETRIES = int(os.getenv("RG_API_MAX_RETRIES", "2"))
API_RETRY_BASE_DELAY_SECONDS = float(os.getenv("RG_API_RETRY_BASE_DELAY_SECONDS", "1.0"))

VISUAL_RELATIONSHIPS = ("contradicts", "supports", "extends", "qualifies")
NON_VISUAL_RELATIONSHIPS = ("uses_same_method", "uses_same_data")
ALL_RELATIONSHIPS = VISUAL_RELATIONSHIPS + NON_VISUAL_RELATIONSHIPS

HEALTH_COLORS = {
    "healthy": "#5E897D",
    "caution": "#B78345",
    "concern": "#AB5E51",
}

HEALTH_ICONS = {
    "healthy": "Healthy",
    "caution": "Caution",
    "concern": "Concern",
}

EDGE_COLORS = {
    "contradicts": "#B06A5A",
    "supports": "#5F806E",
    "extends": "#8B8268",
    "qualifies": "#B59058",
}

DEFAULT_MANIFEST = {
    "version": 1,
    "papers_by_hash": {},
    "processed_pairs": {},
    "failed_pairs": {},
    "failed_files": {},
}


def ensure_project_dirs() -> None:
    for path in (DATA_DIR, RAW_DIR, CACHE_DIR, PAPER_CACHE_DIR, PAIR_CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
