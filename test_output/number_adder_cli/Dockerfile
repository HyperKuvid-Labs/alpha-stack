# Use a slim, official Python image to keep the final image size small.
# Pinning the version ensures build reproducibility.
FROM python:3.11-slim-bullseye

# - PYTHONUNBUFFERED: Prevents Python from buffering stdout/stderr, ensuring logs are visible in real-time.
# - PYTHONPATH: Adds the 'src' directory to Python's module search path to handle the src layout.
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"

# Set the working directory for subsequent commands.
WORKDIR /app

# Running as a non-root user is a security best practice.
RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --ingroup appgroup appuser

# Copy only the requirements file first to leverage Docker's layer caching.
# This layer is only rebuilt if requirements.txt changes.
COPY requirements.txt .

# Use a BuildKit cache mount to speed up subsequent builds by caching downloaded packages.
# Install dependencies as root before switching to the non-root user.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy the application source code into the container.
COPY src/ ./src/

# Pre-compile python files to .pyc to catch syntax errors during the build.
RUN python -m compileall -q src/

# Change the ownership of the application directory to the non-root user.
RUN chown -R appuser:appgroup /app

# Switch to the non-root user for running the application.
USER appuser

# Define the command to run the application.
# 'python -m number_adder_cli' executes the __main__.py file within the package.
# Command-line arguments for the application should be appended to the 'docker run' command.
ENTRYPOINT ["python", "-m", "number_adder_cli"]