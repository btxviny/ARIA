# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps:
#   - build-essential + libxml2-dev + libxslt1-dev: needed for lxml (used by trafilatura)
#   - curl: lightweight healthchecks
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libxml2-dev \
      libxslt1-dev \
      curl \
 && rm -rf /var/lib/apt/lists/*

# uv: fast, reproducible installs from the committed uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

# The venv lives outside /app so the dev compose override's `./:/app` bind
# mount never shadows it. torch resolves to the CPU-only wheel (see
# [tool.uv.sources] in pyproject.toml) -- no GPU in these containers.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

# Install deps first so subsequent code changes don't bust the cache.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Pre-bake the local embedding model's weights into the image so the first
# RAG upload/query doesn't stall on a live download from huggingface.co.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application source.
COPY . .

# Default command is overridden per-service by docker-compose.yml.
CMD ["python", "-c", "print('Specify a command in docker-compose.yml')"]
