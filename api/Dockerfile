FROM python:3.11-slim AS builder

ENV UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra api --no-install-project

FROM python:3.11-slim AS runtime

ARG VERSION=dev
ARG BUILD_TIME=unknown

LABEL org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_TIME}" \
      org.opencontainers.image.description="Monkey AI Backend API"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

COPY api/main.py ./
COPY api/src/ ./src/
COPY api/alembic.ini ./alembic.ini
COPY api/alembic/ ./alembic/
COPY api/newrelic.ini ./newrelic.ini

EXPOSE 8000

CMD ["newrelic-admin", "run-program", "uvicorn", "main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]