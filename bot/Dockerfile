FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    UV_COMPILE_BYTECODE=1

# System dependencies:
#   build-essential — C extensions (cryptography)
#   libffi-dev      — cryptography, asyncssh
#   libssl-dev      — asyncssh, cryptography
#   ffmpeg          — voice message processing
#   tzdata          — TZ env variable support
#   docker.io       — Docker CLI for container management via socket
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    tzdata \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies (separate layer for caching)
COPY pyproject.toml uv.lock pytest.ini ./
ENV PATH="/app/.venv/bin:$PATH"
RUN uv sync --frozen --extra bot --group dev --no-install-project

# Copy source code
COPY bot/src/ ./src/
COPY bot/main.py ./
COPY bot/tests/ ./tests/
COPY bot/newrelic.ini ./newrelic.ini

EXPOSE 5000

CMD ["newrelic-admin", "run-program", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]
