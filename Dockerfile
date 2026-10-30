# Stage 1: Build dependencies using uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Install dependencies first (leveraging Docker layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application code
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# Stage 2: Runtime image
FROM python:3.14-slim-bookworm

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Set path to use virtual environment python binaries
ENV PATH="/app/.venv/bin:$PATH"

# Run the ingestion worker script
CMD ["python", "-m", "src.main"]
