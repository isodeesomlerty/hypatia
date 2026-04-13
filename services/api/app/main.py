from __future__ import annotations

from fastapi import FastAPI

from app.config import settings
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.meta import router as meta_router
from app.routers.uploads import router as uploads_router
from app.routers.viewer import router as viewer_router
from app.routers.workspaces import router as workspaces_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Production API surface for Hypatia.",
    )
    app.include_router(health_router)
    app.include_router(meta_router)
    app.include_router(viewer_router)
    app.include_router(jobs_router)
    app.include_router(uploads_router)
    app.include_router(workspaces_router)
    return app


app = create_app()
