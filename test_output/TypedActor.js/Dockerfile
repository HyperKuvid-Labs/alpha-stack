# --- Base Stage ---
# Use the official Bun image. The slim version is smaller and good for production.
# Use a specific version for reproducibility.
FROM oven/bun:1.1.20-slim AS base
WORKDIR /usr/src/app

# --- Dependencies Stage ---
# This stage installs all dependencies (dev and prod) to be used by build and test stages.
# It leverages Docker layer caching. It only re-runs when package.json or bun.lockb changes.
FROM base AS deps
COPY package.json bun.lockb* ./
RUN bun install --frozen-lockfile

# --- Test Stage ---
# This stage runs the tests.
# Copying source code and using cached dependencies from the previous stage.
FROM deps AS test
COPY . .
# The requirement is to run tests but not fail the build if they fail.
RUN bun test || true

# --- Build Stage ---
# This stage builds the TypeScript source code into JavaScript.
FROM deps AS build
COPY . .
# Run the build script defined in package.json
RUN bun run build

# --- Production Stage ---
# This is the final, lean image for production.
FROM oven/bun:1.1.20-slim AS production
WORKDIR /usr/src/app

# Create a non-root user and group for security.
# The user's home directory will be created at /home/appuser.
RUN useradd -m -u 1000 appuser

# Copy dependency manifests and install ONLY production dependencies.
COPY package.json bun.lockb* ./
RUN bun install --production --frozen-lockfile

# Copy the compiled application code from the build stage.
COPY --from=build /usr/src/app/dist ./dist
# Copy package.json to allow `bun run` to work and for metadata purposes.
COPY package.json .

# Change ownership of the application files to the non-root user.
RUN chown -R appuser:appuser /usr/src/app

# Switch to the non-root user.
USER appuser

# Expose the port the application will listen on for cluster communication.
# This value is based on the .env.example file.
EXPOSE 7000

# Add a health check to verify the service is running and responsive.
# This attempts a TCP connection to the exposed port.
# Note: This requires the application to actively listen on this port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD bun exec -- bash -c 'exec 3<>/dev/tcp/localhost/7000' || exit 1

# Set the default command to run the application.
# This executes the compiled JavaScript output.
CMD ["bun", "run", "dist/index.js"]