# ---- Base Stage ----
# Use a slim, official Python image for a smaller footprint.
FROM python:3.11-slim-bookworm

# Set recommended environment variables for running Python in a container.
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files.
# PYTHONUNBUFFERED: Ensures that Python output is sent straight to the terminal without being buffered.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory for the application.
WORKDIR /app

# Create a non-root user and group to run the application for security reasons.
# Using a static GID/UID makes access management easier.
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

# The project's requirements.txt only contains 'pytest', which is a development
# dependency. For a production-ready image, we should not install test tools.
# The application has no external runtime dependencies.

# Copy the application source code into the container.
# The --chown flag sets the owner of the copied files to the created appuser.
COPY --chown=appuser:appgroup src ./src

# As a sanity check, compile the Python code to ensure syntax is valid.
# The bytecode is not stored due to PYTHONDONTWRITEBYTECODE=1.
RUN python -m compileall ./src

# Switch to the non-root user.
USER appuser

# Set the entrypoint to execute the main script.
# The container will run this command by default when it starts.
# Command-line arguments can be appended to `docker run`.
ENTRYPOINT ["python", "src/main.py"]