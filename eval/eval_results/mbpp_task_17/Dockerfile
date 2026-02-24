# syntax=docker/dockerfile:1
FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# Copy project files
COPY pyproject.toml .
COPY solution.py .
COPY tests/ tests/

# Validate syntax
RUN python -m compileall .

# Pre-install pytest for potential future steps (no tests run here)
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --no-cache-dir pytest

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN useradd -m -u 1000 appuser
USER root
WORKDIR /app

# Copy artifacts from builder
COPY --from=builder /workspace/ .

# Ensure proper permissions for non-root user
RUN chown -R appuser:appuser /app

# Ensure Python can import modules from the app directory
ENV PYTHONPATH=/app

# Install pytest with cache to allow test runs
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-cache-dir pytest

# Re-validate syntax after copy
RUN python -m compileall .

USER appuser

CMD ["pytest","-q"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import solution as s; print(s.perimeter_of_square(2))" || exit 1
