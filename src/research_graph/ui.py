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
        "visible_edge_types": ["contradicts", "supports", "extends", "qualifies"],
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
    }
    kind_map = help_texts.get(kind, {})
    return kind_map.get(normalized, kind_map.get(normalized.lower(), kind_map.get("default", "")))


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
            padding: 0 1.15rem 1.1rem;
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


def render_metric_cards(
    paper_count: int,
    relationship_count: int,
    edge_count: int,
    pairwise_status: dict[str, int] | None = None,
) -> None:
    pairwise_status = pairwise_status or {}
    potential_pair_count = pairwise_status.get("potential_pair_count", 0)
    processed_pair_count = pairwise_status.get("processed_pair_count", 0)
    cards = [
        ("Corpus", str(paper_count), "papers loaded"),
        ("Potential Pairs", str(potential_pair_count), "possible paper-to-paper comparisons"),
        ("Processed Pairs", str(processed_pair_count), "pairwise comparisons completed"),
        ("Claim Relationships", str(relationship_count), "cross-paper claim relationships"),
        ("Paper Relationships", str(edge_count), "paper pairs deemed related enough to draw"),
    ]
    columns = st.columns(len(cards))
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


def render_edge_details(
    selection: dict,
    papers: dict[str, dict],
    paper_edges: dict[tuple[str, str], dict],
    relationship_index: dict[str, list[dict]],
) -> None:
    edge_key = selection["id"]
    left, right = edge_key.split("||", maxsplit=1)
    paper_a = papers.get(left, {})
    paper_b = papers.get(right, {})
    aggregate = paper_edges.get(tuple(sorted((left, right))), {})

    title = f"{paper_a.get('title', left)} <-> {paper_b.get('title', right)}"
    _render_panel_header(
        eyebrow="Paper Relationship",
        title=title,
        pills=[
            _pill(_count_label(aggregate.get('contradicts', 0), "contradiction")),
            _pill(_count_label(aggregate.get('supports', 0), "support")),
            _pill(_count_label(aggregate.get('extends', 0), "extension")),
            _pill(_count_label(aggregate.get('qualifies', 0), "qualification")),
        ],
    )

    overview_tab, links_tab, notes_tab = st.tabs(["Overview", "Claim Relationships", "Method Notes"])

    with overview_tab:
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
            for label, key in (
                ("Contradictions", "contradicts"),
                ("Supports", "supports"),
                ("Extensions", "extends"),
                ("Qualifications", "qualifies"),
            ):
                st.markdown(
                    f"""
                    <div class="rg-edge-shell">
                      <strong>{escape(label)}</strong>
                      <div class="rg-detail-meta" style="margin-top:0.35rem;">{aggregate.get(key, 0)} claim relationships</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    all_relationships = relationship_index.get(edge_key, [])
    with links_tab:
        if not all_relationships:
            st.info("No claim relationships were stored for this paper relationship.")
        for index, relationship in enumerate(all_relationships, start=1):
            label = (
                f"{index}. "
                f"{_pretty_label(relationship.get('relationship', 'related'))} "
                f"({relationship.get('relationship_strength', 'unknown')})"
            )
            with st.expander(label, expanded=False):
                st.markdown(_pill(_pretty_label(relationship.get("relationship", "related"))), unsafe_allow_html=True)
                st.write(relationship.get("explanation", ""))
                st.caption(
                    f"{relationship.get('source_claim_id', 'unknown')} -> {relationship.get('target_claim_id', 'unknown')}"
                )

    with notes_tab:
        notes = [item for item in all_relationships if item.get("methodological_note", "").strip()]
        if not notes:
            st.info("No explicit methodological notes were returned for this paper relationship.")
        for item in notes:
            st.markdown(
                f"""
                <div class="rg-check-shell">
                  <strong>{escape(_pretty_label(item.get('relationship', 'related')))}</strong>
                  <div class="rg-help-text" style="margin-top:0.55rem;">{escape(item.get('methodological_note', ''))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_detail_panel(
    selected_graph_item: dict,
    papers: dict[str, dict],
    paper_edges: dict[tuple[str, str], dict],
    relationship_index: dict[str, list[dict]],
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
        render_edge_details(selected_graph_item, papers, paper_edges, relationship_index)
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
