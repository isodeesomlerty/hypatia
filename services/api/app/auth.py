from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class ViewerContext:
    user_id: str
    email: str
    display_name: str
    auth_mode: str
    default_workspace_id: str


def get_viewer_context(
    x_hypatia_user_id: str | None = Header(default=None),
    x_hypatia_user_email: str | None = Header(default=None),
    x_hypatia_user_name: str | None = Header(default=None),
    x_hypatia_auth_mode: str | None = Header(default=None),
    x_hypatia_default_workspace_id: str | None = Header(default=None),
) -> ViewerContext:
    user_id = x_hypatia_user_id or "demo-user"
    email = x_hypatia_user_email or "demo@hypatia.app"
    display_name = x_hypatia_user_name or "Hypatia Demo User"
    auth_mode = x_hypatia_auth_mode or "development"
    default_workspace_id = x_hypatia_default_workspace_id or "demo"

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing viewer identity")

    return ViewerContext(
        user_id=user_id,
        email=email,
        display_name=display_name,
        auth_mode=auth_mode,
        default_workspace_id=default_workspace_id,
    )
