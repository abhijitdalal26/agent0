# syntax=docker/dockerfile:1
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    AGENT0_API_HOST=0.0.0.0 \
    AGENT0_WORKSPACE_ROOT=/data/workspaces
RUN useradd --system --uid 10001 --create-home --home-dir /home/agent0 agent0 \
    && mkdir -p /data/workspaces && chown -R agent0:agent0 /data
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY config ./config
COPY agents ./agents
COPY skills ./skills
COPY plugins ./plugins
USER agent0
EXPOSE 8000
# uvicorn only listens after startup (DB, secrets, orchestrator) finished. The worker service disables this.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3     CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]
ENTRYPOINT ["agent0"]
CMD ["serve"]
