FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock pytest.ini ./
ENV PATH="/app/.venv/bin:$PATH"
RUN uv sync --frozen --extra api --group dev --no-install-project

COPY api/main.py ./
COPY api/src/ ./src/
COPY api/tests/ ./tests/
COPY api/newrelic.ini ./newrelic.ini

EXPOSE 8000

CMD ["newrelic-admin", "run-program", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
