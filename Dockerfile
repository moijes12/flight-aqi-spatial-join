# Stage 1: Build dependencies using uv
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev


# Stage 2: Lightweight runtime image
FROM python:3.14-slim-bookworm

WORKDIR /app

# Copy virtual environment and source code from builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/packages /app/packages

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# CRITICAL: Use the absolute path to the virtualenv python interpreter
CMD ["/app/.venv/bin/python", "-m", "src.main"]
