from __future__ import annotations

from copy import deepcopy
from html import escape

import streamlit as st

from .cache import pair_key


def initialize_session_state() -> None:
    defaults = {
        "papers": {},
        "relationships": [],
        "paper_edges": {},
        "failed_pairs": {},
        "manifest": {},
        "relationship_index": {},
        "selected_graph_item": {"type": "background", "id": None},
        "search_state": {
            "query": "",
            "matching_claim_ids": [],
            "paper_ids": [],
            "summary": "",
            "used_fallback": False,
            "fallback_error": "",
        },
        "hide_low_signal_edges": False,
        "reset_token": 0,
        "uploader_reset_token": 0,
        "data_loaded": False,
        "upload_error": "",
        "upload_notice": "",
        "pending_upload_paper": None,
        "pending_duplicate_matches": [],
        "delete_target_paper_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(value)


def selection_is_meaningful(selection: dict | None) -> bool:
    return bool(selection and selection.get("type") in {"node", "edge"} and selection.get("id"))


def _truncate_text(value: str, limit: int = 96) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(" ", maxsplit=1)[0].strip()
    return (shortened or text[:limit]).rstrip(" ,;:.") + "..."


def _ingestion_mode_label(mode: str | None) -> str:
    mapping = {
        "claude_pdf": "Native PDF",
        "local_text": "Text read",
        "local_fallback": "Text fallback",
    }
    return mapping.get(mode or "", (mode or "unknown").replace("_", " ").title())


def _pretty_label(value: str | None) -> str:
    text = (value or "unknown").strip()
    token_map = {
        "ai": "AI",
        "llm": "LLM",
        "pdf": "PDF",
        "rct": "RCT",
        "rlhf": "RLHF",
    }
    explicit_map = {
        "policy_recommendation": "Policy Recommendation",
    }
    if text in explicit_map:
        return explicit_map[text]
    parts = text.replace("_", " ").split()
    if not parts:
        return "Unknown"
    formatted_parts = []
    for part in parts:
        formatted_parts.append(token_map.get(part.lower(), part.capitalize()))
    return " ".join(formatted_parts)


def _pretty_check_label(value: str | None) -> str:
    mapping = {
        "sample_size": "Sample Size",
        "multiple_comparisons": "Multiple Comparisons",
        "p_value_clustering": "P-value Clustering",
        "robustness_checks": "Robustness Checks",
        "effect_size_reporting": "Effect Size Reporting",
        "data_availability": "Data Availability",
        "conflict_of_interest": "Conflict of Interest",
        "selection_bias": "Selection Bias",
        "outcome_switching": "Outcome Switching",
        "external_validity": "External Validity",
    }
    return mapping.get((value or "").strip(), _pretty_label(value))


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural or singular + 's'}"


def _pending_relationship_message(count: int) -> str:
    if count == 1:
        return "1 paper relationship is pending because the comparison did not complete."
    return f"{count} paper relationships are pending because their comparisons did not complete."


def _evidence_strength_tone(value: str | None) -> str:
    mapping = {
        "strong": "healthy",
        "moderate": "caution",
        "weak": "concern",
    }
    return mapping.get((value or "").lower(), "")


def _tag_help_text(kind: str, value: str | None) -> str:
    normalized = (value or "").strip()
    help_texts = {
        "claim_type": {
            "causal": "A claim that one factor causes another outcome.",
            "correlational": "A claim that variables move together without proving cause and effect.",
            "descriptive": "A claim that summarizes what the paper observed in its data.",
            "theoretical": "A claim about mechanisms, concepts, or conceptual framing.",
            "predictive": "A claim about forecasting or anticipating future outcomes.",
            "policy_recommendation": "A claim that recommends an intervention, practice, or policy.",
        },
        "evidence_type": {
            "RCT": "Evidence from a randomized controlled trial.",
            "natural_experiment": "Evidence from a naturally occurring comparison that approximates random assignment.",
            "quasi_experimental": "Evidence from a designed comparison that is not fully randomized.",
            "observational": "Evidence from observed data without experimental control.",
            "meta_analysis": "Evidence pooled statistically across multiple prior studies.",
            "systematic_review": "Evidence synthesized across prior studies using a structured review process.",
            "computational_simulation": "Evidence generated through model-based simulation rather than direct observation.",
            "survey": "Evidence gathered from self-reported responses.",
            "case_study": "Evidence drawn from one or a small number of detailed cases.",
            "theoretical_model": "Support based on a formal or conceptual model rather than direct empirical testing.",
            "qualitative": "Evidence from interviews, ethnography, coding, or other non-numeric analysis.",
            "other": "A supporting evidence type that does not fit the main categories.",
        },
        "evidence_strength": {
            "strong": "The supporting evidence for this claim appears comparatively robust within the paper.",
            "moderate": "The evidence is suggestive but comes with important caveats or limitations.",
            "weak": "The claim appears only lightly supported, speculative, or fragile in this paper.",
        },
        "health_score": {
            "healthy": "The paper passed most methodology checks with few major concerns.",
            "caution": "The paper raised some methodology concerns that deserve careful reading.",
            "concern": "The paper raised several methodology concerns or clear red flags.",
        },
        "claim_count": {
            "default": "The number of substantive claims extracted from this paper.",
        },
        "method_status": {
            "pass": "This methodology check passed.",
            "warn": "This methodology check raised a caution flag.",
            "fail": "This methodology check raised a significant concern.",
        },
        "relationship": {
            "supports": "These papers independently point in the same direction.",
            "contradicts": "These papers reach meaningfully different conclusions on a similar question.",
            "extends": "One paper builds on or generalizes the other.",
            "qualifies": "One paper narrows, conditions, or limits the other.",
            "pending": "Hypatia has not finished comparing these papers yet.",
        },
        "relationship_strength": {
            "direct": "The connection is explicit and close in scope.",
            "partial": "The connection is meaningful but only overlaps part of the claim.",
            "implicit": "The connection is inferred from the papers' claims rather than stated directly.",
        },
    }
    kind_map = help_texts.get(kind, {})
    return kind_map.get(normalized, kind_map.get(normalized.lower(), kind_map.get("default", "")))


RELATIONSHIP_COPY = {
    "supports": {
        "title": "Supports",
        "singular": "support",
        "plural": "supports",
    },
    "contradicts": {
        "title": "Contradicts",
        "singular": "contradiction",
        "plural": "contradictions",
    },
    "extends": {
        "title": "Extends",
        "singular": "extension",
        "plural": "extensions",
    },
    "qualifies": {
        "title": "Qualifies",
        "singular": "qualification",
        "plural": "qualifications",
    },
    "pending": {
        "title": "Pending",
        "singular": "pending relationship",
        "plural": "pending relationships",
    },
}


