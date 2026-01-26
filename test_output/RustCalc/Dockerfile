# Build Stage
FROM rust:1.83-alpine AS builder

# Install build dependencies for native linking on Alpine
RUN apk add --no-cache musl-dev

WORKDIR /app

# Copy Cargo Manifest
COPY Cargo.toml ./

# Copy Source Code
COPY src ./src

# Build the release binary with BuildKit cache mounts for registry and target
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release

# Runtime Stage
FROM alpine:latest

# Create a non-root user with UID 1000
RUN addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser

# Copy the binary from the builder stage
COPY --from=builder /app/target/release/rustcalc /usr/local/bin/rustcalc

# Set ownership of the binary to the non-root user
RUN chown appuser:appuser /usr/local/bin/rustcalc

# Switch to the non-root user
USER appuser

# Set the entrypoint for the application
ENTRYPOINT ["rustcalc"]