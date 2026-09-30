# syntax=docker/dockerfile:1
# Image for the `api` and `worker` services. Build context: the repository root
# (the uv workspace lockfile lives there). Pattern from
# https://docs.astral.sh/uv/guides/integration/docker/

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1. Third-party dependencies only: this layer is cached until uv.lock changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=backend/pyproject.toml,target=backend/pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace --package outreach-agents-backend

# 2. The application itself.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/app backend/app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package outreach-agents-backend

# Database migrations (run by the one-shot `migrate` service of docker compose).
COPY backend/alembic.ini backend/alembic.ini
COPY backend/migrations backend/migrations

# Never run as root inside the container.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
