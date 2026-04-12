from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv()

import streamlit as st  # noqa: E402

from research_graph.cache import (  # noqa: E402
    clear_cached_corpus,
    current_pairwise_status,
    load_cached_dataset,
    remove_pair_relationships_for_paper,
    remove_paper_record,
    save_combined_dataset,
)
from research_graph.components.graph_component import render_graph_component  # noqa: E402
from research_graph.graph import (  # noqa: E402
    aggregate_paper_edges,
    build_graph_payload,
    build_pending_pair_index,
    build_relationship_index,
)
from research_graph.pipeline import (  # noqa: E402
    PAPER_ANALYSIS_SIGNATURE,
    PAIRWISE_ANALYSIS_SIGNATURE,
    analyze_uploaded_pdf,
    detect_potential_duplicates,
    merge_uploaded_paper,
    search_claims,
)
from research_graph.ui import (  # noqa: E402
    build_processing_card_markup,
    build_progress_timeline_markup,
    clear_upload_widget,
    inject_global_styles,
    initialize_session_state,
    render_detail_panel,
    render_flow_gap,
    render_hero,
    render_metric_cards,
    render_search_summary,
    reset_view,
    set_search_state,
    _pending_relationship_message,
)


def load_dataset_into_session(force: bool = False) -> None:
    if st.session_state.data_loaded and not force:
        return

    papers, relationships, paper_edges, manifest = load_cached_dataset(
        analysis_signature=PAPER_ANALYSIS_SIGNATURE,
        pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
    )
    if papers and not paper_edges:
        paper_edges = aggregate_paper_edges(relationships, papers)

    st.session_state.papers = papers
    st.session_state.relationships = relationships
    st.session_state.paper_edges = paper_edges
    st.session_state.manifest = manifest
    st.session_state.relationship_index = build_relationship_index(relationships, papers)
    st.session_state.failed_pairs = build_pending_pair_index(
        manifest,
        papers,
        pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
    )
    st.session_state.data_loaded = True


def sync_dataset(
    papers: dict[str, dict],
    relationships: list[dict],
    paper_edges: dict[tuple[str, str], dict],
    manifest: dict,
) -> None:
    st.session_state.papers = papers
    st.session_state.relationships = relationships
    st.session_state.paper_edges = paper_edges
    st.session_state.manifest = manifest
    st.session_state.relationship_index = build_relationship_index(relationships, papers)
    st.session_state.failed_pairs = build_pending_pair_index(
        manifest,
        papers,
        pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
    )
    st.session_state.data_loaded = True


def pairwise_status_summary(
    papers: dict[str, dict],
    manifest: dict,
    paper_edges: dict[tuple[str, str], dict],
) -> dict[str, int]:
    return current_pairwise_status(
        papers,
        manifest,
        paper_edges,
        pairwise_signature=PAIRWISE_ANALYSIS_SIGNATURE,
    )


