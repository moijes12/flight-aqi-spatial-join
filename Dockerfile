# Stage 1: Build dependencies using uv
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation and UV optimizations
ENV UV_COMPILE_BYTECODE=1

# Install git (required if dependencies pull from git repos or package indexes)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy root configuration and lock files first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# If you have local workspace packages, copy their pyproject.toml files here as well:
COPY packages/geo_spatial_joiner/pyproject.toml ./packages/geo_spatial_joiner/

# Install project dependencies without the project itself first
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application source code and packages
COPY . .

# Complete the virtual environment sync with the project code included
RUN uv sync --frozen --no-dev


# Stage 2: Lightweight runtime image
FROM python:3.14-slim-bookworm

WORKDIR /app

# Copy the pre-built virtual environment and source code from the builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/packages /app/packages

# Configure environment paths and ensure Python recognizes /app as the module root
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Execute the ingestion worker script as a module
CMD ["python", "-m", "src.main"]
