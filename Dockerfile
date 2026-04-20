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

# Install Python deps first so subsequent code changes don't bust the cache.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application source.
COPY . .

# Default command is overridden per-service by docker-compose.yml.
CMD ["python", "-c", "print('Specify a command in docker-compose.yml')"]
