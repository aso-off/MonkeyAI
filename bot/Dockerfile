# ---- Stage 1: builder ----
# Compiles all Python C extensions into .venv using build tools
FROM python:3.11-slim AS builder

ENV UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra bot --no-install-project

# ---- Stage 2: runtime ----
# Only the compiled .venv + source; no build tools, no headers
FROM python:3.11-slim AS runtime

ARG VERSION=dev
ARG BUILD_TIME=unknown

LABEL org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_TIME}" \
      org.opencontainers.image.description="Monkey AI Telegram Bot"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    ffmpeg \
    tzdata \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

COPY bot/src/ ./src/
COPY bot/main.py ./
COPY bot/newrelic.ini ./newrelic.ini

EXPOSE 5000

CMD ["newrelic-admin", "run-program", "uvicorn", "main:app", \
     "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]