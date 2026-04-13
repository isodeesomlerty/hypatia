from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from fastapi import Header, HTTPException

from app.config import settings

try:
    import jwt
    from jwt import PyJWKClient
    from jwt.exceptions import InvalidTokenError
except ImportError:  # pragma: no cover - optional during scaffold bootstrapping
    jwt = None
    PyJWKClient = None
    InvalidTokenError = Exception


@dataclass(frozen=True)
class ViewerContext:
    user_id: str
    email: str
    display_name: str
    auth_mode: str
    default_workspace_id: str


def _derive_default_workspace_id(user_id: str, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    sanitized = "".join(ch for ch in user_id if ch.isalnum())
    suffix = sanitized[-12:] or "personal"
    return f"ws-{suffix.lower()}"


def _jwks_url() -> str:
    if settings.clerk_jwks_url:
        return settings.clerk_jwks_url
    issuer = settings.clerk_issuer.rstrip("/")
    if issuer:
        return f"{issuer}/.well-known/jwks.json"
    return ""


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    jwks_url = _jwks_url()
    if not jwks_url:
        raise HTTPException(
            status_code=500,
            detail="Clerk JWT verification is not configured",
        )
    if PyJWKClient is None:
        raise HTTPException(
            status_code=500,
            detail="PyJWT is not installed for Clerk token verification",
        )
    return PyJWKClient(jwks_url)


def _verify_clerk_token(token: str) -> dict:
    if jwt is None:
        raise HTTPException(
            status_code=500,
            detail="PyJWT is not installed for Clerk token verification",
        )
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "options": {"verify_aud": False},
        }
        if settings.clerk_issuer:
            decode_kwargs["issuer"] = settings.clerk_issuer
        return jwt.decode(token, signing_key.key, **decode_kwargs)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Clerk token: {exc}") from exc


def _development_viewer(
    x_hypatia_user_id: str | None,
    x_hypatia_user_email: str | None,
    x_hypatia_user_name: str | None,
    x_hypatia_auth_mode: str | None,
    x_hypatia_default_workspace_id: str | None,
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


def _clerk_viewer(
    claims: dict,
    x_hypatia_user_email: str | None,
    x_hypatia_user_name: str | None,
    x_hypatia_default_workspace_id: str | None,
) -> ViewerContext:
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Clerk token missing subject")

    raw_name = claims.get("name")
    if not raw_name:
        given_name = claims.get("given_name", "")
        family_name = claims.get("family_name", "")
        raw_name = f"{given_name} {family_name}".strip()

    email = claims.get("email") or x_hypatia_user_email or f"{user_id}@clerk.local"
    display_name = raw_name or x_hypatia_user_name or "Hypatia User"
    default_workspace_id = _derive_default_workspace_id(
        user_id,
        x_hypatia_default_workspace_id,
    )

    return ViewerContext(
        user_id=user_id,
        email=email,
        display_name=display_name,
        auth_mode="clerk",
        default_workspace_id=default_workspace_id,
    )


def get_viewer_context(
    authorization: str | None = Header(default=None),
    x_hypatia_user_id: str | None = Header(default=None),
    x_hypatia_user_email: str | None = Header(default=None),
    x_hypatia_user_name: str | None = Header(default=None),
    x_hypatia_auth_mode: str | None = Header(default=None),
    x_hypatia_default_workspace_id: str | None = Header(default=None),
) -> ViewerContext:
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    if token:
        claims = _verify_clerk_token(token)
        token_issuer = claims.get("iss", "")
        if settings.clerk_issuer and token_issuer:
            parsed_issuer = urlparse(settings.clerk_issuer)
            parsed_token_issuer = urlparse(token_issuer)
            if parsed_issuer.netloc and parsed_issuer.netloc != parsed_token_issuer.netloc:
                raise HTTPException(status_code=401, detail="Clerk issuer mismatch")
        return _clerk_viewer(
            claims,
            x_hypatia_user_email=x_hypatia_user_email,
            x_hypatia_user_name=x_hypatia_user_name,
            x_hypatia_default_workspace_id=x_hypatia_default_workspace_id,
        )

    if settings.environment == "development" or settings.allow_dev_auth:
        return _development_viewer(
            x_hypatia_user_id=x_hypatia_user_id,
            x_hypatia_user_email=x_hypatia_user_email,
            x_hypatia_user_name=x_hypatia_user_name,
            x_hypatia_auth_mode=x_hypatia_auth_mode,
            x_hypatia_default_workspace_id=x_hypatia_default_workspace_id,
        )

    raise HTTPException(status_code=401, detail="Missing Clerk bearer token")
