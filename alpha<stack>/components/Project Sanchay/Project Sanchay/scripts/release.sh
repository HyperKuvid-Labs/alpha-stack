#!/bin/bash
#
# Project Sanchay Release Script
#
# This script automates the process of creating a new software release for Project Sanchay.
# It handles versioning, building the Rust core, packaging the Python application with PyInstaller,
# and creating distributable archives for the current platform.
#
# This script is intended to be run by the CI/CD pipeline on dedicated runners
# for Linux, macOS, and Windows to produce platform-specific binaries.

set -euo pipefail # Exit immediately if a command exits with a non-zero status.
                   # Exit if an unset variable is used.
                   # The return value of a pipeline is the value of the last command to exit with a non-zero status.

# --- Configuration ---
APP_NAME="sanchay"
REPO_ROOT="$(git rev-parse --show-toplevel)"
BUILD_DIR="$REPO_ROOT/build"
DIST_DIR="$REPO_ROOT/dist"
VENV_DIR="$REPO_ROOT/.venv_release" # Isolated venv for release process

# Determine the operating system and architecture
OS="$(uname -s)"
ARCH="$(uname -m)"

# PyInstaller specific options for GUI apps
PYINSTALLER_OPTS=()
case "$OS" in
    Linux*)
        TARGET_OS="linux"
        ;;
    Darwin*)
        TARGET_OS="macos"
        PYINSTALLER_OPTS+=("--windowed") # For macOS GUI apps, creates .app bundle
        ;;
    MINGW*|CYGWIN*|MSYS*)
        TARGET_OS="windows"
        PYINSTALLER_OPTS+=("--windowed") # For Windows GUI apps
        ;;
    *)
        echo "Error: Unsupported OS for release build: $OS"
        exit 1
        ;;
esac

# --- Functions ---

# Function to display messages
log() {
    echo "--- $APP_NAME Release: $1 ---"
}

# Function to clean previous build artifacts and virtual environment
clean_build() {
    log "Cleaning previous build artifacts and virtual environment..."
    rm -rf "$BUILD_DIR" "$DIST_DIR" "$VENV_DIR"
    mkdir -p "$BUILD_DIR" "$DIST_DIR"
}

# Function to get the project version from pyproject.toml
get_version() {
    # Extract version using grep and sed, assuming format 'version = "X.Y.Z"'
    VERSION=$(grep -E '^version\s*=' "$REPO_ROOT/pyproject.toml" | head -n 1 | sed -E 's/version\s*=\s*"([^"]+)".*/\1/')
    if [ -z "$VERSION" ]; then
        echo "Error: Could not determine version from pyproject.toml. Ensure 'version = \"X.Y.Z\"' is present in the [project] section."
        exit 1
    fi
    echo "$VERSION"
}

# --- Main Script ---

cd "$REPO_ROOT"

clean_build

VERSION=$(get_version)
log "Starting release build for version: $VERSION ($TARGET_OS-$ARCH)"

# 1. Setup Python Virtual Environment
log "Setting up isolated Python virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install build tools and project dependencies
log "Installing build tools (maturin, pyinstaller) and project dependencies..."
pip install --upgrade pip setuptools wheel
pip install maturin pyinstaller

# Install the main 'sanchay' project from the root `pyproject.toml`.
# This step is crucial:
# - Due to `build-backend = "maturin"` in `pyproject.toml`, `pip install .` will invoke `maturin`.
# - For maturin to find `crates/sanchay_core/Cargo.toml`, the root `pyproject.toml` *must* have:
#   `[tool.maturin]`
#   `manifest-path = "crates/sanchay_core/Cargo.toml"`
#   `module-name = "sanchay_core"`
# - This command will build the Rust extension (`sanchay_core`) in release mode and install it.
# - It will also install the Python package `sanchay` (which includes code from `src/sanchay_app`) and its declared dependencies (e.g., PySide6).
pip install --no-cache-dir --verbose "$REPO_ROOT"

