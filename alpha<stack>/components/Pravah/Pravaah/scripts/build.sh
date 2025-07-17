#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
# -u: Treat unset variables as an error.
# -o pipefail: Return the exit status of the last command in a pipeline that failed.
set -euo pipefail

echo "Pravah Build Script"
echo "-------------------"

# Define project root relative to the script location.
# This script is at pravah/scripts/build.sh, so ../ moves to pravah/.
PROJECT_ROOT=$(dirname "$(realpath "$0")")/..
RUST_CORE_DIR="${PROJECT_ROOT}/pravah_core"
DOCKER_IMAGE_NAME="pravah"

# Determine the Docker image version tag.
# Prioritize GIT_TAG_VERSION environment variable (useful in CI/CD for release tags).
# Otherwise, use a short Git commit hash if in a Git repository.
# Fallback to 'latest' if not in a Git repository.
if [ -n "${GIT_TAG_VERSION:-}" ]; then
    VERSION_TAG="${GIT_TAG_VERSION}"
elif git -C "${PROJECT_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    VERSION_TAG=$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)
else
    VERSION_TAG="latest"
fi

IMAGE_TAG="${DOCKER_IMAGE_NAME}:${VERSION_TAG}"

echo "1. Building Rust core engine (pravah_core)..."
echo "   Navigating to: ${RUST_CORE_DIR}"
# Navigate to the Rust core directory and build the Python wheel in release mode.
# `maturin build --release` will output the .whl file to `pravah_core/target/wheels/`
# This path is relative to the project root, which Docker can access.
pushd "${RUST_CORE_DIR}" > /dev/null # Push current directory and change, suppress output
maturin build --release
popd > /dev/null # Pop back to original directory (PROJECT_ROOT/scripts), suppress output

echo "   Rust wheel built successfully at ${RUST_CORE_DIR}/target/wheels/"

echo "2. Building Docker image '${IMAGE_TAG}'..."
# Navigate to the project root to ensure the Docker build context includes all necessary files.
cd "${PROJECT_ROOT}"
# Build the Docker image. The Dockerfile will then be able to access the
# generated Rust wheel from `pravah_core/target/wheels/`.
docker build -t "${IMAGE_TAG}" .

echo "-----------------------------------"
echo "Pravah build completed successfully!"
echo "Docker image created: ${IMAGE_TAG}"
echo "You can run it using: docker run -p 8000:8000 ${IMAGE_TAG}"
echo "-----------------------------------"