from __future__ import annotations

import hmac
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from agent0.api import routes_core, routes_ext, routes_models, routes_secrets, sse
from agent0.api.deps import ApiDeps
from agent0.api.errors import ApiError, RateLimiter, install_error_handlers
from agent0.config import Settings, get_settings
from agent0.models.registry import set_secret_resolver

log = logging.getLogger(__name__)

DEFAULT_API_KEY = "dev-key"


def check_startup(settings: Settings) -> None:
    if settings.env == "cloud" and settings.api_key == DEFAULT_API_KEY:
        raise RuntimeError("refusing to start in env=cloud with the default AGENT0_API_KEY")


def make_auth(settings: Settings) -> Callable[[Request], None]:
    expected = settings.api_key.encode()

    def require_auth(request: Request) -> None:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(token.strip().encode(), expected):
            raise ApiError(401, "unauthorized", "missing or invalid API key", {"WWW-Authenticate": "Bearer"})

    return require_auth


async def sync_registry(deps: ApiDeps) -> None:
    for profile in await deps.repos.model_profiles.list():
        try:
            deps.registry.update(profile)
        except KeyError:
            deps.registry.add(profile)


def create_app(
    deps: ApiDeps | None = None,
    *,
    build_deps: Callable[[], Awaitable[ApiDeps]] | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    if (deps is None) == (build_deps is None):
        raise ValueError("pass exactly one of deps or build_deps")
    settings = deps.settings if deps is not None else (settings or get_settings())
    check_startup(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if build_deps is not None:
            app.state.deps = await build_deps()
        current: ApiDeps = app.state.deps
        await current.secrets.load()
        set_secret_resolver(current.secrets.resolve)
        await sync_registry(current)
        try:
            yield
        finally:
            set_secret_resolver(None)
            if current.close is not None:
                await current.close()

    app = FastAPI(title="agent0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.mcp_status = {}
    app.state.secrets_limiter = RateLimiter()
    if deps is not None:
        app.state.deps = deps
        set_secret_resolver(deps.secrets.resolve)

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )

    api = APIRouter(prefix="/api/v1", dependencies=[Depends(make_auth(settings))])
    for module in (routes_core, routes_models, routes_ext, routes_secrets, sse):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