# 2. Package the Python application with PyInstaller
log "Packaging application with PyInstaller..."

# Determine the correct icon path for PyInstaller
ICON_PATH="$REPO_ROOT/assets/icons/app_icon.png" # Default for Linux/generic
case "$OS" in
    Darwin*)
        if [ -f "$REPO_ROOT/assets/icons/app_icon.icns" ]; then
            ICON_PATH="$REPO_ROOT/assets/icons/app_icon.icns"
        fi
        ;;
    MINGW*|CYGWIN*|MSYS*)
        if [ -f "$REPO_ROOT/assets/icons/app_icon.ico" ]; then
            ICON_PATH="$REPO_ROOT/assets/icons/app_icon.ico"
        fi
        ;;
esac

# PyInstaller command:
# --name: Sets the name of the executable (and its containing folder for --onedir)
# --distpath: Where to put the bundled app
# --workpath: Where PyInstaller puts its temporary files
# --specpath: Where to put the .spec file
# --onedir: Creates a directory containing the executable and all its dependencies (recommended for PySide6)
# --add-data: Includes additional files/directories. Format: "source:destination" (destination is relative to bundled app root)
# --icon: Specifies the application icon
# --hidden-import: Ensures modules not automatically detected (like native extensions) are included
pyinstaller \
    --name "$APP_NAME-$VERSION-$TARGET_OS-$ARCH" \
    --distpath "$BUILD_DIR/pyinstaller_dist" \
    --workpath "$BUILD_DIR/pyinstaller_work" \
    --specpath "$BUILD_DIR/pyinstaller_spec" \
    --onedir \
    "${PYINSTALLER_OPTS[@]}" \
    --add-data "$REPO_ROOT/assets:assets" \
    --add-data "$REPO_ROOT/config:config" \
    --icon "$ICON_PATH" \
    --hidden-import "sanchay_core" \
    "$REPO_ROOT/src/sanchay_app/__main__.py"

RELEASE_BUNDLE_DIR="$BUILD_DIR/pyinstaller_dist/$APP_NAME-$VERSION-$TARGET_OS-$ARCH"

if [ ! -d "$RELEASE_BUNDLE_DIR" ]; then
    echo "Error: PyInstaller output directory not found at $RELEASE_BUNDLE_DIR after packaging."
    exit 1
fi

# 3. Create distributable archives
log "Creating distributable archives..."
FINAL_ARCHIVE_NAME="$APP_NAME-$VERSION-$TARGET_OS-$ARCH"

# Change to the directory where PyInstaller placed the bundle to ensure correct archive structure
cd "$BUILD_DIR/pyinstaller_dist"

case "$OS" in
    Linux*)
        # On Linux, typically a tar.gz archive of the directory
        tar -czvf "$DIST_DIR/$FINAL_ARCHIVE_NAME.tar.gz" "./$FINAL_ARCHIVE_NAME"
        ;;
    Darwin*)
        # On macOS, PyInstaller with --windowed --onedir creates an .app bundle.
        # We zip this .app bundle.
        zip -r "$DIST_DIR/$FINAL_ARCHIVE_NAME.zip" "./$FINAL_ARCHIVE_NAME"
        ;;
    MINGW*|CYGWIN*|MSYS*)
        # On Windows, PyInstaller creates a folder. We zip this folder.
        # This assumes 'zip' command is available (common on CI runners).
        zip -r "$DIST_DIR/$FINAL_ARCHIVE_NAME.zip" "./$FINAL_ARCHIVE_NAME"
        ;;
esac

cd "$REPO_ROOT" # Go back to original repository root

log "Release build completed successfully!"
log "Packaged application created at: $RELEASE_BUNDLE_DIR"
log "Distributable archives created in: $DIST_DIR"
find "$DIST_DIR" -type f -name "$FINAL_ARCHIVE_NAME.*"

# Deactivate virtual environment
deactivate
log "Virtual environment deactivated and cleaned."