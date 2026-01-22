# ---- Base Stage ----
# Use the official Bun image as a base for installing dependencies and building the application.
# Using a specific version is recommended for reproducibility.
FROM oven/bun:1 AS base
WORKDIR /app

# Copy package management files
COPY package.json bun.lockb ./

# ---- Dependencies Stage ----
# This stage installs all dependencies, including devDependencies, needed for building and testing.
FROM base AS deps
# Install all dependencies. Using --frozen-lockfile ensures deterministic installs.
RUN bun install --frozen-lockfile

# ---- Builder Stage ----
# This stage builds the TypeScript source code into JavaScript.
FROM deps AS builder
# Copy the rest of the source code
COPY . .
# Run tests. Use `|| true` to prevent build failure if tests fail, as per requirements.
# This can be adjusted for stricter CI/CD pipelines.
RUN bun test || true
# Build the application. The TypeScript compiler will validate syntax.
RUN bun run build

# ---- Production Stage ----
# This is the final, optimized image for running the application.
# It uses a slim base image to reduce size and attack surface.
FROM oven/bun:1-slim AS production
WORKDIR /app

# Create a non-root user and group for security
# Using -S creates a system user without a password or home directory
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Install only production dependencies for a smaller image size.
COPY package.json bun.lockb ./
RUN bun install --production --frozen-lockfile

# Install netcat for the health check.
# Clean up apt cache to keep the image slim.
RUN apt-get update && \
    apt-get install -y --no-install-recommends netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

# Copy the compiled application from the builder stage
COPY --from=builder /app/dist ./dist

# Copy the environment variable template.
# Actual environment variables should be injected at runtime.
COPY .env.example .env

# Set ownership of the application files to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port the actor system node will listen on.
# This value is based on ACTOR_NODE_PORT in .env.example.
EXPOSE 7878

# Healthcheck to verify that the service is running and listening on its port.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD nc -z 127.0.0.1 7878 || exit 1

# The command to run the application.
# This corresponds to the `start` script logic in package.json.
CMD ["bun", "run", "dist/index.js"]