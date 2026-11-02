# # Stage 1: Build dependencies using uv
# FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# WORKDIR /app

# ENV UV_COMPILE_BYTECODE=1

# RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# COPY pyproject.toml uv.lock ./
# COPY packages/geo_spatial_joiner/pyproject.toml ./packages/geo_spatial_joiner/

# RUN uv sync --frozen --no-dev --no-install-project

# COPY . .
# RUN uv sync --frozen --no-dev


# # Complete the virtual environment sync with the project code included
# RUN uv sync --frozen --no-dev

# # Place virtual environment binaries at the front of the PATH
# ENV PATH="/app/.venv/bin:$PATH"
# ENV PYTHONPATH="/app"

# # Execute the application module directly using the virtual environment python
# CMD ["python", "-m", "src.main"]

FROM python:3.14-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1
ENV UV_FROZEN=1
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/geo_spatial_joiner/pyproject.toml ./packages/geo_spatial_joiner/
RUN uv sync --no-install-project --no-dev

COPY . .
RUN uv sync --no-dev

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "src.main"]
