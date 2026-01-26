# syntax=docker/dockerfile:1

# ---- Base Stage ----
# Use an official Python runtime as a parent image.
# Using a specific slim version is good for production as it's smaller and has a reduced attack surface.
FROM python:3.11-slim-bookworm AS base

# Set environment variables to prevent Python from writing .pyc files to disc
# and to ensure output is sent straight to the terminal without buffering.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container.
WORKDIR /app

# ---- Builder Stage ----
# This stage installs dependencies and prepares the application.
FROM base AS builder

# Create a non-root user and group for security purposes.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy the dependency file first to leverage Docker's layer caching.
# This layer is only rebuilt when requirements.txt changes.
COPY requirements.txt .

# Install dependencies using a cache mount for faster subsequent builds.
# --no-cache-dir reduces the image size.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy the application source code into the container.
COPY ./src ./src

# Validate Python syntax by attempting to compile all .py files.
# This will fail the build if there are syntax errors.
RUN python -m compileall .

# ---- Final Stage ----
# This is the final, lean image that will be used to run the application.
FROM base AS final

# Copy the non-root user from the builder stage.
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group

# Copy the installed dependencies and application code from the builder stage.
COPY --from=builder /app /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Set the working directory.
WORKDIR /app

# Change the ownership of the application directory to the non-root user.
RUN chown -R appuser:appgroup /app

# Switch to the non-root user.
USER appuser

# Set the entrypoint to run the application.
# Arguments passed to `docker run` will be appended to this command.
# e.g., `docker run <image> 5 10` will execute `python src/main.py 5 10`
ENTRYPOINT ["python", "src/main.py"]