from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

_GRAPH_COMPONENT = components.declare_component(
    "research_graph_network",
    path=str(FRONTEND_DIR),
)


def render_graph_component(
    *,
    nodes: list[dict],
    edges: list[dict],
    highlight_node_ids: list[str] | None,
    focus_node_ids: list[str] | None,
    reset_token: int,
    height: int = 9000,
    key: str = "research_graph_network",
):
    return _GRAPH_COMPONENT(
        nodes=nodes,
        edges=edges,
        highlight_node_ids=highlight_node_ids or [],
        focus_node_ids=focus_node_ids or [],
        reset_token=reset_token,
        height=height,
        default={"type": "background", "id": None},
        key=key,
    )
