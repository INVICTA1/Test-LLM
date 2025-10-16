# Multi-stage build for SWE-bench infrastructure
FROM python:3.10-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy project files
COPY task-release-2025-07-29-115124/ /app/

# Create virtual environment and install dependencies
RUN uv venv && \
    uv pip install -e .

# Set environment variables
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create output directory for results
RUN mkdir -p /app/output

# Default command
CMD ["python", "-m", "swe_bench_downloader", "--help"]

