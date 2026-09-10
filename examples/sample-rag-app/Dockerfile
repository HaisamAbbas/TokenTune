FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_HTTP_TIMEOUT=300

ENV UV_PYTHON_DOWNLOADS=0

RUN apt-get update && apt-get install curl build-essential -y

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"

# Build context is the repo root (see docker-compose.yml) because this app's
# `ai-cost-optimizer-sdk` dependency is a local path dependency (`../../sdk`
# relative to this app's pyproject.toml) - the sdk source has to be in the
# build context alongside the app, mirroring the repo's own layout.
WORKDIR /app

COPY sdk ./sdk

WORKDIR /app/examples/sample-rag-app

RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=examples/sample-rag-app/uv.lock,target=uv.lock \
  --mount=type=bind,source=examples/sample-rag-app/pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-dev

RUN touch README.md

COPY examples/sample-rag-app/pyproject.toml examples/sample-rag-app/uv.lock ./

COPY examples/sample-rag-app/src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm

WORKDIR /app/examples/sample-rag-app

COPY --from=builder /app /app
COPY examples/sample-rag-app/scripts ./scripts
COPY examples/sample-rag-app/corpus ./corpus

ENV PATH="/app/examples/sample-rag-app/.venv/bin:$PATH" HOST="0.0.0.0"

CMD ["api"]
