"""FastAPI application factory, lifespan, security middleware and SPA hosting."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from alembic import command
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chapter_tests import router as chapter_tests_router
from app.api.learner import router as learner_router
from app.api.lessons import router as lessons_router
from app.api.schemas import ConfigResponse, HealthResponse
from app.api.sessions import router as sessions_router
from app.config import BACKEND_DIR, Settings, get_settings
from app.content.validation import load_lessons
from app.db import create_db_engine, create_session_factory
from app.services.audio import AudioLibrary, load_audio_library
from app.services.content_sync import sync_content
from app.services.rate_limit import FailureLimiter

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = CSP
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            request.url.path.startswith("/api/")
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.headers.get("X-Requested-With") != "jp-practice"
        ):
            return JSONResponse(status_code=403, content={"detail": "Yêu cầu không hợp lệ."})
        return await call_next(request)


def _run_migrations(settings: Settings) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = settings.database_url
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def create_app(
    settings: Settings | None = None, lessons=None, audio: AudioLibrary | None = None
) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.ensure_data_dir()
        if settings.auto_migrate:
            _run_migrations(settings)
        loaded = lessons if lessons is not None else load_lessons(settings.content_dir)
        with session_factory() as db:
            sync_content(db, loaded)
        yield
        engine.dispose()

    app = FastAPI(title="Japanese Practice API", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.login_limiter = FailureLimiter()
    app.state.admin_login_limiter = FailureLimiter()
    app.state.audio = audio if audio is not None else load_audio_library()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.include_router(auth_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(learner_router, prefix="/api")
    app.include_router(lessons_router, prefix="/api")
    app.include_router(sessions_router, prefix="/api")
    app.include_router(chapter_tests_router, prefix="/api")

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config", response_model=ConfigResponse)
    def public_config() -> dict[str, object]:
        return {
            "registration_open": False,
            "registration_code_required": False,
            "session_size": settings.session_size,
            "focus_size": settings.focus_size,
        }

    @app.exception_handler(404)
    async def not_found(request: Request, _exc) -> Response:
        if request.url.path == "/api" or request.url.path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": "Không tìm thấy đường dẫn."})
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    frontend = settings.frontend_dist

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str, request: Request) -> Response:
        # API paths must never be swallowed by the history fallback.
        if request.url.path == "/api" or request.url.path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": "Không tìm thấy đường dẫn."})
        if not frontend.is_dir():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if path.startswith("assets/"):
            candidate = (frontend / path).resolve()
            if frontend.resolve() not in candidate.parents or not candidate.is_file():
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            return FileResponse(
                candidate, headers={"Cache-Control": "public, max-age=31536000, immutable"}
            )
        index = frontend / "index.html"
        if not index.is_file():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
