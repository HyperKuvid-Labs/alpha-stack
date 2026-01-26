# syntax=docker/dockerfile:1

# ---- Base/Builder Stage ----
# This stage installs all dependencies and validates the source code.
FROM python:3.11-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install dependencies
# Use a BuildKit cache mount to speed up subsequent builds.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code
COPY . .

# Set PYTHONPATH for src layout
ENV PYTHONPATH=/app/src

# Validate syntax by compiling all python files
# The -q flag suppresses output on success
RUN python -m compileall -q .


# ---- Production Stage ----
# This stage creates the final, lean production image.
FROM python:3.11-slim-bookworm AS production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Set PYTHONPATH so 'gunicorn' and the app can find modules in /app/src
    PYTHONPATH=/app/src

# Set working directory
WORKDIR /app

# Create a non-root user and group
RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --gid 1000 appuser

# Install system dependencies needed for the application or health checks
# curl is used for the health check.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install production Python dependencies
# Copy requirements file and install, utilizing the cache for speed.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy validated application code from the builder stage
COPY --from=builder --chown=appuser:appgroup /app/src ./src
COPY --from=builder --chown=appuser:appgroup /app/configs ./configs

# Switch to the non-root user
USER appuser

# Expose the port the app runs on
# This should match the port specified in configs/settings.yaml or the gunicorn bind parameter.
EXPOSE 5000

# Health check to ensure the application is responsive
# It attempts to connect to the /add endpoint. A successful connection (even with a 400 error) indicates the server is running.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -s http://localhost:5000/add > /dev/null || exit 1

# Command to run the application using a production-grade WSGI server
# The application object 'app' is located in the 'src/app.py' module.
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "src.app:app"]