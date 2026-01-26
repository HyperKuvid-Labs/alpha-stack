# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim-bookworm

# Set environment variables for best practices
# 1. PYTHONUNBUFFERED: Prevents Python from buffering stdout and stderr, ensuring logs are sent straight to the terminal.
# 2. PYTHONPATH: Adds the 'src' directory to the Python module search path, allowing direct imports from the 'number_adder_cli' package.
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Create a non-root user and group for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Set the working directory in the container
WORKDIR /app

# Copy the dependency file first to leverage Docker layer caching.
# This step is only re-run if requirements.txt changes.
COPY requirements.txt .

# Install dependencies
# Using --no-cache-dir reduces the image size.
# The BuildKit cache mount speeds up subsequent builds.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy the application source code into the container
COPY src/ ./src/

# Verify syntax and pre-compile Python modules to bytecode.
# This can provide a minor startup performance improvement and acts as a basic check.
RUN python -m compileall .

# Change the ownership of the application directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Define the command to run the application.
# This allows passing command-line arguments directly to `docker run`.
# Example: docker run <image_name> 10 20
ENTRYPOINT ["python", "-m", "number_adder_cli.main"]