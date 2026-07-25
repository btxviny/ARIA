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

# CPU-only torch, installed before requirements.txt so pip's resolver is
# already satisfied by it and doesn't pull the ~4GB CUDA build that
# sentence-transformers would otherwise resolve to -- these containers have
# no GPU access, so CUDA torch is pure bloat.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install Python deps first so subsequent code changes don't bust the cache.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Pre-bake the local embedding model's weights into the image so the first
# RAG upload/query doesn't stall on a live download from huggingface.co.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application source.
COPY . .

# Default command is overridden per-service by docker-compose.yml.
CMD ["python", "-c", "print('Specify a command in docker-compose.yml')"]