def main() -> None:
    st.set_page_config(
        page_title="Hypatia",
        page_icon="H",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_styles()
    initialize_session_state()
    load_dataset_into_session()

    render_hero()
    render_metric_cards(
        len(st.session_state.papers),
        len(st.session_state.relationships),
        len(st.session_state.paper_edges),
    )
    render_flow_gap("md")

    with st.form("search_form", clear_on_submit=False):
        query = st.text_input(
            "Ask Hypatia",
            value=st.session_state.search_state.get("query", ""),
            placeholder="Example: does RLHF cause sycophancy?",
        )
        search_submitted = st.form_submit_button("Search")

    controls_left, controls_mid, controls_right = st.columns([1, 1, 3])
    if controls_left.button("Reset view", use_container_width=True):
        reset_view()
        st.rerun()

    st.session_state.hide_low_signal_edges = controls_mid.checkbox(
        "Hide weaker relationships",
        value=st.session_state.hide_low_signal_edges,
    )

    if search_submitted:
        if not st.session_state.papers:
            st.warning("Add papers to your research map before searching.")
        elif not query.strip():
            st.warning("Enter a search query first.")
        else:
            with st.spinner("Searching claims..."):
                result = search_claims(query.strip(), st.session_state.papers)
            set_search_state(query.strip(), result)
            st.session_state.selected_graph_item = {"type": "background", "id": None}
            st.rerun()

    if st.session_state.upload_error:
        st.error(st.session_state.upload_error)
    if st.session_state.upload_notice:
        st.success(st.session_state.upload_notice)

    selected_paper = None
    if st.session_state.selected_graph_item.get("type") == "node":
        selected_paper = st.session_state.papers.get(st.session_state.selected_graph_item.get("id"))
    selected_paper_id = selected_paper["paper_id"] if selected_paper else None
    if st.session_state.delete_target_paper_id != selected_paper_id:
        st.session_state.delete_target_paper_id = selected_paper_id

    main_col, detail_col = st.columns([1.9, 1.1], gap="large")

    with main_col:
        st.markdown('<div class="rg-panel-title">Research Map</div>', unsafe_allow_html=True)
        if not st.session_state.papers:
            st.info(
                "Your research map is empty. Add a paper below to get started, or preload a larger library before you open Hypatia."
            )
        highlighted = st.session_state.search_state.get("paper_ids", [])
        nodes, edges = build_graph_payload(
            st.session_state.papers,
            st.session_state.paper_edges,
            pending_pairs=st.session_state.failed_pairs,
            highlighted_paper_ids=highlighted,
            hide_low_signal_edges=st.session_state.hide_low_signal_edges,
        )
        selection = render_graph_component(
            nodes=nodes,
            edges=edges,
            highlight_node_ids=highlighted,
            focus_node_ids=highlighted,
            reset_token=st.session_state.reset_token,
            height=760,
        )
        if selection != st.session_state.selected_graph_item:
            st.session_state.selected_graph_item = selection
            st.rerun()

        with st.expander("Add a paper", expanded=False):
            st.markdown(
                """
                <div class="rg-expander-intro">
                  <div class="rg-panel-title">Single-paper upload</div>
                  <p class="rg-help-text">
                    Upload one PDF to analyze it and add it to the current research map.
                    Hypatia will extract the paper's claims, assess its methodology, and link it to related work already in the map.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader(
                "Choose one PDF to add",
                type=["pdf"],
                accept_multiple_files=False,
                label_visibility="collapsed",
                key=f"single_paper_uploader_{st.session_state.uploader_reset_token}",
            )
            analyze_upload = st.button("Analyze and add paper", disabled=uploaded_file is None)
            if st.session_state.pending_upload_paper and st.session_state.pending_duplicate_matches:
                pending_paper = st.session_state.pending_upload_paper
                st.warning(
                    f"'{pending_paper['title']}' looks similar to papers already in the map. "
                    "Review the closest matches before adding it."
                )
                for match in st.session_state.pending_duplicate_matches:
                    author_line = ", ".join(match.get("authors", [])) or "Unknown authors"
                    reason_line = "; ".join(match.get("reasons", []))
                    year = match.get("year") or "n.d."
                    st.markdown(
                        f"- **{match['title']}** ({year})  \n"
                        f"  {author_line}  \n"
                        f"  Why flagged: {reason_line}"
                    )
                review_left, review_mid, _ = st.columns([1, 1, 2])
                add_anyway = review_left.button("Add anyway", key="confirm_duplicate_upload")
                cancel_review = review_mid.button("Cancel", key="cancel_duplicate_upload")
                if add_anyway:
                    st.session_state.upload_error = ""
                    progress_card = st.empty()
                    progress_details = st.empty()
                    progress_events: list[dict] = []

                    def handle_merge_progress(event: dict) -> None:
                        progress_value = event.get("progress")
                        current_progress = 0.45
                        if progress_value is not None:
                            current_progress = max(0.01, min(float(progress_value), 1.0))
                        message = event.get("message", "").strip()
                        if message:
                            progress_events.append(
                                {
                                    "stage": event.get("stage", ""),
                                    "message": message,
                                    "error": event.get("error", ""),
                                }
                            )
                            progress_card.markdown(
                                build_processing_card_markup(message, current_progress),
                                unsafe_allow_html=True,
                            )
                            timeline_markup = build_progress_timeline_markup(progress_events[-6:])
                            if timeline_markup:
                                with progress_details.container():
                                    with st.expander("Show details", expanded=False):
                                        st.markdown(timeline_markup, unsafe_allow_html=True)
                            else:
                                progress_details.empty()

                    try:
                        papers = dict(st.session_state.papers)
                        paper = st.session_state.pending_upload_paper
                        relationships, paper_edges, pair_failures = merge_uploaded_paper(
                            paper,
                            papers,
                            st.session_state.manifest,
                            progress_callback=handle_merge_progress,
                        )
                        progress_card.markdown(
                            build_processing_card_markup("Paper added", 1.0),
                            unsafe_allow_html=True,
                        )
                        progress_details.empty()
                        sync_dataset(
                            papers,
                            relationships,
                            paper_edges,
                            st.session_state.manifest,
                        )
                        st.session_state.selected_graph_item = {"type": "node", "id": paper["paper_id"]}
                        pairwise_status = pairwise_status_summary(
                            papers,
                            st.session_state.manifest,
                            paper_edges,
                        )
                        st.session_state.upload_notice = (
                            f"Added {paper['title']}. "
                            f"Hypatia has processed {pairwise_status['processed_pair_count']} of "
                            f"{pairwise_status['potential_pair_count']} possible paper comparisons, "
                            f"with {pairwise_status['paper_edge_count']} visible paper relationships."
                        )
                        if pair_failures:
                            st.session_state.upload_notice += (
                                f" {_pending_relationship_message(len(pair_failures))}"
                            )
                        st.session_state.pending_upload_paper = None
                        st.session_state.pending_duplicate_matches = []
                        clear_upload_widget()
                        st.session_state.reset_token += 1
                        st.rerun()
                    except Exception as exc:
                        st.session_state.upload_error = str(exc)
                        st.rerun()
                if cancel_review:
                    st.session_state.pending_upload_paper = None
                    st.session_state.pending_duplicate_matches = []
                    st.session_state.upload_notice = "Canceled the pending upload."
                    clear_upload_widget()
                    st.rerun()
            if analyze_upload and uploaded_file is not None:
                st.session_state.upload_error = ""
                st.session_state.upload_notice = ""
                st.session_state.pending_upload_paper = None
                st.session_state.pending_duplicate_matches = []
                progress_card = st.empty()
                progress_details = st.empty()
                progress_events: list[dict] = []
                progress_card.markdown(
                    build_processing_card_markup("Preparing paper", 0.02),
                    unsafe_allow_html=True,
                )

                def handle_upload_progress(event: dict) -> None:
                    progress_value = event.get("progress")
                    current_progress = 0.02
                    if progress_value is not None:
                        current_progress = max(0.01, min(float(progress_value), 1.0))
                    message = event.get("message", "").strip()
                    if message:
                        progress_events.append(
                            {
                                "stage": event.get("stage", ""),
                                "message": message,
                                "error": event.get("error", ""),
                            }
                        )
                        progress_card.markdown(
                            build_processing_card_markup(message, current_progress),
                            unsafe_allow_html=True,
                        )
                        timeline_markup = build_progress_timeline_markup(progress_events[-6:])
                        if timeline_markup:
                            with progress_details.container():
                                with st.expander("Show details", expanded=False):
                                    st.markdown(timeline_markup, unsafe_allow_html=True)
                        else:
                            progress_details.empty()
                try:
                    papers = dict(st.session_state.papers)
                    paper = analyze_uploaded_pdf(
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        st.session_state.manifest,
                        progress_callback=handle_upload_progress,
                    )
                    duplicate_matches = detect_potential_duplicates(paper, st.session_state.papers)
                    if duplicate_matches:
                        progress_card.markdown(
                            build_processing_card_markup("Ready for review", 1.0),
                            unsafe_allow_html=True,
                        )
                        st.session_state.pending_upload_paper = paper
                        st.session_state.pending_duplicate_matches = duplicate_matches
                        st.session_state.upload_notice = (
                            "The paper is ready. Review the possible duplicate matches below."
                        )
                        clear_upload_widget()
                        st.rerun()

                    relationships, paper_edges, pair_failures = merge_uploaded_paper(
                        paper,
                        papers,
                        st.session_state.manifest,
                        progress_callback=handle_upload_progress,
                    )
                    progress_card.markdown(
                        build_processing_card_markup("Paper added", 1.0),
                        unsafe_allow_html=True,
                    )
                    progress_details.empty()
                    sync_dataset(
                        papers,
                        relationships,
                        paper_edges,
                        st.session_state.manifest,
                    )
                    st.session_state.selected_graph_item = {"type": "node", "id": paper["paper_id"]}
                    pairwise_status = pairwise_status_summary(
                        papers,
                        st.session_state.manifest,
                        paper_edges,
                    )
                    st.session_state.upload_notice = (
                        f"Added {paper['title']}. "
                        f"Hypatia has processed {pairwise_status['processed_pair_count']} of "
                        f"{pairwise_status['potential_pair_count']} possible paper comparisons, "
                        f"with {pairwise_status['paper_edge_count']} visible paper relationships."
                    )
                    if pair_failures:
                        st.session_state.upload_notice += (
                            f" {_pending_relationship_message(len(pair_failures))}"
                        )
                    clear_upload_widget()
                    st.session_state.reset_token += 1
                    st.rerun()
                except Exception as exc:
                    st.session_state.upload_error = str(exc)
                    st.rerun()

        with st.expander("Manage papers", expanded=False):
            st.markdown(
                """
                <div class="rg-expander-intro">
                  <div class="rg-panel-title">Edit this research map</div>
                  <p class="rg-help-text">
                    Remove the selected paper or clear the current map.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if selected_paper:
                selected_year_suffix = f" ({selected_paper.get('year')})" if selected_paper.get("year") else ""
                st.markdown(
                    f"Selected paper: **{selected_paper['title']}**{selected_year_suffix}"
                )
            else:
                st.markdown("Selected paper: **None**")

            delete_confirm = st.checkbox(
                "Confirm deletion of the selected paper",
                disabled=selected_paper is None,
                key=f"confirm_delete_selected_paper_{selected_paper_id or 'none'}_{st.session_state.reset_token}",
            )
            delete_selected = st.button(
                "Delete selected paper",
                disabled=selected_paper is None or not delete_confirm,
                use_container_width=True,
                key="delete_selected_paper_button",
            )
            if delete_selected and selected_paper is not None:
                papers = dict(st.session_state.papers)
                manifest = st.session_state.manifest
                claim_ids = {claim["claim_id"] for claim in selected_paper.get("claims", [])}
                papers.pop(selected_paper["paper_id"], None)
                relationships = [
                    relationship
                    for relationship in st.session_state.relationships
                    if relationship.get("source_claim_id") not in claim_ids
                    and relationship.get("target_claim_id") not in claim_ids
                ]
                remove_paper_record(selected_paper, manifest)
                remove_pair_relationships_for_paper(selected_paper["paper_id"], manifest)
                paper_edges = aggregate_paper_edges(relationships, papers)
                save_combined_dataset(papers, relationships, paper_edges, manifest)
                reset_view()
                sync_dataset(papers, relationships, paper_edges, manifest)
                st.session_state.upload_notice = f"Removed {selected_paper['title']} from the cached corpus."
                clear_upload_widget()
                st.rerun()

            st.divider()
            clear_confirm = st.checkbox(
                "Confirm clearing all cached corpus data",
                disabled=not st.session_state.papers,
                key=f"confirm_clear_corpus_{st.session_state.reset_token}",
            )
            clear_corpus = st.button(
                "Clear all cached papers",
                disabled=not st.session_state.papers or not clear_confirm,
                use_container_width=True,
                key="clear_cached_corpus_button",
            )
            if clear_corpus:
                manifest = clear_cached_corpus()
                reset_view()
                sync_dataset({}, [], {}, manifest)
                st.session_state.upload_notice = "Cleared all cached corpus data."
                clear_upload_widget()
                st.rerun()

    with detail_col:
        render_search_summary(st.session_state.search_state)
        render_detail_panel(
            st.session_state.selected_graph_item,
            st.session_state.papers,
            st.session_state.paper_edges,
            st.session_state.relationship_index,
            st.session_state.failed_pairs,
        )


if __name__ == "__main__":
    main()
