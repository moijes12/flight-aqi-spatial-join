FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY packages/geo_spatial_joiner ./packages/geo_spatial_joiner
RUN uv sync --frozen --no-dev --no-install-project

COPY . /app
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

CMD ["flight-aqi-job"]
