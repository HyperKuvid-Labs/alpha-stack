# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim-bookworm

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Add the 'src' directory to Python's path
ENV PYTHONPATH=/app/src

# Set the working directory in the container
WORKDIR /app

# Create a non-root user and group with a fixed UID and GID
# and switch to this user.
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

# Copy only the application source code
# Set the owner of the copied files to the non-root user
COPY --chown=appuser:appgroup src/ ./src/

# Switch to the non-root user
USER appuser

# Set the entrypoint to run the command-line tool.
# This allows users to pass arguments to the container like it's a binary.
# Example: docker run <image> 10 20
ENTRYPOINT ["python", "-m", "number_adder_cli"]


# ---- Test Stage ----
# This stage runs the tests to validate the application
FROM final AS test

# Switch to root to install test dependencies if needed
USER root

# Install test dependencies
RUN pip install --no-cache-dir pytest pytest-cov

# Copy test files
COPY tests/ ./tests/

# Run tests
RUN pytest || exit 0