from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

import fitz
import pdfplumber
import requests

from .cache import (
    compute_sha256,
    current_pairwise_status,
    display_path,
    load_all_pair_relationships,
    load_all_paper_records,
    load_manifest,
    make_paper_id,
    pair_key,
    record_failed_file,
    save_combined_dataset,
    save_pair_failure_artifact,
    save_pair_relationships,
    save_paper_record,
)
from .config import (
    ALL_RELATIONSHIPS,
    API_MAX_RETRIES,
    API_BASE_URL,
    API_RETRY_BASE_DELAY_SECONDS,
    API_VERSION,
    CACHE_DIR,
    EXTRACTION_WORKERS,
    FILES_API_BETA,
    MEASURES_PATH,
    PAIRWISE_COMPACT_CLAIMS_PER_PAPER,
    PAIRWISE_FALLBACK_MAX_TOKENS,
    PAIRWISE_MAX_TOKENS,
    PAIRWISE_SERIAL_RETRY_ATTEMPTS,
    PAIRWISE_WORKERS,
    PAPER_ANALYSIS_INPUT_MODE,
    PAPER_ANALYSIS_MODEL,
    PAPER_ANALYSIS_PDF_PAGE_THRESHOLD,
    PAPER_ANALYSIS_TEXT_CHAR_LIMIT,
    PDF_MAX_FILE_MB,
    PDF_MAX_PAGES,
    RAW_DIR,
    RELATIONSHIP_MODEL,
    REQUEST_TIMEOUT_SECONDS,
    SEARCH_MODEL,
    SEARCH_TIMEOUT_SECONDS,
    SUPPRESS_PDF_PARSER_WARNINGS,
    ensure_project_dirs,
)
from .measures import compute_measures
from .graph import aggregate_paper_edges, paper_ids_for_claim_ids
from .prompts import (
    PAIRWISE_RELATIONSHIP_SYSTEM_PROMPT,
    PAPER_ANALYSIS_SYSTEM_PROMPT,
    SEARCH_SYSTEM_PROMPT,
)
from .schemas import (
    PAPER_ANALYSIS_SCHEMA,
    RELATIONSHIP_SCHEMA,
    SEARCH_SCHEMA,
    validate_payload,
)
from .search import fallback_search


class ResearchGraphError(RuntimeError):
    """Base pipeline exception."""


class ClaudeAPIError(ResearchGraphError):
    """Raised when Claude API calls fail."""


