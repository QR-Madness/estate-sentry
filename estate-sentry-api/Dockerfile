# Estate Sentry API Dockerfile
# Uses uv for fast Python package management.
#
# Build from the REPOSITORY ROOT, not from estate-sentry-api/:
#
#     docker build -f estate-sentry-api/Dockerfile .
#
# The API depends on ../estate-sentry-perception for the frame contract — it is
# imported rather than restated so the two cannot drift apart on the wire — and
# a build context cannot reach outside itself. Built from estate-sentry-api/,
# `uv sync` fails with "Distribution not found at file:///estate-sentry-perception".
# Compose sets the context accordingly; Dockerfile.dockerignore keeps that
# context to the two projects this image needs.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# UV_PYTHON_DOWNLOADS=0 pins the venv to this image's own interpreter. Left to
# itself uv may fetch a managed Python into /root/.local/share/uv, and the
# venv's interpreter symlink would then point at a path the runtime stage never
# receives — an image that builds and cannot start.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# At the path the API's uv source names: ../estate-sentry-perception from /app.
COPY estate-sentry-perception /estate-sentry-perception

COPY estate-sentry-api/pyproject.toml estate-sentry-api/uv.lock ./

# --no-editable: the lock marks perception editable, which is right for local
# development and wrong for an image. An editable install is a pointer back to a
# source tree; this installs it as an ordinary package inside the venv, so the
# runtime stage needs nothing outside /app.
# --no-install-project: nothing imports the API as a package — manage.py runs
# from source in /app.
RUN uv sync --frozen --no-dev --no-install-project --no-editable

COPY estate-sentry-api/ .

# =============================================================================
# Production image
# =============================================================================

# Must match the builder's base: the venv's interpreter is a symlink to
# /usr/local/bin/python3.12, which has to exist at the same path here.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# The application and its venv, in one copy.
COPY --from=builder /app /app

# Allowed to fail the build. It used to end in `|| true`, so an image whose
# collectstatic had failed still built green and served a dashboard with no
# htmx, no SSE extension, no overlay and no CSS.
RUN python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# ASGI, not WSGI. The HQ MJPEG and SSE endpoints hold a connection open for as
# long as someone watches; under gunicorn's sync workers each viewer pinned a
# worker, and three viewers left /api/health/ unanswered after 8s. Under uvicorn
# the same server answered in 30ms with four.
#
# `exec` makes uvicorn PID 1, so `docker stop`'s SIGTERM reaches it rather than
# dying with the shell — without it Docker waits ten seconds and SIGKILLs.
# --timeout-graceful-shutdown bounds the wait for the streams, which never end
# on their own; the same lesson `task hq:serve` already encodes.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec uvicorn estate_sentry.asgi:application --host 0.0.0.0 --port 8000 --workers 3 --timeout-graceful-shutdown 5"]
