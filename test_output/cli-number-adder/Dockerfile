# syntax=docker/dockerfile:1

# Use an official Python runtime as a parent image
# Using a slim version to keep the image size down
FROM python:3.11-slim-bookworm

# Set environment variables to prevent generating .pyc files and to run in unbuffered mode
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Create a non-root user and group
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy the dependency file first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies using a cache mount to speed up subsequent builds
# Although requirements.txt is empty, this is a good practice for future development
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-cache-dir -r requirements.txt

# Copy the application source code into the container
COPY number_adder/ ./number_adder/

# Validate Python syntax
RUN python -m compileall .

# Change the ownership of the application files to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Set the entrypoint to run the application
# This allows passing command-line arguments directly to `docker run`
ENTRYPOINT ["python", "-m", "number_adder"]