class ClaudeResponseFormatError(ClaudeAPIError):
    """Raised when Claude returns malformed structured output."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "response_format_error",
        raw_text: str = "",
        response_payload: dict[str, Any] | None = None,
        model: str | None = None,
        request_name: str | None = None,
        prompt_mode: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.raw_text = raw_text
        self.response_payload = response_payload or {}
        self.model = model
        self.request_name = request_name
        self.prompt_mode = prompt_mode

    def debug_payload(self) -> dict[str, Any]:
        return {
            "error_type": self.error_code,
            "model": self.model,
            "request_name": self.request_name,
            "prompt_mode": self.prompt_mode,
            "raw_response_text": self.raw_text,
            "raw_response_text_length": len(self.raw_text),
            "response_id": self.response_payload.get("id"),
            "stop_reason": self.response_payload.get("stop_reason"),
            "stop_sequence": self.response_payload.get("stop_sequence"),
            "usage": self.response_payload.get("usage"),
        }


class PDFGuardrailError(ResearchGraphError):
    """Raised when a PDF should not be processed."""


ProgressCallback = Callable[[dict[str, Any]], None]
TITLE_TOKEN_RE = re.compile(r"[a-z0-9]+")
REFERENCES_HEADING_RE = re.compile(r"(?im)^\s*(references|bibliography|works cited)\s*$")
TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def _signature_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


PAPER_ANALYSIS_SIGNATURE = _signature_hash(
    {
        "version": "paper-analysis-v3",
        "paper_analysis_model": PAPER_ANALYSIS_MODEL,
        "paper_analysis_prompt": PAPER_ANALYSIS_SYSTEM_PROMPT,
        "paper_analysis_schema": PAPER_ANALYSIS_SCHEMA,
    }
)

PAIRWISE_ANALYSIS_SIGNATURE = _signature_hash(
    {
        "version": "pairwise-analysis-v2",
        "paper_analysis_signature": PAPER_ANALYSIS_SIGNATURE,
        "relationship_model": RELATIONSHIP_MODEL,
        "relationship_prompt": PAIRWISE_RELATIONSHIP_SYSTEM_PROMPT,
        "relationship_schema": RELATIONSHIP_SCHEMA,
    }
)


def _normalized_title_tokens(title: str) -> list[str]:
    tokens = TITLE_TOKEN_RE.findall((title or "").lower())
    filtered = [token for token in tokens if token not in TITLE_STOPWORDS]
    return filtered or tokens


def _normalized_title_string(title: str) -> str:
    return " ".join(_normalized_title_tokens(title))


def _author_last_names(authors: list[str] | None) -> set[str]:
    last_names: set[str] = set()
    for author in authors or []:
        parts = TITLE_TOKEN_RE.findall((author or "").lower())
        if parts:
            last_names.add(parts[-1])
    return last_names


def detect_potential_duplicates(
    paper: dict,
    existing_papers: dict[str, dict],
    limit: int = 3,
) -> list[dict]:
    uploaded_title = paper.get("title", "")
    uploaded_title_norm = _normalized_title_string(uploaded_title)
    uploaded_year = paper.get("year")
    uploaded_authors = _author_last_names(paper.get("authors", []))
    matches: list[dict] = []

    for existing in existing_papers.values():
        reasons: list[str] = []
        score = 0.0

        if existing.get("paper_id") == paper.get("paper_id"):
            reasons.append("same PDF is already in the map")
            score = 10.0
        else:
            existing_title_norm = _normalized_title_string(existing.get("title", ""))
            if not uploaded_title_norm or not existing_title_norm:
                continue

            title_similarity = SequenceMatcher(None, uploaded_title_norm, existing_title_norm).ratio()
            uploaded_tokens = set(uploaded_title_norm.split())
            existing_tokens = set(existing_title_norm.split())
            token_overlap = (
                len(uploaded_tokens & existing_tokens) / max(1, len(uploaded_tokens | existing_tokens))
            )
            year_match = bool(uploaded_year and existing.get("year") and uploaded_year == existing.get("year"))
            existing_authors = _author_last_names(existing.get("authors", []))
            shared_authors = uploaded_authors & existing_authors
            author_overlap = len(shared_authors) / max(1, min(len(uploaded_authors), len(existing_authors) or 1))

            if uploaded_title_norm == existing_title_norm:
                reasons.append("same normalized title")
                score += 0.8
            elif title_similarity >= 0.96:
                reasons.append("nearly identical title")
                score += 0.75
            elif title_similarity >= 0.88 and token_overlap >= 0.72:
                reasons.append("very similar title")
                score += 0.6
            else:
                continue

            if year_match:
                reasons.append(f"same year ({uploaded_year})")
                score += 0.2

            if shared_authors:
                if author_overlap >= 0.5:
                    reasons.append("strong author overlap")
                    score += 0.2
                else:
                    reasons.append("some author overlap")
                    score += 0.1

            if score < 0.75:
                continue

        matches.append(
            {
                "paper_id": existing.get("paper_id"),
                "title": existing.get("title", "Untitled paper"),
                "year": existing.get("year"),
                "authors": existing.get("authors", []),
                "reasons": reasons,
                "score": round(score, 2),
            }
        )

    matches.sort(key=lambda item: (-item["score"], item["year"] or 0, item["title"]))
    return matches[:limit]


def _emit_progress(
    callback: ProgressCallback | None,
    *,
    stage: str,
    message: str,
    progress: float | None = None,
    current: int | None = None,
    total: int | None = None,
    **extra: Any,
) -> None:
    if not callback:
        return

    event: dict[str, Any] = {
        "stage": stage,
        "message": message,
    }
    if progress is not None:
        event["progress"] = max(0.0, min(progress, 1.0))
    if current is not None:
        event["current"] = current
    if total is not None:
        event["total"] = total
    event.update(extra)
    callback(event)


def _api_key() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ResearchGraphError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or .env file."
        )
    return api_key


def _claude_headers(include_files_beta: bool = False) -> dict[str, str]:
    headers = {
        "x-api-key": _api_key(),
        "anthropic-version": API_VERSION,
    }
    if include_files_beta:
        headers["anthropic-beta"] = FILES_API_BETA
    return headers


def _message_headers(include_files_beta: bool = False) -> dict[str, str]:
    headers = _claude_headers(include_files_beta=include_files_beta)
    headers["content-type"] = "application/json"
    return headers


def _parse_message_text(response_payload: dict) -> str:
    text_chunks = [
        block.get("text", "")
        for block in response_payload.get("content", [])
        if block.get("type") == "text"
    ]
    text = "".join(text_chunks).strip()
    if not text:
        raise ClaudeAPIError("Claude returned no text content in the response.")
    return text


def _raise_api_error(response: requests.Response) -> None:
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message") or payload.get("message")
    except ValueError:
        message = response.text.strip()
    detail = message or f"HTTP {response.status_code}"
    raise ClaudeAPIError(detail)


def _is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 409, 429, 500, 502, 503, 504, 529}


def _retry_delay_seconds(attempt_index: int) -> float:
    return API_RETRY_BASE_DELAY_SECONDS * (2**attempt_index)


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
        return max(0.0, seconds)
    except (TypeError, ValueError):
        return None


def _parse_reset_time_seconds(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    try:
        reset_at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    return max(0.0, (reset_at - datetime.now(timezone.utc)).total_seconds())


def _response_retry_delay_seconds(response: requests.Response, attempt_index: int) -> float:
    header_delay = _parse_retry_after_seconds(response.headers.get("retry-after"))
    if header_delay is not None:
        return header_delay

    for header_name in (
        "anthropic-ratelimit-input-tokens-reset",
        "anthropic-ratelimit-output-tokens-reset",
        "anthropic-ratelimit-requests-reset",
        "anthropic-ratelimit-tokens-reset",
    ):
        reset_delay = _parse_reset_time_seconds(response.headers.get(header_name))
        if reset_delay is not None:
            return reset_delay

    fallback_delay = _retry_delay_seconds(attempt_index)
    if response.status_code == 429:
        return max(fallback_delay, 15.0)
    return fallback_delay


def _send_request_with_retry(
    request_fn: Callable[[], requests.Response],
) -> requests.Response:
    last_exception: Exception | None = None
    for attempt in range(API_MAX_RETRIES + 1):
        try:
            response = request_fn()
        except requests.RequestException as exc:
            last_exception = exc
            if attempt >= API_MAX_RETRIES:
                raise ClaudeAPIError(str(exc)) from exc
            time.sleep(_retry_delay_seconds(attempt))
            continue

        if response.status_code < 400:
            return response

        if _is_retryable_status(response.status_code) and attempt < API_MAX_RETRIES:
            time.sleep(_response_retry_delay_seconds(response, attempt))
            continue

        _raise_api_error(response)

    if last_exception:
        raise ClaudeAPIError(str(last_exception)) from last_exception
    raise ClaudeAPIError("Request failed after retries.")


def _post_message(
    *,
    model: str,
    system_prompt: str,
    content: list[dict[str, Any]],
    schema: dict[str, Any],
    max_tokens: int,
    timeout_seconds: int,
    include_files_beta: bool = False,
    request_name: str | None = None,
    prompt_mode: str | None = None,
) -> dict:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    }
    response = _send_request_with_retry(
        lambda: requests.post(
            f"{API_BASE_URL}/v1/messages",
            headers=_message_headers(include_files_beta=include_files_beta),
            json=payload,
            timeout=timeout_seconds,
        )
    )
    parsed = response.json()
    text = _parse_message_text(parsed)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClaudeResponseFormatError(
            f"Unterminated or malformed JSON returned by Claude: {exc}",
            error_code="malformed_json",
            raw_text=text,
            response_payload=parsed,
            model=model,
            request_name=request_name,
            prompt_mode=prompt_mode,
        ) from exc


def _upload_pdf_to_files_api(pdf_path: Path) -> dict:
    def _request() -> requests.Response:
        with pdf_path.open("rb") as handle:
            return requests.post(
                f"{API_BASE_URL}/v1/files",
                headers=_claude_headers(include_files_beta=True),
                files={"file": (pdf_path.name, handle, "application/pdf")},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

    response = _send_request_with_retry(_request)
    return response.json()


def _delete_uploaded_file(file_id: str) -> None:
    try:
        response = _send_request_with_retry(
            lambda: requests.delete(
                f"{API_BASE_URL}/v1/files/{file_id}",
                headers=_claude_headers(include_files_beta=True),
                timeout=30,
            )
        )
        if response.status_code >= 400:
            return
    except ClaudeAPIError:
        return


def _document_content(file_id: str, instruction: str) -> list[dict[str, Any]]:
    return [
        {"type": "text", "text": instruction},
        {
            "type": "document",
            "source": {
                "type": "file",
                "file_id": file_id,
            },
        },
    ]


def _text_content(text: str, instruction: str) -> list[dict[str, Any]]:
    return [
        {"type": "text", "text": instruction},
        {"type": "text", "text": text},
    ]


def inspect_pdf(pdf_path: Path) -> dict:
    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    try:
        with fitz.open(pdf_path) as document:
            page_count = document.page_count
            metadata = document.metadata or {}
            is_password_protected = bool(document.needs_pass)
    except Exception as exc:
        raise PDFGuardrailError(f"Could not open PDF: {exc}") from exc

    if is_password_protected:
        raise PDFGuardrailError(
            f"{pdf_path.name} is password-protected and cannot be processed."
        )
    if file_size_mb > PDF_MAX_FILE_MB:
        raise PDFGuardrailError(
            f"{pdf_path.name} is {file_size_mb:.1f}MB, above the {PDF_MAX_FILE_MB}MB limit."
        )
    if page_count > PDF_MAX_PAGES:
        raise PDFGuardrailError(
            f"{pdf_path.name} has {page_count} pages, above the {PDF_MAX_PAGES}-page limit."
        )

    return {
        "page_count": page_count,
        "file_size_mb": round(file_size_mb, 2),
        "metadata": metadata,
    }


@contextmanager
def _suppress_pdf_parser_noise() -> Any:
    if not SUPPRESS_PDF_PARSER_WARNINGS:
        yield
        return

    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        yield


def _extract_text_with_pdfplumber(pdf_path: Path) -> str:
    chunks: list[str] = []
    with _suppress_pdf_parser_noise():
        with pdfplumber.open(pdf_path) as document:
            for page in document.pages:
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(text)
    return "\n\n".join(chunks).strip()


def _extract_text_with_pymupdf(pdf_path: Path) -> str:
    chunks: list[str] = []
    with _suppress_pdf_parser_noise():
        with fitz.open(pdf_path) as document:
            for page in document:
                text = page.get_text("text") or ""
                if text.strip():
                    chunks.append(text)
    return "\n\n".join(chunks).strip()


def extract_text_locally(pdf_path: Path) -> str:
    primary = ""
    try:
        primary = _extract_text_with_pdfplumber(pdf_path)
    except Exception:
        primary = ""

    if len(primary) >= 500:
        return primary

    secondary = _extract_text_with_pymupdf(pdf_path)
    if len(secondary) >= len(primary):
        return secondary
    return primary


def _prepare_analysis_text(text: str) -> str:
    cleaned = (text or "").replace("\x00", " ")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    references_match = REFERENCES_HEADING_RE.search(cleaned)
    if references_match:
        cleaned = cleaned[: references_match.start()].rstrip()

    if len(cleaned) <= PAPER_ANALYSIS_TEXT_CHAR_LIMIT:
        return cleaned

    marker = "\n\n[... middle sections omitted for length ...]\n\n"
    head_chars = int(PAPER_ANALYSIS_TEXT_CHAR_LIMIT * 0.58)
    tail_chars = max(PAPER_ANALYSIS_TEXT_CHAR_LIMIT - head_chars - len(marker), 4000)
    if head_chars + tail_chars + len(marker) > PAPER_ANALYSIS_TEXT_CHAR_LIMIT:
        tail_chars = PAPER_ANALYSIS_TEXT_CHAR_LIMIT - head_chars - len(marker)

    head = cleaned[:head_chars].rstrip()
    tail = cleaned[-tail_chars:].lstrip()
    return f"{head}{marker}{tail}".strip()


def _preferred_paper_analysis_mode(pdf_info: dict) -> str:
    configured_mode = PAPER_ANALYSIS_INPUT_MODE.lower().strip()
    if configured_mode in {"text", "text_first"}:
        return "text"
    if configured_mode == "claude_pdf":
        return "claude_pdf"
    if configured_mode == "adaptive":
        if (pdf_info.get("page_count") or 0) <= PAPER_ANALYSIS_PDF_PAGE_THRESHOLD:
            return "claude_pdf"
        return "text"
    return "text"


def _normalize_metadata(
    raw_metadata: dict,
    pdf_path: Path,
    source_hash: str,
) -> tuple[str, str, list[str], int | None]:
    title = (raw_metadata.get("title") or "").strip() or pdf_path.stem.replace("_", " ")

    authors = raw_metadata.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    authors = [author.strip() for author in authors if author and author.strip()]

    year = raw_metadata.get("year")
    if isinstance(year, str) and year.isdigit():
        year = int(year)
    if not isinstance(year, int) or year < 1800 or year > 2100:
        year = None

    paper_id = make_paper_id(title, source_hash, year)
    return title, paper_id, authors, year


def _normalize_claims(claims: list[dict], paper_id: str) -> list[dict]:
    normalized: list[dict] = []
    for index, claim in enumerate(claims, start=1):
        normalized.append(
            {
                "claim_id": f"{paper_id}_claim{index}",
                "claim": claim.get("claim", "").strip(),
                "claim_type": claim.get("claim_type", "descriptive"),
                "evidence_type": claim.get("evidence_type", "other"),
                "evidence_strength": claim.get("evidence_strength", "moderate"),
                "evidence_reasoning": claim.get("evidence_reasoning", "").strip(),
                "key_variables": [item.strip() for item in claim.get("key_variables", []) if item and item.strip()],
                "context": claim.get("context", "").strip(),
            }
        )
    return normalized


def _normalize_health_result(health_payload: dict, paper_id: str) -> dict:
    return {
        "paper_id": paper_id,
        "overall_score": health_payload.get("overall_score", "caution"),
        "checks": [
            {
                "check": check.get("check", "").strip(),
                "status": check.get("status", "warn"),
                "detail": check.get("detail", "").strip(),
            }
            for check in health_payload.get("checks", [])
        ],
    }


def _build_paper_record(
    *,
    pdf_path: Path,
    source_hash: str,
    ingestion_mode: str,
    analysis_payload: dict,
    pdf_info: dict,
) -> dict:
    title, paper_id, authors, year = _normalize_metadata(
        analysis_payload.get("paper_metadata", {}),
        pdf_path,
        source_hash,
    )
    normalized_claims = _normalize_claims(analysis_payload.get("claims", []), paper_id)
    health_payload = analysis_payload.get("health_assessment", {})

    return {
        "paper_id": paper_id,
        "source_hash": source_hash,
        "source_filename": pdf_path.name,
        "title": title,
        "authors": authors,
        "year": year,
        "ingestion_mode": ingestion_mode,
        "page_count": pdf_info.get("page_count"),
        "file_size_mb": pdf_info.get("file_size_mb"),
        "health_score": _normalize_health_result(health_payload, paper_id),
        "claims": normalized_claims,
    }


def _analyze_pdf_document(file_id: str, source_name: str) -> dict:
    instruction = (
        f"Analyze the uploaded paper '{source_name}'. "
        "Return best-effort paper metadata, the authors' substantive claims, and a methodology health assessment."
    )
    payload = _post_message(
        model=PAPER_ANALYSIS_MODEL,
        system_prompt=PAPER_ANALYSIS_SYSTEM_PROMPT,
        content=_document_content(file_id, instruction),
        schema=PAPER_ANALYSIS_SCHEMA,
        max_tokens=6144,
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        include_files_beta=True,
    )
    validate_payload("paper_analysis", payload)
    return payload


def _analyze_text_document(text: str, source_name: str) -> dict:
    prepared_text = _prepare_analysis_text(text)
    instruction = (
        f"Analyze the paper text from '{source_name}'. "
        "Return best-effort paper metadata, the authors' substantive claims, and a methodology health assessment."
    )
    payload = _post_message(
        model=PAPER_ANALYSIS_MODEL,
        system_prompt=PAPER_ANALYSIS_SYSTEM_PROMPT,
        content=_text_content(prepared_text, instruction),
        schema=PAPER_ANALYSIS_SCHEMA,
        max_tokens=6144,
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        include_files_beta=False,
    )
    validate_payload("paper_analysis", payload)
    return payload


def _analyze_paper_via_text(
    *,
    pdf_path: Path,
    source_hash: str,
    pdf_info: dict,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    _emit_progress(
        progress_callback,
        stage="prepare_text",
        message="Preparing a lighter read.",
        progress=0.15,
        source_filename=pdf_path.name,
    )
    local_text = extract_text_locally(pdf_path)
    if not local_text.strip():
        raise ResearchGraphError(
            f"Local text extraction could not recover readable content from {pdf_path.name}."
        )

    _emit_progress(
        progress_callback,
        stage="extract_text",
        message="Extracting claims and assessing methodology.",
        progress=0.35,
        source_filename=pdf_path.name,
    )
    analysis_payload = _analyze_text_document(local_text, pdf_path.name)
    return _build_paper_record(
        pdf_path=pdf_path,
        source_hash=source_hash,
        ingestion_mode="local_text",
        analysis_payload=analysis_payload,
        pdf_info=pdf_info,
    )


def _analyze_paper_via_pdf(
    *,
    pdf_path: Path,
    source_hash: str,
    pdf_info: dict,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    file_id: str | None = None
    try:
        _emit_progress(
            progress_callback,
            stage="upload_pdf",
            message="Preparing for analysis.",
            progress=0.15,
            source_filename=pdf_path.name,
        )
        upload_result = _upload_pdf_to_files_api(pdf_path)
        file_id = upload_result["id"]

        _emit_progress(
            progress_callback,
            stage="extract_pdf",
            message="Extracting claims and assessing methodology.",
            progress=0.35,
            source_filename=pdf_path.name,
        )
        analysis_payload = _analyze_pdf_document(file_id, pdf_path.name)
        return _build_paper_record(
            pdf_path=pdf_path,
            source_hash=source_hash,
            ingestion_mode="claude_pdf",
            analysis_payload=analysis_payload,
            pdf_info=pdf_info,
        )
    finally:
        if file_id:
            _delete_uploaded_file(file_id)


def analyze_pdf(
    pdf_path: Path,
    manifest: dict | None = None,
    persist: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    ensure_project_dirs()
    manifest = manifest or load_manifest()
    source_hash = compute_sha256(pdf_path)
    cached_entry = manifest.get("papers_by_hash", {}).get(source_hash)
    if (
        cached_entry
        and cached_entry.get("analysis_signature") == PAPER_ANALYSIS_SIGNATURE
        and cached_entry.get("paper_cache_path")
    ):
        absolute = CACHE_DIR / cached_entry["paper_cache_path"]
        if absolute.exists():
            _emit_progress(
                progress_callback,
                stage="cache_hit",
                message="Using the saved analysis.",
                progress=0.45,
                source_filename=pdf_path.name,
            )
            with absolute.open("r", encoding="utf-8") as handle:
                return json.load(handle)

    _emit_progress(
        progress_callback,
        stage="inspect_pdf",
        message="Checking the paper.",
        progress=0.05,
        source_filename=pdf_path.name,
    )
    pdf_info = inspect_pdf(pdf_path)
    preferred_mode = _preferred_paper_analysis_mode(pdf_info)

    if preferred_mode == "text":
        try:
            paper = _analyze_paper_via_text(
                pdf_path=pdf_path,
                source_hash=source_hash,
                pdf_info=pdf_info,
                progress_callback=progress_callback,
            )
        except (ResearchGraphError, ClaudeAPIError, requests.RequestException) as exc:
            _emit_progress(
                progress_callback,
                stage="fallback_pdf",
                message="Trying the original PDF.",
                progress=0.22,
                source_filename=pdf_path.name,
                error=str(exc),
            )
            try:
                paper = _analyze_paper_via_pdf(
                    pdf_path=pdf_path,
                    source_hash=source_hash,
                    pdf_info=pdf_info,
                    progress_callback=progress_callback,
                )
            except (ClaudeAPIError, requests.RequestException, ResearchGraphError) as pdf_exc:
                raise ResearchGraphError(
                    f"Could not analyze {pdf_path.name} in text or PDF mode: {pdf_exc}"
                ) from pdf_exc
    else:
        try:
            paper = _analyze_paper_via_pdf(
                pdf_path=pdf_path,
                source_hash=source_hash,
                pdf_info=pdf_info,
                progress_callback=progress_callback,
            )
        except (ClaudeAPIError, requests.RequestException, ResearchGraphError) as exc:
            _emit_progress(
                progress_callback,
                stage="fallback_text",
                message="Switching to a lighter text read.",
                progress=0.22,
                source_filename=pdf_path.name,
                error=str(exc),
            )
            try:
                paper = _analyze_paper_via_text(
                    pdf_path=pdf_path,
                    source_hash=source_hash,
                    pdf_info=pdf_info,
                    progress_callback=progress_callback,
                )
            except (ResearchGraphError, ClaudeAPIError, requests.RequestException) as text_exc:
                raise ResearchGraphError(
                    f"Could not analyze {pdf_path.name} in PDF or text mode: {text_exc}"
                ) from text_exc

    if persist:
        _emit_progress(
            progress_callback,
            stage="save_paper",
            message="Saving the analysis.",
            progress=0.45,
            source_filename=pdf_path.name,
            paper_id=paper["paper_id"],
        )
        save_paper_record(paper, manifest, analysis_signature=PAPER_ANALYSIS_SIGNATURE)
    return paper


def _truncate_prompt_text(value: str | None, limit: int = 220) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _pairwise_claims_payload(claims: list[dict], *, compact: bool) -> list[dict]:
    if not compact:
        return claims

    compact_claims: list[dict[str, Any]] = []
    for claim in claims[:PAIRWISE_COMPACT_CLAIMS_PER_PAPER]:
        compact_claims.append(
            {
                "claim_id": claim.get("claim_id"),
                "claim": _truncate_prompt_text(claim.get("claim"), limit=360),
                "claim_type": claim.get("claim_type"),
                "evidence_strength": claim.get("evidence_strength"),
                "context": _truncate_prompt_text(claim.get("context"), limit=220),
                "key_variables": list(claim.get("key_variables", []))[:5],
            }
        )
    return compact_claims


def _pairwise_user_prompt(
    paper_a: dict,
    paper_b: dict,
    *,
    compact: bool,
) -> str:
    if compact:
        prompt_intro = (
            "Compact claim summaries are shown below because a previous structured-output "
            "attempt returned malformed JSON. Return only the strongest, clearest "
            "cross-paper relationships."
        )
    else:
        prompt_intro = "Full extracted claims are shown below."

    return (
        f"{prompt_intro}\n\n"
        f'Paper A: "{paper_a["title"]}"\n'
        f"Claims from Paper A:\n"
        f"{json.dumps(_pairwise_claims_payload(paper_a.get('claims', []), compact=compact), ensure_ascii=False)}\n\n"
        f'Paper B: "{paper_b["title"]}"\n'
        f"Claims from Paper B:\n"
        f"{json.dumps(_pairwise_claims_payload(paper_b.get('claims', []), compact=compact), ensure_ascii=False)}"
    )


def _clean_relationship_payload(payload: dict) -> list[dict]:
    validate_payload("relationships", payload)

    cleaned: list[dict] = []
    for relationship in payload.get("relationships", []):
        if relationship.get("relationship") not in ALL_RELATIONSHIPS:
            continue
        cleaned.append(relationship)
    return cleaned


def _compare_papers_once(
    paper_a: dict,
    paper_b: dict,
    *,
    compact: bool,
) -> list[dict]:
    payload = _post_message(
        model=RELATIONSHIP_MODEL,
        system_prompt=PAIRWISE_RELATIONSHIP_SYSTEM_PROMPT,
        content=[{"type": "text", "text": _pairwise_user_prompt(paper_a, paper_b, compact=compact)}],
        schema=RELATIONSHIP_SCHEMA,
        max_tokens=PAIRWISE_FALLBACK_MAX_TOKENS if compact else PAIRWISE_MAX_TOKENS,
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        include_files_beta=False,
        request_name="pairwise_relationships",
        prompt_mode="compact_claims_retry" if compact else "full_claims",
    )
    return _clean_relationship_payload(payload)


def compare_papers(paper_a: dict, paper_b: dict) -> list[dict]:
    try:
        return _compare_papers_once(paper_a, paper_b, compact=False)
    except ClaudeResponseFormatError as exc:
        try:
            return _compare_papers_once(paper_a, paper_b, compact=True)
        except Exception as retry_exc:
            raise retry_exc from exc


def _pair_error_type(error: Exception | str) -> str:
    if isinstance(error, ClaudeResponseFormatError):
        return error.error_code
    return getattr(error, "error_code", "pairwise_error")


def _pair_error_message(error: Exception | str) -> str:
    error_type = _pair_error_type(error)
    message = str(error).strip() or error_type
    if error_type != "pairwise_error" and not message.startswith(f"{error_type}:"):
        return f"{error_type}: {message}"
    return message


def _pair_failure(left: str, right: str, error: Exception | str) -> dict[str, str]:
    return {
        "pair_key": pair_key(left, right),
        "paper_a_id": left,
        "paper_b_id": right,
        "error": _pair_error_message(error),
    }


def _pair_progress_details(
    papers: dict[str, dict],
    left: str,
    right: str,
) -> dict[str, str]:
    return {
        "pair_key": pair_key(left, right),
        "paper_a_id": left,
        "paper_b_id": right,
        "paper_a_title": papers.get(left, {}).get("title", left),
        "paper_b_title": papers.get(right, {}).get("title", right),
    }


def _record_pair_failure(
    papers: dict[str, dict],
    left: str,
    right: str,
    error: Exception | str,
    *,
    pair_phase: str,
    retry_attempt: int | None = None,
) -> dict[str, str]:
    artifact_payload: dict[str, Any] = {
        **_pair_progress_details(papers, left, right),
        "pair_phase": pair_phase,
        "retry_attempt": retry_attempt,
        "error": _pair_error_message(error),
        "error_type": _pair_error_type(error),
    }
    if isinstance(error, ClaudeResponseFormatError):
        artifact_payload.update(error.debug_payload())

    artifact_path = save_pair_failure_artifact(left, right, artifact_payload)
    failure = _pair_failure(left, right, error)
    failure["debug_path"] = display_path(artifact_path)
    failure["error_type"] = artifact_payload["error_type"]
    return failure


def ensure_pairwise_relationships(
    papers: dict[str, dict],
    manifest: dict,
    only_pairs: list[tuple[str, str]] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[dict], list[dict]]:
    if only_pairs is None:
        paper_ids = sorted(papers)
        candidate_pairs = [
            (paper_ids[index], paper_ids[other_index])
            for index in range(len(paper_ids))
            for other_index in range(index + 1, len(paper_ids))
        ]
    else:
        candidate_pairs = [tuple(sorted(pair)) for pair in only_pairs if pair[0] != pair[1]]
    candidate_pairs = list(dict.fromkeys(candidate_pairs))

    existing_pairs = {
        key
        for key, entry in manifest.get("processed_pairs", {}).items()
        if (
            entry.get("pairwise_signature") == PAIRWISE_ANALYSIS_SIGNATURE
            and entry.get("pair_cache_path")
            and (CACHE_DIR / entry["pair_cache_path"]).exists()
        )
    }
    pairs_to_process = [
        pair for pair in candidate_pairs if pair_key(pair[0], pair[1]) not in existing_pairs
    ]
    candidate_pair_count = len(candidate_pairs)
    cached_pair_count = candidate_pair_count - len(pairs_to_process)

    failures: list[dict] = []
    if not pairs_to_process:
        _emit_progress(
            progress_callback,
            stage="pairwise_complete",
            message=(
                "All candidate paper comparisons were already cached; "
                "skipping fresh pairwise analysis."
                if candidate_pair_count
                else "No paper comparisons were needed."
            ),
            progress=1.0,
            current=candidate_pair_count,
            total=candidate_pair_count,
            candidate_pairs_total=candidate_pair_count,
            cached_pairs_skipped=cached_pair_count,
            fresh_pairs_total=0,
            successful_pairs_count=0,
            failed_pairs_count=0,
            skipped_all_cached=bool(candidate_pair_count),
        )
        return load_all_pair_relationships(
            manifest,
            pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
        ), failures

    _emit_progress(
        progress_callback,
        stage="pairwise_start",
        message=(
            f"Preparing {len(pairs_to_process)} fresh pairwise comparisons; "
            f"{cached_pair_count} already cached."
        ),
        progress=0.0,
        current=0,
        total=len(pairs_to_process),
        candidate_pairs_total=candidate_pair_count,
        cached_pairs_skipped=cached_pair_count,
        fresh_pairs_total=len(pairs_to_process),
        pairwise_workers=max(1, min(PAIRWISE_WORKERS, len(pairs_to_process))),
    )
    max_workers = max(1, min(PAIRWISE_WORKERS, len(pairs_to_process)))
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(compare_papers, papers[left], papers[right]): (left, right)
            for left, right in pairs_to_process
        }
        for future in as_completed(future_map):
            left, right = future_map[future]
            pair_details = _pair_progress_details(papers, left, right)
            try:
                relationships = future.result()
                save_pair_relationships(
                    left,
                    right,
                    relationships,
                    manifest,
                    pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
                )
                pair_outcome = "succeeded"
                relationship_count = len(relationships)
                error_text = ""
                debug_path = ""
            except Exception as exc:
                failure = _record_pair_failure(
                    papers,
                    left,
                    right,
                    exc,
                    pair_phase="fresh",
                )
                failures.append(failure)
                pair_outcome = "failed"
                relationship_count = 0
                error_text = failure["error"]
                debug_path = failure.get("debug_path", "")
            completed += 1
            _emit_progress(
                progress_callback,
                stage="pairwise_progress",
                message="Completed a fresh paper comparison.",
                progress=completed / len(pairs_to_process),
                current=completed,
                total=len(pairs_to_process),
                candidate_pairs_total=candidate_pair_count,
                cached_pairs_skipped=cached_pair_count,
                fresh_pairs_total=len(pairs_to_process),
                pair_phase="fresh",
                pair_outcome=pair_outcome,
                relationship_count=relationship_count,
                error=error_text,
                debug_path=debug_path,
                **pair_details,
            )

    if failures and PAIRWISE_SERIAL_RETRY_ATTEMPTS > 0:
        retry_queue = failures
        for attempt in range(1, PAIRWISE_SERIAL_RETRY_ATTEMPTS + 1):
            if not retry_queue:
                break
            _emit_progress(
                progress_callback,
                stage="pairwise_retry_start",
                message=(
                    f"Retrying {len(retry_queue)} incomplete paper comparisons "
                    f"(pass {attempt} of {PAIRWISE_SERIAL_RETRY_ATTEMPTS})."
                ),
                progress=0.0,
                current=0,
                total=len(retry_queue),
                retry_attempt=attempt,
                retry_max_attempts=PAIRWISE_SERIAL_RETRY_ATTEMPTS,
                retry_pairs_total=len(retry_queue),
            )
            remaining_failures: list[dict] = []
            for index, failure in enumerate(retry_queue, start=1):
                left = failure["paper_a_id"]
                right = failure["paper_b_id"]
                pair_details = _pair_progress_details(papers, left, right)
                try:
                    relationships = compare_papers(papers[left], papers[right])
                    save_pair_relationships(
                        left,
                        right,
                        relationships,
                        manifest,
                        pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
                    )
                    pair_outcome = "succeeded"
                    relationship_count = len(relationships)
                    error_text = ""
                    debug_path = ""
                except Exception as exc:
                    failure = _record_pair_failure(
                        papers,
                        left,
                        right,
                        exc,
                        pair_phase="retry",
                        retry_attempt=attempt,
                    )
                    remaining_failures.append(failure)
                    pair_outcome = "failed"
                    relationship_count = 0
                    error_text = failure["error"]
                    debug_path = failure.get("debug_path", "")
                _emit_progress(
                    progress_callback,
                    stage="pairwise_retry_progress",
                    message="Completed a retry of a failed paper comparison.",
                    progress=index / len(retry_queue),
                    current=index,
                    total=len(retry_queue),
                    pair_phase="retry",
                    pair_outcome=pair_outcome,
                    relationship_count=relationship_count,
                    retry_attempt=attempt,
                    retry_max_attempts=PAIRWISE_SERIAL_RETRY_ATTEMPTS,
                    retry_pairs_total=len(retry_queue),
                    error=error_text,
                    debug_path=debug_path,
                    **pair_details,
                )
            retry_queue = remaining_failures
        failures = retry_queue

    successful_pairs_count = len(pairs_to_process) - len(failures)
    _emit_progress(
        progress_callback,
        stage="pairwise_complete",
        message=(
            "Finished comparing related papers."
            if not failures
            else f"Finished comparing related papers; {len(failures)} pair(s) still failed."
        ),
        progress=1.0,
        current=candidate_pair_count,
        total=candidate_pair_count,
        candidate_pairs_total=candidate_pair_count,
        cached_pairs_skipped=cached_pair_count,
        fresh_pairs_total=len(pairs_to_process),
        successful_pairs_count=successful_pairs_count,
        failed_pairs_count=len(failures),
    )
    return load_all_pair_relationships(
        manifest,
        pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
    ), failures


def compute_and_save_measures(
    papers: dict[str, dict],
    relationships: list[dict],
    paper_edges: dict,
) -> dict[str, dict]:
    """Compute graph influence measures and persist them to measures.json."""
    measures = compute_measures(papers, relationships, paper_edges)
    from .cache import write_json
    write_json(MEASURES_PATH, measures)
    return measures


def preprocess_corpus(
    raw_dir: Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    ensure_project_dirs()
    target_dir = raw_dir or RAW_DIR
    manifest = load_manifest()
    papers = load_all_paper_records(
        manifest,
        analysis_signature=PAPER_ANALYSIS_SIGNATURE,
    )
    pdf_paths = sorted(target_dir.glob("*.pdf"))

    processed = 0
    skipped = 0
    failed = 0
    pending_paths: list[tuple[Path, str]] = []

    _emit_progress(
        progress_callback,
        stage="scan_raw_dir",
        message=f"Scanning {target_dir} for PDFs.",
        progress=0.0,
        current=0,
        total=len(pdf_paths),
    )
    for pdf_path in pdf_paths:
        source_hash = compute_sha256(pdf_path)
        cache_entry = manifest.get("papers_by_hash", {}).get(source_hash)
        cache_path = (
            CACHE_DIR / cache_entry["paper_cache_path"]
            if cache_entry and cache_entry.get("paper_cache_path")
            else None
        )
        if (
            cache_entry
            and cache_entry.get("status") == "ready"
            and cache_entry.get("analysis_signature") == PAPER_ANALYSIS_SIGNATURE
            and cache_path
            and cache_path.exists()
        ):
            skipped += 1
            continue
        pending_paths.append((pdf_path, source_hash))

    if pending_paths:
        _emit_progress(
            progress_callback,
            stage="paper_batch_start",
            message=f"Analyzing {len(pending_paths)} new PDFs.",
            progress=0.1,
            current=0,
            total=len(pending_paths),
        )
        max_workers = max(1, min(EXTRACTION_WORKERS, len(pending_paths)))
        completed_papers = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(analyze_pdf, pdf_path, manifest, False): (pdf_path, source_hash)
                for pdf_path, source_hash in pending_paths
            }
            for future in as_completed(future_map):
                pdf_path, source_hash = future_map[future]
                try:
                    paper = future.result()
                    save_paper_record(
                        paper,
                        manifest,
                        analysis_signature=PAPER_ANALYSIS_SIGNATURE,
                    )
                    papers[paper["paper_id"]] = paper
                    processed += 1
                    completed_papers += 1
                    _emit_progress(
                        progress_callback,
                        stage="paper_batch_progress",
                        message=f"Processed {completed_papers} of {len(pending_paths)} new PDFs.",
                        progress=0.1 + (0.35 * (completed_papers / len(pending_paths))),
                        current=completed_papers,
                        total=len(pending_paths),
                        paper_id=paper["paper_id"],
                    )
                except Exception as exc:
                    record_failed_file(pdf_path, source_hash, exc, manifest)
                    failed += 1
                    completed_papers += 1
                    _emit_progress(
                        progress_callback,
                        stage="paper_batch_progress",
                        message=f"Processed {completed_papers} of {len(pending_paths)} new PDFs ({failed} failed).",
                        progress=0.1 + (0.35 * (completed_papers / len(pending_paths))),
                        current=completed_papers,
                        total=len(pending_paths),
                        source_filename=pdf_path.name,
                        error=str(exc),
                    )
    else:
        _emit_progress(
            progress_callback,
            stage="paper_batch_complete",
            message="No new PDFs needed analysis.",
            progress=0.45,
            current=0,
            total=0,
        )

    def _pairwise_progress(event: dict[str, Any]) -> None:
        pair_progress = event.get("progress", 0.0)
        forwarded = {
            key: value
            for key, value in event.items()
            if key not in {"stage", "message", "progress", "current", "total"}
        }
        _emit_progress(
            progress_callback,
            stage=event.get("stage", "pairwise"),
            message=event.get("message", "Running paper comparisons."),
            progress=0.45 + (0.45 * pair_progress),
            current=event.get("current"),
            total=event.get("total"),
            **forwarded,
        )

    relationships, pair_failures = ensure_pairwise_relationships(
        papers,
        manifest,
        progress_callback=_pairwise_progress,
    )
    _emit_progress(
        progress_callback,
        stage="aggregate_edges",
        message="Aggregating claim-level relationships into graph edges.",
        progress=0.94,
    )
    paper_edges = aggregate_paper_edges(relationships, papers)
    save_combined_dataset(papers, relationships, paper_edges, manifest)
    compute_and_save_measures(papers, relationships, paper_edges)
    pairwise_status = current_pairwise_status(
        papers,
        manifest,
        paper_edges,
        pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
    )
    _emit_progress(
        progress_callback,
        stage="complete",
        message="Finished preprocessing corpus and writing cache files.",
        progress=1.0,
        current=len(papers),
        total=len(papers),
    )

    return {
        "processed_papers": processed,
        "skipped_papers": skipped,
        "failed_papers": failed,
        "pair_failures": pair_failures,
        "paper_count": len(papers),
        "relationship_count": len(relationships),
        "edge_count": len(paper_edges),
        "potential_pair_count": pairwise_status["potential_pair_count"],
        "processed_pair_count": pairwise_status["processed_pair_count"],
        "unprocessed_pair_count": pairwise_status["unprocessed_pair_count"],
        "pairs_with_relationships_count": pairwise_status["pairs_with_relationships_count"],
    }


def search_claims(query: str, papers: dict[str, dict]) -> dict:
    claim_corpus: list[dict[str, Any]] = []
    for paper in papers.values():
        for claim in paper.get("claims", []):
            claim_corpus.append(
                {
                    "paper_id": paper["paper_id"],
                    "title": paper.get("title"),
                    "year": paper.get("year"),
                    "claim_id": claim.get("claim_id"),
                    "claim": claim.get("claim"),
                    "evidence_strength": claim.get("evidence_strength"),
                    "key_variables": claim.get("key_variables"),
                    "context": claim.get("context"),
                }
            )

    try:
        payload = _post_message(
            model=SEARCH_MODEL,
            system_prompt=SEARCH_SYSTEM_PROMPT,
            content=[
                {
                    "type": "text",
                    "text": (
                        f'User query: "{query}"\n\n'
                        f"Claims:\n{json.dumps(claim_corpus, ensure_ascii=False)}"
                    ),
                }
            ],
            schema=SEARCH_SCHEMA,
            max_tokens=2048,
            timeout_seconds=SEARCH_TIMEOUT_SECONDS,
            include_files_beta=False,
        )
        validate_payload("search", payload)
        matching_claim_ids = payload.get("matching_claim_ids", [])[:20]
        return {
            "matching_claim_ids": matching_claim_ids,
            "summary": payload.get("summary", "").strip(),
            "paper_ids": paper_ids_for_claim_ids(matching_claim_ids, papers),
            "used_fallback": False,
        }
    except Exception as exc:
        fallback_result = fallback_search(query, papers)
        fallback_result["fallback_error"] = str(exc)
        return fallback_result


def analyze_uploaded_pdf(
    file_name: str,
    file_bytes: bytes,
    manifest: dict,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    safe_name = Path(file_name).name or "uploaded-paper.pdf"
    _emit_progress(
        progress_callback,
        stage="upload_received",
        message="Paper received.",
        progress=0.02,
        source_filename=safe_name,
    )
    with tempfile.TemporaryDirectory(prefix="researchgraph-upload-") as temp_dir:
        final_path = Path(temp_dir) / safe_name
        final_path.write_bytes(file_bytes)
        return analyze_pdf(
            final_path,
            manifest=manifest,
            persist=False,
            progress_callback=progress_callback,
        )


def merge_uploaded_paper(
    paper: dict,
    papers: dict[str, dict],
    manifest: dict,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[dict], dict[tuple[str, str], dict], list[dict]]:
    save_paper_record(paper, manifest, analysis_signature=PAPER_ANALYSIS_SIGNATURE)
    papers[paper["paper_id"]] = paper

    def _pairwise_progress(event: dict[str, Any]) -> None:
        pair_progress = event.get("progress", 0.0)
        forwarded = {
            key: value
            for key, value in event.items()
            if key not in {"stage", "message", "progress", "current", "total"}
        }
        _emit_progress(
            progress_callback,
            stage=event.get("stage", "pairwise"),
            message=event.get("message", "Comparing the paper with related work."),
            progress=0.45 + (0.45 * pair_progress),
            current=event.get("current"),
            total=event.get("total"),
            **forwarded,
        )

    _emit_progress(
        progress_callback,
        stage="save_paper",
        message="Adding to the map.",
        progress=0.45,
        paper_id=paper["paper_id"],
    )
    relationships, pair_failures = ensure_pairwise_relationships(
        papers,
        manifest,
        progress_callback=_pairwise_progress,
    )
    _emit_progress(
        progress_callback,
        stage="merge_graph",
        message="Updating the research map.",
        progress=0.94,
        paper_id=paper["paper_id"],
    )
    paper_edges = aggregate_paper_edges(relationships, papers)
    save_combined_dataset(papers, relationships, paper_edges, manifest)
    compute_and_save_measures(papers, relationships, paper_edges)
    _emit_progress(
        progress_callback,
        stage="complete",
        message="Paper added to Hypatia.",
        progress=1.0,
        paper_id=paper["paper_id"],
    )
    return relationships, paper_edges, pair_failures


def ingest_uploaded_pdf(
    file_name: str,
    file_bytes: bytes,
    papers: dict[str, dict],
    manifest: dict,
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict, list[dict], dict[tuple[str, str], dict], list[dict]]:
    paper = analyze_uploaded_pdf(
        file_name,
        file_bytes,
        manifest,
        progress_callback=progress_callback,
    )
    relationships, paper_edges, pair_failures = merge_uploaded_paper(
        paper,
        papers,
        manifest,
        progress_callback=progress_callback,
    )
    return paper, relationships, paper_edges, pair_failures