def _relationship_tone(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in RELATIONSHIP_COPY:
        return normalized
    return "pending" if normalized == "pending" else ""


def _relationship_title(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return RELATIONSHIP_COPY.get(normalized, {}).get("title", _pretty_label(value))


def _relationship_count_text(value: str | None, count: int) -> str:
    normalized = (value or "").strip().lower()
    rel = RELATIONSHIP_COPY.get(normalized)
    if not rel:
        return _count_label(count, "relationship")
    noun = rel["singular"] if count == 1 else rel["plural"]
    return f"{count} {noun}"


def _relationship_summary_text(value: str | None, count: int) -> str:
    normalized = (value or "").strip().lower()
    rel = RELATIONSHIP_COPY.get(normalized)
    if not rel:
        return _relationship_count_text(value, count).title()
    noun = rel["singular"].capitalize() if count == 1 else rel["plural"].capitalize()
    return f"{count} {noun}"


def _relationship_pill(value: str | None, label: str | None = None, tooltip: str | None = None) -> str:
    normalized = (value or "").strip().lower()
    return _pill(
        label or _relationship_title(normalized),
        tone=_relationship_tone(normalized),
        tooltip=tooltip or _tag_help_text("relationship", normalized),
    )


def _paper_tile_meta(paper: dict) -> str:
    metadata_bits = []
    if paper.get("authors"):
        metadata_bits.append(", ".join(paper["authors"]))
    if paper.get("year"):
        metadata_bits.append(str(paper["year"]))
    return " | ".join(metadata_bits)


def _friendly_pair_error(error: str, error_kind: str | None = None) -> str:
    text = (error or "").strip()
    lowered = text.lower()
    normalized_kind = (error_kind or "").strip().lower()
    if normalized_kind == "truncated":
        return "Hypatia ran out of room while comparing these papers. Retrying later should usually recover it."
    if normalized_kind == "structured_output":
        return "Hypatia received an incomplete comparison result while linking these papers."
    if normalized_kind == "rate_limit":
        return "Hypatia was temporarily rate-limited while comparing these papers."
    if normalized_kind == "overloaded":
        return "Anthropic was temporarily overloaded while comparing these papers."
    if normalized_kind == "timeout":
        return "The paper comparison took too long to finish."
    if normalized_kind == "network":
        return "A network issue interrupted the paper comparison."
    if "ran out of room" in lowered or "max_tokens" in lowered:
        return "Hypatia ran out of room while comparing these papers. Retrying later should usually recover it."
    if "invalid structured output" in lowered or "unterminated string" in lowered:
        return "Hypatia received an incomplete comparison result while linking these papers."
    if "all relationship items were invalid" in lowered:
        return "Hypatia received a malformed comparison result while linking these papers."
    if "rate limit" in lowered or "429" in lowered:
        return "Hypatia was temporarily rate-limited while comparing these papers."
    if not text:
        return "Hypatia has not finished comparing these papers yet."
    return "Hypatia could not finish comparing these papers yet."


def _claim_metadata_markup(claim: dict) -> str:
    claim_type = claim.get("claim_type", "unknown")
    evidence_type = claim.get("evidence_type", "unknown")
    evidence_strength = claim.get("evidence_strength", "unknown")
    return " ".join(
        [
            _pill(
                _pretty_label(claim_type),
                tooltip=_tag_help_text("claim_type", claim_type),
            ),
            _pill(
                _pretty_label(evidence_type),
                tooltip=_tag_help_text("evidence_type", evidence_type),
            ),
            _pill(
                _pretty_label(evidence_strength),
                tone=_evidence_strength_tone(evidence_strength),
                tooltip=_tag_help_text("evidence_strength", evidence_strength),
            ),
        ]
    )


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --rg-bg: #f6f0e5;
            --rg-bg-deep: #efe4d3;
            --rg-surface: rgba(255, 251, 245, 0.88);
            --rg-surface-strong: rgba(255, 253, 249, 0.96);
            --rg-border: rgba(53, 38, 24, 0.12);
            --rg-ink: #201812;
            --rg-muted: #6f6152;
            --rg-accent: #b96d38;
            --rg-accent-soft: #e8d5c2;
            --rg-green: #2f7c6e;
            --rg-shadow: 0 20px 60px rgba(43, 30, 18, 0.08);
            --rg-space-sm: 0.7rem;
            --rg-space-md: 1.05rem;
            --rg-space-lg: 1.45rem;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 252, 245, 0.96) 0%, rgba(255, 252, 245, 0.92) 22%, rgba(246, 240, 229, 0.94) 58%, rgba(239, 228, 211, 0.98) 100%);
            color: var(--rg-ink);
        }

        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2.4rem;
            max-width: 1480px;
        }

        h1, h2, h3, h4, h5, h6,
        .rg-hero-title,
        .rg-section-title,
        .rg-panel-title {
            font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif !important;
            color: var(--rg-ink);
            letter-spacing: -0.02em;
        }

        html, body, [class*="css"], [data-testid="stMarkdownContainer"], label, input, textarea, button {
            font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
        }

        .rg-hero {
            padding: 1.4rem 1.6rem 1.55rem;
            border: 1px solid var(--rg-border);
            border-radius: 28px;
            background:
                linear-gradient(135deg, rgba(255, 252, 247, 0.94), rgba(250, 244, 236, 0.9)),
                radial-gradient(circle at top right, rgba(185, 109, 56, 0.12), transparent 38%);
            box-shadow: var(--rg-shadow);
            margin-bottom: 1rem;
        }

        .rg-hero-kicker {
            display: inline-block;
            margin-top: 1.62rem;
            margin-bottom: 0;
            padding: 0.35rem 0.72rem;
            border-radius: 999px;
            border: 1px solid rgba(185, 109, 56, 0.2);
            background: rgba(255, 250, 244, 0.82);
            color: var(--rg-accent);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .rg-hero-title {
            margin: 0 0 0.35rem;
            font-size: clamp(2.3rem, 4vw, 4.1rem);
            line-height: 0.98;
        }

        .rg-hero-body {
            max-width: 56rem;
            color: var(--rg-muted);
            font-size: 1.02rem;
            line-height: 1.55;
            margin: 0;
        }

        .rg-hero-line {
            display: block;
        }

        .rg-hero-line + .rg-hero-line {
            margin-top: 0.18rem;
        }

        .rg-stat-card {
            border: 1px solid var(--rg-border);
            border-radius: 24px;
            padding: 1rem 1.1rem 1.05rem;
            background: var(--rg-surface);
            box-shadow: 0 10px 30px rgba(43, 30, 18, 0.05);
        }

        .rg-stat-label {
            color: var(--rg-muted);
            font-size: 0.8rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .rg-stat-value {
            font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
            font-size: 2.15rem;
            line-height: 1;
            color: var(--rg-ink);
        }

        .rg-stat-note {
            color: var(--rg-muted);
            font-size: 0.88rem;
            margin-top: 0.4rem;
        }

        div[data-testid="stForm"],
        div[data-testid="stExpander"],
        div[data-testid="stFileUploader"],
        div[data-testid="stAlert"] {
            border-radius: 24px !important;
        }

        div[data-testid="stForm"] {
            padding: 1rem 1rem 0.45rem;
            border: 1px solid var(--rg-border);
            background: rgba(255, 251, 245, 0.8);
            box-shadow: 0 10px 30px rgba(43, 30, 18, 0.04);
            margin: 0;
        }

        div[data-testid="stTextInputRootElement"] > div {
            border-radius: 18px !important;
            border: 1px solid var(--rg-border) !important;
            background: rgba(255, 253, 250, 0.95) !important;
        }

        div[data-testid="stTextInputRootElement"] input {
            color: var(--rg-ink) !important;
        }

        div[data-testid="stCheckbox"] label,
        div[data-testid="stFileUploader"] label {
            color: var(--rg-muted);
        }

        .stButton > button,
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 999px !important;
            border: 1px solid rgba(138, 88, 48, 0.18) !important;
            background: linear-gradient(180deg, #fffaf4 0%, #f2e2d2 100%) !important;
            color: #38261a !important;
            font-weight: 600 !important;
            box-shadow: 0 8px 24px rgba(185, 109, 56, 0.12);
        }

        .stButton > button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {
            border-color: rgba(138, 88, 48, 0.32) !important;
            background: linear-gradient(180deg, #fffdf8 0%, #eed7c2 100%) !important;
        }

        div[data-testid="stTabs"] {
            margin-top: 0.75rem;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 0.55rem;
            padding: 0.28rem;
            border-radius: 999px;
            border: 1px solid var(--rg-border);
            background: rgba(255, 251, 246, 0.88);
            margin-bottom: 0.2rem;
        }

        div[data-testid="stTabs"] [data-baseweb="tab"] {
            height: 2.3rem;
            padding: 0 1rem;
            border-radius: 999px;
            color: var(--rg-muted);
            font-weight: 600;
        }

        div[data-testid="stTabs"] [aria-selected="true"] {
            background: linear-gradient(180deg, #f4dfcb 0%, #ead1bb 100%);
            color: var(--rg-ink) !important;
        }

        .rg-panel-card,
        .rg-search-card,
        .rg-empty-card,
        .rg-detail-card {
            border: 1px solid var(--rg-border);
            border-radius: 24px;
            background: var(--rg-surface-strong);
            box-shadow: 0 12px 34px rgba(43, 30, 18, 0.05);
            padding: 1.15rem 1.25rem 1.2rem;
        }

        .rg-panel-card + .rg-panel-card,
        .rg-search-card + .rg-panel-card {
            margin-top: 0.85rem;
        }

        .rg-detail-card {
            margin-bottom: 1.15rem;
        }

        .rg-panel-title {
            margin: 0 0 0.18rem;
            font-size: 0.98rem;
            color: var(--rg-muted);
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .rg-detail-heading {
            margin: 0;
            font-size: 1.75rem;
            line-height: 1.05;
        }

        .rg-detail-meta {
            margin-top: 0.5rem;
            color: var(--rg-muted);
            font-size: 0.95rem;
        }

        .rg-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.9rem;
            overflow: visible;
        }

        .rg-pill {
            display: inline-flex;
            align-items: center;
            position: relative;
            border-radius: 999px;
            padding: 0.38rem 0.72rem;
            font-size: 0.82rem;
            font-weight: 600;
            background: rgba(233, 220, 205, 0.58);
            color: #4c3725;
            border: 1px solid rgba(127, 92, 61, 0.1);
        }

        .rg-pill[data-tooltip] {
            cursor: help;
        }

        .rg-pill[data-tooltip]::after {
            content: attr(data-tooltip);
            position: absolute;
            left: 50%;
            top: calc(100% + 10px);
            transform: translateX(-50%);
            min-width: 180px;
            max-width: 260px;
            padding: 0.65rem 0.78rem;
            border-radius: 14px;
            border: 1px solid rgba(66, 45, 27, 0.12);
            background: rgba(35, 27, 20, 0.96);
            color: #fffaf4;
            font-size: 0.76rem;
            font-weight: 500;
            line-height: 1.42;
            text-align: left;
            white-space: normal;
            box-shadow: 0 16px 36px rgba(23, 16, 11, 0.2);
            opacity: 0;
            pointer-events: none;
            visibility: hidden;
            z-index: 50;
            transition: opacity 120ms ease, transform 120ms ease, visibility 120ms ease;
        }

        .rg-pill[data-tooltip]::before {
            content: "";
            position: absolute;
            left: 50%;
            top: calc(100% + 4px);
            transform: translateX(-50%);
            border-width: 6px;
            border-style: solid;
            border-color: transparent transparent rgba(35, 27, 20, 0.96) transparent;
            opacity: 0;
            visibility: hidden;
            z-index: 49;
            transition: opacity 120ms ease, visibility 120ms ease;
        }

        .rg-pill[data-tooltip]:hover::after,
        .rg-pill[data-tooltip]:hover::before,
        .rg-pill[data-tooltip]:focus-visible::after,
        .rg-pill[data-tooltip]:focus-visible::before {
            opacity: 1;
            visibility: visible;
        }

        .rg-pill[data-tooltip]:hover::after,
        .rg-pill[data-tooltip]:focus-visible::after {
            transform: translateX(-50%) translateY(2px);
        }

        .rg-pill--healthy {
            background: rgba(80, 147, 131, 0.14);
            color: #29695d;
        }

        .rg-pill--caution {
            background: rgba(212, 156, 78, 0.18);
            color: #8b5a1d;
        }

        .rg-pill--concern {
            background: rgba(208, 103, 85, 0.16);
            color: #9b4334;
        }

        .rg-pill--supports {
            background: rgba(80, 147, 131, 0.16);
            color: #29695d;
            border-color: rgba(47, 124, 110, 0.18);
        }

        .rg-pill--contradicts {
            background: rgba(186, 109, 89, 0.16);
            color: #934d3e;
            border-color: rgba(176, 106, 90, 0.18);
        }

        .rg-pill--extends {
            background: rgba(123, 125, 112, 0.16);
            color: #666250;
            border-color: rgba(119, 118, 102, 0.18);
        }

        .rg-pill--qualifies {
            background: rgba(212, 156, 78, 0.18);
            color: #8b5a1d;
            border-color: rgba(183, 131, 69, 0.18);
        }

        .rg-pill--pending {
            background: rgba(181, 154, 118, 0.16);
            color: #7a654b;
            border-color: rgba(166, 141, 109, 0.16);
        }

        .rg-relationship-header {
            margin-bottom: 1.2rem;
            padding-bottom: 1.3rem;
        }

        .rg-relationship-hero {
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
            margin-top: 0.85rem;
        }

        .rg-relationship-paper-card {
            border: 1px solid rgba(66, 45, 27, 0.08);
            border-radius: 22px;
            background: rgba(255, 251, 246, 0.74);
            padding: 1rem 1.08rem 1.05rem;
        }

        .rg-relationship-paper-label {
            color: var(--rg-muted);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .rg-relationship-paper-title {
            margin-top: 0.35rem;
            font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
            font-size: 1.38rem;
            line-height: 1.12;
            color: var(--rg-ink);
        }

        .rg-relationship-center {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.34rem;
            padding: 0.05rem 0 0.1rem;
        }

        .rg-relationship-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.48rem 0.92rem;
            border-radius: 999px;
            font-size: 0.86rem;
            font-weight: 700;
            border: 1px solid rgba(127, 92, 61, 0.1);
            background: rgba(233, 220, 205, 0.58);
            color: #4c3725;
        }

        .rg-relationship-badge--supports {
            background: rgba(80, 147, 131, 0.14);
            color: #29695d;
            border-color: rgba(47, 124, 110, 0.18);
        }

        .rg-relationship-badge--contradicts {
            background: rgba(186, 109, 89, 0.15);
            color: #934d3e;
            border-color: rgba(176, 106, 90, 0.18);
        }

        .rg-relationship-badge--extends {
            background: rgba(123, 125, 112, 0.15);
            color: #666250;
            border-color: rgba(119, 118, 102, 0.18);
        }

        .rg-relationship-badge--qualifies {
            background: rgba(212, 156, 78, 0.16);
            color: #8b5a1d;
            border-color: rgba(183, 131, 69, 0.18);
        }

        .rg-relationship-badge--pending {
            background: rgba(181, 154, 118, 0.16);
            color: #7a654b;
            border-color: rgba(166, 141, 109, 0.16);
        }

        .rg-relationship-center-note {
            color: var(--rg-muted);
            font-size: 0.79rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .rg-pill-row--relationship-summary {
            margin-top: 1.18rem;
        }

        .rg-claim-shell,
        .rg-check-shell,
        .rg-edge-shell {
            border: 1px solid rgba(66, 45, 27, 0.08);
            border-radius: 20px;
            background: rgba(255, 251, 246, 0.72);
            padding: 1.15rem 1.25rem 1.1rem;
            margin-bottom: 1rem;
        }

        .rg-claim-shell strong,
        .rg-edge-shell strong,
        .rg-check-shell strong {
            display: block;
            line-height: 1.42;
        }

        .rg-claim-preview {
            font-size: 1.02rem;
            font-weight: 650;
            line-height: 1.45;
            color: var(--rg-ink);
        }

        .rg-detail-meta--compact {
            margin-top: 0.55rem;
        }

        .rg-detail-meta--paper-tile {
            margin-top: 0.55rem;
            line-height: 1.5;
            font-size: 0.88rem;
        }

        .rg-claim-metadata {
            margin: 0.9rem 0 1rem;
            overflow: visible;
        }

        .rg-subtitle {
            margin: 0.2rem 0 0.9rem;
            color: var(--rg-muted);
        }

        .rg-flow-gap {
            width: 100%;
        }

        .rg-flow-gap--sm {
            height: var(--rg-space-sm);
        }

        .rg-flow-gap--md {
            height: var(--rg-space-md);
        }

        .rg-flow-gap--lg {
            height: var(--rg-space-lg);
        }

        div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
            padding-top: 1.05rem;
        }

        div[data-testid="stExpander"] details {
            border: 1px solid rgba(66, 45, 27, 0.08);
            border-radius: 20px;
            background: rgba(255, 251, 246, 0.7);
            overflow: visible;
            margin-bottom: 1rem;
        }

        div[data-testid="stExpander"] summary {
            font-weight: 600;
            color: var(--rg-ink);
            line-height: 1.45;
            padding: 1rem 1.15rem;
        }

        div[data-testid="stExpander"] details > div {
            padding: 0.42rem 1.15rem 1.48rem;
        }

        .rg-expander-intro {
            margin-top: 0.6rem;
            margin-bottom: 1rem;
        }

        .rg-expander-intro .rg-panel-title {
            margin-bottom: 0.35rem;
        }

        .rg-help-text {
            color: var(--rg-muted);
            font-size: 0.92rem;
            line-height: 1.62;
        }

        .rg-processing-card {
            margin-top: 1.05rem;
            padding: 1rem 1.05rem 0.95rem;
            border: 1px solid rgba(66, 45, 27, 0.08);
            border-radius: 20px;
            background: rgba(255, 251, 246, 0.72);
            box-shadow: 0 12px 32px rgba(43, 30, 18, 0.04);
        }

        .rg-processing-row {
            display: flex;
            align-items: center;
            gap: 0.72rem;
            margin-bottom: 0.85rem;
        }

        .rg-processing-spinner {
            width: 0.95rem;
            height: 0.95rem;
            border-radius: 999px;
            border: 2px solid rgba(185, 109, 56, 0.16);
            border-top-color: rgba(185, 109, 56, 0.9);
            animation: rg-spin 900ms linear infinite;
            flex: 0 0 auto;
        }

        .rg-processing-current {
            color: var(--rg-ink);
            font-size: 1rem;
            font-weight: 600;
            line-height: 1.45;
        }

        .rg-progress-track {
            width: 100%;
            height: 0.58rem;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(199, 189, 177, 0.28);
        }

        .rg-progress-fill {
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #4e9fdc 0%, #2f7fcb 100%);
            transition: width 160ms ease;
        }

        .rg-activity-log {
            margin-top: 1rem;
        }

        .rg-activity-list {
            list-style: none;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        .rg-activity-item {
            display: flex;
            align-items: flex-start;
            gap: 0.58rem;
            padding: 0.05rem 0;
        }

        .rg-activity-dot {
            width: 0.5rem;
            height: 0.5rem;
            margin-top: 0.48rem;
            border-radius: 999px;
            background: rgba(127, 113, 96, 0.24);
            box-shadow: inset 0 0 0 1px rgba(66, 45, 27, 0.06);
            flex: 0 0 auto;
        }

        .rg-activity-item span:last-child {
            color: var(--rg-muted);
            line-height: 1.45;
            font-size: 0.93rem;
        }

        .rg-activity-item--healthy .rg-activity-dot {
            background: rgba(80, 147, 131, 0.62);
        }

        .rg-activity-item--healthy span:last-child {
            color: #63766f;
        }

        .rg-activity-item--caution .rg-activity-dot {
            background: rgba(212, 156, 78, 0.82);
        }

        .rg-activity-item--caution span:last-child {
            color: #8b5a1d;
        }

        .rg-activity-item--concern .rg-activity-dot {
            background: rgba(208, 103, 85, 0.82);
        }

        .rg-activity-item--concern span:last-child {
            color: #9b4334;
        }

        .rg-relationship-stats {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
            margin-top: 1rem;
        }

        .rg-edge-shell--supports {
            background: rgba(246, 251, 249, 0.9);
            border-color: rgba(47, 124, 110, 0.12);
        }

        .rg-edge-shell--contradicts {
            background: rgba(252, 247, 245, 0.92);
            border-color: rgba(176, 106, 90, 0.12);
        }

        .rg-edge-shell--extends {
            background: rgba(249, 248, 244, 0.92);
            border-color: rgba(119, 118, 102, 0.12);
        }

        .rg-edge-shell--qualifies {
            background: rgba(252, 249, 244, 0.92);
            border-color: rgba(183, 131, 69, 0.12);
        }

        .rg-edge-shell--pending {
            background: rgba(249, 246, 241, 0.92);
            border-color: rgba(166, 141, 109, 0.12);
        }

        .rg-edge-stat-label {
            color: var(--rg-muted);
            font-size: 0.79rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .rg-edge-stat-value {
            margin-top: 0.4rem;
            font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
            font-size: 1.7rem;
            line-height: 1;
            color: var(--rg-ink);
        }

        .rg-relationship-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 1rem 0 1.1rem;
            overflow: visible;
        }

        .rg-relationship-explainer {
            color: var(--rg-ink);
            font-size: 1rem;
            line-height: 1.62;
            margin-bottom: 0.38rem;
        }

        @keyframes rg-spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="rg-hero">
          <div class="rg-hero-kicker">Anthropic Hackathon | Scientific Discovery</div>
          <h1 class="rg-hero-title">Hypatia</h1>
          <p class="rg-hero-body">
            <span class="rg-hero-line">Upload a body of research and see the full landscape instantly.</span>
            <span class="rg-hero-line">Hypatia extracts every claim, grades the evidence, and reveals where papers agree, conflict, and why.</span>
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(paper_count: int, relationship_count: int, edge_count: int) -> None:
    cards = [
        ("Corpus", str(paper_count), "papers loaded"),
        ("Claim Relationships", str(relationship_count), "cross-paper claim relationships"),
        ("Paper Relationships", str(edge_count), "relationships shown in the map"),
    ]
    columns = st.columns(3)
    for column, (label, value, note) in zip(columns, cards):
        with column:
            st.markdown(
                f"""
                <div class="rg-stat-card">
                  <div class="rg-stat-label">{escape(label)}</div>
                  <div class="rg-stat-value">{escape(value)}</div>
                  <div class="rg-stat-note">{escape(note)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_flow_gap(size: str = "md") -> None:
    if size not in {"sm", "md", "lg"}:
        size = "md"
    st.markdown(f'<div class="rg-flow-gap rg-flow-gap--{size}"></div>', unsafe_allow_html=True)


def clear_upload_widget() -> None:
    st.session_state.uploader_reset_token += 1


def _progress_tone(event: dict) -> str:
    if event.get("error"):
        return "concern"
    if event.get("stage") == "fallback_text":
        return "caution"
    return "healthy"


def build_processing_card_markup(message: str, progress: float) -> str:
    clean_message = (message or "Working...").strip().rstrip(".")
    percent = max(0, min(int(round(progress * 100)), 100))
    return (
        '<div class="rg-processing-card">'
        '<div class="rg-processing-row">'
        '<span class="rg-processing-spinner"></span>'
        f'<div class="rg-processing-current">{escape(clean_message)}</div>'
        "</div>"
        '<div class="rg-progress-track">'
        f'<div class="rg-progress-fill" style="width: {percent}%;"></div>'
        "</div></div>"
    )


def build_progress_timeline_markup(events: list[dict]) -> str:
    if not events:
        return ""
    completed_events = events[:-1] if len(events) > 1 else []
    if not completed_events:
        return ""
    items: list[str] = []
    for event in completed_events[-3:]:
        message = (event.get("message") or "").strip()
        if not message:
            continue
        tone = _progress_tone(event)
        items.append(
            (
                f'<li class="rg-activity-item rg-activity-item--{tone}">'
                '<span class="rg-activity-dot"></span>'
                f"<span>{escape(message)}</span>"
                "</li>"
            )
        )
    if not items:
        return ""
    return (
        '<div class="rg-activity-log"><ul class="rg-activity-list">'
        + "".join(items)
        + "</ul></div>"
    )


def _pill(label: str, tone: str = "", tooltip: str = "") -> str:
    suffix = f" rg-pill--{tone}" if tone else ""
    tooltip_attr = f' data-tooltip="{escape(tooltip)}" tabindex="0"' if tooltip else ""
    return f'<span class="rg-pill{suffix}"{tooltip_attr}>{escape(label)}</span>'


def _render_panel_header(
    *,
    eyebrow: str,
    title: str,
    meta: str = "",
    pills: list[str] | None = None,
) -> None:
    st.markdown(
        f"""
        <div class="rg-panel-card">
          <div class="rg-panel-title">{escape(eyebrow)}</div>
          <h3 class="rg-detail-heading">{escape(title)}</h3>
          {f'<div class="rg-detail-meta">{escape(meta)}</div>' if meta else ''}
          <div class="rg-pill-row">{''.join(pills or [])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_health_summary(checks: list[dict]) -> None:
    pass_count = sum(1 for item in checks if item.get("status") == "pass")
    warn_count = sum(1 for item in checks if item.get("status") == "warn")
    fail_count = sum(1 for item in checks if item.get("status") == "fail")
    cols = st.columns(3)
    stats = [("Pass", pass_count), ("Warn", warn_count), ("Fail", fail_count)]
    for col, (label, value) in zip(cols, stats):
        with col:
            st.markdown(
                f"""
                <div class="rg-stat-card">
                  <div class="rg-stat-label">{escape(label)}</div>
                  <div class="rg-stat-value" style="font-size:1.8rem;">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_search_summary(search_state: dict) -> None:
    query = search_state.get("query", "").strip()
    if not query:
        return

    fallback_pill = _pill("Local fallback", "caution") if search_state.get("used_fallback") else _pill("Sonnet synthesis")
    fallback_note = ""
    if search_state.get("used_fallback") and search_state.get("fallback_error"):
        fallback_note = (
            f'<p class="rg-help-text" style="margin-top:0.7rem;">'
            f"Claude search was unavailable, so Hypatia used local keyword matching instead."
            f"</p>"
        )
    st.markdown(
        f"""
        <div class="rg-search-card">
          <div class="rg-panel-title">Search Result</div>
          <h3 class="rg-detail-heading" style="font-size:1.35rem;">{escape(query)}</h3>
          <div class="rg-pill-row">{fallback_pill}</div>
          <p class="rg-help-text" style="margin-top:0.85rem;">{escape(search_state.get("summary") or "No summary available.")}</p>
          {fallback_note}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_paper_details(paper: dict) -> None:
    metadata_bits = []
    if paper.get("authors"):
        metadata_bits.append(", ".join(paper["authors"]))
    if paper.get("year"):
        metadata_bits.append(str(paper["year"]))

    health = paper.get("health_score", {})
    health_score = health.get("overall_score", "unknown")
    _render_panel_header(
        eyebrow="Paper",
        title=paper.get("title", "Untitled paper"),
        meta=" | ".join(metadata_bits),
        pills=[
            _pill(
                _pretty_label(health_score),
                health_score,
                tooltip=_tag_help_text("health_score", health_score),
            ),
            _pill(
                f"{len(paper.get('claims', []))} claims",
                tooltip=_tag_help_text("claim_count", "default"),
            ),
        ],
    )

    overview_tab, methodology_tab, claims_tab = st.tabs(["Overview", "Methodology", "Claims"])

    with overview_tab:
        claim_count = len(paper.get("claims", []))
        health_badge = _pretty_label(health_score)
        st.markdown(
            f"""
            <div class="rg-detail-card">
              <div class="rg-panel-title">What This Paper Adds</div>
              <p class="rg-help-text">
                This paper is rated <strong>{escape(health_badge)}</strong> overall and contributes
                <strong>{claim_count}</strong> extracted claims to the graph. Use the tabs to jump
                between the methodology review and the full claim breakdown when you want more detail.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if paper.get("claims"):
            st.markdown('<p class="rg-subtitle">Preview claims</p>', unsafe_allow_html=True)
            preview_claims = paper["claims"][:2]
            for claim in preview_claims:
                st.markdown(
                    f"""
                    <div class="rg-claim-shell">
                      <div class="rg-claim-preview">{escape(_truncate_text(claim.get('claim', 'Untitled claim'), 190))}</div>
                      <div class="rg-detail-meta rg-detail-meta--compact">
                        {_claim_metadata_markup(claim)}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if claim_count > len(preview_claims):
                st.caption(f"Open the Claims tab to inspect all {claim_count} extracted claims.")
        else:
            st.info("No claims are available for this paper yet.")

    with methodology_tab:
        checks = health.get("checks", [])
        _render_health_summary(checks)
        render_flow_gap("md")
        st.markdown('<p class="rg-subtitle">Methodological Health Check</p>', unsafe_allow_html=True)
        for item in checks:
            tone = "healthy" if item.get("status") == "pass" else "caution" if item.get("status") == "warn" else "concern"
            st.markdown(
                f"""
                <div class="rg-check-shell">
                    <div style="display:flex;justify-content:space-between;gap:0.75rem;align-items:center;">
                    <strong>{escape(_pretty_check_label(item.get('check', 'check')))}</strong>
                    {_pill(
                        _pretty_label(item.get('status', 'unknown')),
                        tone,
                        tooltip=_tag_help_text("method_status", item.get("status", "")),
                    )}
                  </div>
                  <div class="rg-help-text" style="margin-top:0.55rem;">{escape(item.get('detail', 'No detail available.'))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if not checks:
            st.info("No methodology checks were returned for this paper.")

    with claims_tab:
        st.markdown(
            '<p class="rg-subtitle">Extracted substantive claims. Click a claim to expand the full detail.</p>',
            unsafe_allow_html=True,
        )
        for index, claim in enumerate(paper.get("claims", []), start=1):
            label = f"{index}. {_truncate_text(claim.get('claim', 'Untitled claim'))}"
            with st.expander(label, expanded=False):
                st.markdown(
                    f"""
                    <div class="rg-claim-metadata">
                    {_claim_metadata_markup(claim)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.write(claim.get("claim", ""))
                st.markdown(f"**Context**  \n{claim.get('context', 'n/a')}")
                st.markdown(
                    f"**Key variables**  \n{', '.join(claim.get('key_variables', [])) or 'n/a'}"
                )
                st.markdown(
                    f"**Why this evidence rating**  \n{claim.get('evidence_reasoning', 'n/a')}"
                )
        if not paper.get("claims"):
            st.info("No extracted claims are available for this paper.")


def _render_relationship_header(
    paper_a: dict,
    paper_b: dict,
    aggregate: dict,
    is_pending_only: bool,
) -> None:
    if is_pending_only:
        summary_tone = "pending"
        summary_text = "Pending"
        summary_note = "Comparison in progress"
        summary_pills = [
            _relationship_pill(
                "pending",
                label="Pending relationship",
                tooltip=_tag_help_text("relationship", "pending"),
            )
        ]
    else:
        dominant = aggregate.get("dominant", "supports")
        dominant_count = aggregate.get(dominant, 0)
        summary_tone = _relationship_tone(dominant)
        summary_text = _relationship_summary_text(dominant, dominant_count)
        summary_note = "Dominant relationship"
        summary_pills = [
            _relationship_pill("contradicts", label=_relationship_count_text("contradicts", aggregate.get("contradicts", 0))),
            _relationship_pill("supports", label=_relationship_count_text("supports", aggregate.get("supports", 0))),
            _relationship_pill("extends", label=_relationship_count_text("extends", aggregate.get("extends", 0))),
            _relationship_pill("qualifies", label=_relationship_count_text("qualifies", aggregate.get("qualifies", 0))),
        ]

    paper_a_meta = _paper_tile_meta(paper_a)
    paper_b_meta = _paper_tile_meta(paper_b)
    st.markdown(
        f"""
        <div class="rg-panel-card rg-relationship-header">
          <div class="rg-panel-title">Paper Relationship</div>
          <div class="rg-relationship-hero">
            <div class="rg-relationship-paper-card">
              <div class="rg-relationship-paper-label">Paper A</div>
              <div class="rg-relationship-paper-title">{escape(paper_a.get('title', 'Unknown paper'))}</div>
              {f'<div class="rg-detail-meta rg-detail-meta--paper-tile">{escape(paper_a_meta)}</div>' if paper_a_meta else ''}
            </div>
            <div class="rg-relationship-center">
              <div class="rg-relationship-badge rg-relationship-badge--{escape(summary_tone)}">{escape(summary_text)}</div>
              <div class="rg-relationship-center-note">{escape(summary_note)}</div>
            </div>
            <div class="rg-relationship-paper-card">
              <div class="rg-relationship-paper-label">Paper B</div>
              <div class="rg-relationship-paper-title">{escape(paper_b.get('title', 'Unknown paper'))}</div>
              {f'<div class="rg-detail-meta rg-detail-meta--paper-tile">{escape(paper_b_meta)}</div>' if paper_b_meta else ''}
            </div>
          </div>
          <div class="rg-pill-row rg-pill-row--relationship-summary">{''.join(summary_pills)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_edge_details(
    selection: dict,
    papers: dict[str, dict],
    paper_edges: dict[tuple[str, str], dict],
    relationship_index: dict[str, list[dict]],
    failed_pairs: dict[str, dict],
) -> None:
    edge_key = selection["id"]
    left, right = edge_key.split("||", maxsplit=1)
    paper_a = papers.get(left, {})
    paper_b = papers.get(right, {})
    aggregate = paper_edges.get(tuple(sorted((left, right))), {})
    pending = failed_pairs.get(edge_key)
    is_pending_only = bool(pending and not aggregate)
    _render_relationship_header(paper_a, paper_b, aggregate, is_pending_only)

    overview_tab, links_tab, notes_tab = st.tabs(["Overview", "Claim Relationships", "Method Notes"])

    with overview_tab:
        if is_pending_only:
            st.markdown(
                """
                <div class="rg-detail-card rg-edge-shell--pending">
                  <div class="rg-panel-title">Pending Comparison</div>
                  <p class="rg-help-text">
                    Hypatia added both papers to the map, but the comparison between them did not complete yet.
                    This line is shown as a pending paper relationship rather than a confirmed connection.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="rg-detail-card">
                  <div class="rg-panel-title">Aggregate View</div>
                  <p class="rg-help-text">
                    This paper relationship rolls up the claim relationships between the two papers.
                    Use the other tabs to inspect each underlying claim relationship and the methodological notes behind disagreements.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if aggregate:
                stat_cards = []
                for label, key in (
                    ("Contradictions", "contradicts"),
                    ("Supports", "supports"),
                    ("Extensions", "extends"),
                    ("Qualifications", "qualifies"),
                ):
                    tone = _relationship_tone(key)
                    stat_cards.append(
                        (
                            f'<div class="rg-edge-shell rg-edge-shell--{escape(tone)}">'
                            f'<div class="rg-edge-stat-label">{escape(label)}</div>'
                            f'<div class="rg-edge-stat-value">{aggregate.get(key, 0)}</div>'
                            '<div class="rg-detail-meta" style="margin-top:0.42rem;">claim relationships</div>'
                            "</div>"
                        )
                    )
                st.markdown(
                    f'<div class="rg-relationship-stats">{"".join(stat_cards)}</div>',
                    unsafe_allow_html=True,
                )

    all_relationships = relationship_index.get(edge_key, [])
    with links_tab:
        if is_pending_only:
            st.info("Claim relationships will appear here once the paper comparison completes.")
        elif not all_relationships:
            st.info("No claim relationships were stored for this paper relationship.")
        else:
            for index, relationship in enumerate(all_relationships, start=1):
                relationship_type = relationship.get("relationship", "related")
                relationship_strength = relationship.get("relationship_strength", "unknown")
                label = (
                    f"{index}. "
                    f"{_relationship_title(relationship_type)} "
                    f"({_pretty_label(relationship_strength)})"
                )
                with st.expander(label, expanded=False):
                    st.markdown(
                        f"""
                        <div class="rg-relationship-pill-row">
                          {_relationship_pill(relationship_type)}
                          {_pill(
                              _pretty_label(relationship_strength),
                              tooltip=_tag_help_text("relationship_strength", relationship_strength),
                          )}
                        </div>
                        <div class="rg-relationship-explainer">{escape(relationship.get('explanation', ''))}</div>
                        """,
                        unsafe_allow_html=True,
                    )

    with notes_tab:
        if is_pending_only:
            st.markdown(
                f"""
                <div class="rg-check-shell">
                  <strong>Last attempt</strong>
                  <div class="rg-help-text" style="margin-top:0.55rem;">{escape(_friendly_pair_error(pending.get('error', ''), pending.get('error_kind', '')))}</div>
                  {f'<div class="rg-detail-meta" style="margin-top:0.35rem;">Technical detail: {escape(pending.get("error", ""))}</div>' if pending.get('error') else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            notes = [item for item in all_relationships if item.get("methodological_note", "").strip()]
            if not notes:
                st.info("No explicit methodological notes were returned for this paper relationship.")
            for item in notes:
                relationship_type = item.get("relationship", "related")
                st.markdown(
                    f"""
                    <div class="rg-check-shell rg-edge-shell--{escape(_relationship_tone(relationship_type))}">
                      <strong>{escape(_relationship_title(relationship_type))}</strong>
                      <div class="rg-help-text" style="margin-top:0.55rem;">{escape(item.get('methodological_note', ''))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


_HEALTH_DOT_COLOR = {"healthy": "#5E897D", "caution": "#B78345", "concern": "#AB5E51"}
_HEALTH_LABEL = {"healthy": "Healthy", "caution": "Caution", "concern": "Concern"}
_HEALTH_BADGE_BG = {
    "healthy": "rgba(94, 137, 125, 0.12)",
    "caution": "rgba(183, 131, 69, 0.12)",
    "concern": "rgba(171, 94, 81, 0.12)",
}


def render_leaderboard(
    papers: dict[str, dict],
    measures: dict[str, dict],
) -> None:
    """Render a prioritised read-next list of up to 5 papers."""
    if not papers:
        st.markdown(
            """
            <div class="rg-empty-card">
              <h3 class="rg-detail-heading" style="font-size:1.45rem;">No papers yet</h3>
              <p class="rg-help-text" style="margin-top:0.7rem;">
                Add papers to your research map to see which ones are worth
                reading first.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    ranked = sorted(
        [(pid, measures.get(pid, {})) for pid in papers],
        key=lambda x: x[1].get("priority_score", 0.0),
        reverse=True,
    )[:5]

    items_html = ""
    for rank, (pid, m) in enumerate(ranked, 1):
        paper = papers[pid]
        raw_title = paper.get("title", "Untitled paper")
        year = str(paper.get("year") or "n.d.")
        authors = paper.get("authors", [])
        author_line = ", ".join(authors[:2]) + (" et al." if len(authors) > 2 else "")

        health = paper.get("health_score", {}).get("overall_score", "caution")
        dot_color = _HEALTH_DOT_COLOR.get(health, "#B78345")
        badge_label = _HEALTH_LABEL.get(health, "Caution")
        badge_bg = _HEALTH_BADGE_BG.get(health, "rgba(183, 131, 69, 0.12)")

        connections = m.get("degree", 0)
        conn_text = f"{connections} connection" if connections == 1 else f"{connections} connections"

        items_html += f"""
        <div class="rg-rl-item">
          <span class="rg-rl-num">{rank}</span>
          <div class="rg-rl-body">
            <div class="rg-rl-title" title="{escape(raw_title)}">{escape(raw_title)}</div>
            <div class="rg-rl-meta">
              {escape(author_line + (" · " if author_line else "") + year)}
              <span class="rg-rl-conn">{conn_text}</span>
            </div>
            <span class="rg-rl-badge" style="color:{dot_color};background:{badge_bg};">
              <span class="rg-rl-dot" style="background:{dot_color};"></span>
              {escape(badge_label)}
            </span>
          </div>
        </div>
        """

    st.markdown(
        f"""
        <style>
        .rg-read-list {{
          display: flex;
          flex-direction: column;
          gap: 0;
        }}
        .rg-rl-intro {{
          font-size: 0.82rem;
          color: var(--rg-muted);
          margin-bottom: 1rem;
          line-height: 1.5;
        }}
        .rg-rl-item {{
          display: flex;
          gap: 0.75rem;
          align-items: flex-start;
          padding: 0.85rem 0;
          border-bottom: 1px solid rgba(53, 38, 24, 0.07);
        }}
        .rg-rl-item:last-child {{ border-bottom: none; }}
        .rg-rl-num {{
          flex-shrink: 0;
          width: 1.4rem;
          font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
          font-size: 1.15rem;
          color: rgba(53, 38, 24, 0.25);
          line-height: 1.3;
          text-align: right;
        }}
        .rg-rl-body {{
          display: flex;
          flex-direction: column;
          gap: 0.22rem;
          min-width: 0;
        }}
        .rg-rl-title {{
          font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
          font-size: 0.9rem;
          color: var(--rg-ink);
          line-height: 1.35;
        }}
        .rg-rl-meta {{
          font-size: 0.77rem;
          color: var(--rg-muted);
          display: flex;
          align-items: center;
          gap: 0.5rem;
          flex-wrap: wrap;
        }}
        .rg-rl-conn {{
          font-size: 0.74rem;
          color: rgba(53, 38, 24, 0.38);
        }}
        .rg-rl-badge {{
          display: inline-flex;
          align-items: center;
          gap: 0.3rem;
          padding: 0.18rem 0.5rem;
          border-radius: 999px;
          font-size: 0.72rem;
          font-weight: 600;
          letter-spacing: 0.04em;
          width: fit-content;
        }}
        .rg-rl-dot {{
          width: 5px;
          height: 5px;
          border-radius: 50%;
          flex-shrink: 0;
        }}
        </style>
        <div class="rg-read-list">
          <p class="rg-rl-intro">
            Papers ranked by methodological quality first, then by influence
            across the relationship network.
          </p>
          {items_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_detail_panel(
    selected_graph_item: dict,
    papers: dict[str, dict],
    paper_edges: dict[tuple[str, str], dict],
    relationship_index: dict[str, list[dict]],
    failed_pairs: dict[str, dict],
) -> None:
    st.markdown('<div class="rg-panel-title">Knowledge Panel</div>', unsafe_allow_html=True)
    if not selection_is_meaningful(selected_graph_item):
        st.markdown(
            """
            <div class="rg-empty-card">
              <h3 class="rg-detail-heading" style="font-size:1.45rem;">Pick a paper or relationship</h3>
              <p class="rg-help-text" style="margin-top:0.7rem;">
                Click a paper to inspect its methodology and claims, or click a paper relationship
                to see where two papers support, contradict, or qualify one another.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if selected_graph_item["type"] == "node":
        paper = papers.get(selected_graph_item["id"])
        if not paper:
            st.warning("That paper is not available in the current cache.")
            return
        render_paper_details(paper)
        return

    if selected_graph_item["type"] == "edge":
        render_edge_details(selected_graph_item, papers, paper_edges, relationship_index, failed_pairs)
        return

    st.info("Click a paper or paper relationship to inspect details.")


def set_search_state(query: str, result: dict) -> None:
    st.session_state.search_state = {
        "query": query,
        "matching_claim_ids": result.get("matching_claim_ids", []),
        "paper_ids": result.get("paper_ids", []),
        "summary": result.get("summary", ""),
        "used_fallback": bool(result.get("used_fallback")),
        "fallback_error": result.get("fallback_error", ""),
    }
    st.session_state.reset_token += 1


def reset_view() -> None:
    st.session_state.selected_graph_item = {"type": "background", "id": None}
    st.session_state.search_state = {
        "query": "",
        "matching_claim_ids": [],
        "paper_ids": [],
        "summary": "",
        "used_fallback": False,
        "fallback_error": "",
    }
    st.session_state.reset_token += 1
    st.session_state.upload_error = ""
    st.session_state.upload_notice = ""
    st.session_state.pending_upload_paper = None
    st.session_state.pending_duplicate_matches = []
    st.session_state.delete_target_paper_id = None


def edge_key_for_selection(left: str, right: str) -> str:
    return pair_key(left, right)
