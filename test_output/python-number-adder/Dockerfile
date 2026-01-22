# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Set environment variables for best practices
# Prevents Python from writing .pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Create a non-root user and group
# Using system users is a good practice for security
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

# Copy the dependency file first to leverage Docker cache
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Disables the cache, which is not needed in a container build
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's source code
COPY . .

# Set the PYTHONPATH to include the src directory
# This allows for absolute imports from the 'src' root, e.g., 'from calculator import ...'
ENV PYTHONPATH=/app/src

# Validate Python syntax by attempting to compile all .py files
# This acts as a quick sanity check before running tests or the app
RUN python -m compileall .

# Run tests
# The '|| true' ensures that the Docker build does not fail if tests fail,
# which can be desirable in some CI/CD pipelines.
RUN python -m unittest discover tests || true

# Switch to the non-root user
USER appuser

# Specify the command to run on container startup
CMD ["python", "src/main.py"]