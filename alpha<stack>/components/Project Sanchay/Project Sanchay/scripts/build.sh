```bash
#!/bin/bash
set -euo pipefail # Exit on error, treat unset variables as error, pipefail

# --- Configuration Variables ---
APP_NAME="Sanchay"
# Determine the project root directory dynamically
# This script is in scripts/, so go up two levels
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

VENV_DIR="${PROJECT_ROOT}/.venv"
RUST_CRATE_DIR="${PROJECT_ROOT}/crates/sanchay_core"
PYTHON_APP_SOURCE_DIR="${PROJECT_ROOT}/src/sanchay_app"
BUILD_DIR="${PROJECT_ROOT}/build"
DIST_DIR="${PROJECT_ROOT}/dist"
APP_ICON="${PROJECT_ROOT}/assets/icons/app_icon.png"

# Use 'python3' as default, but allow override if needed (e.g., 'python' on some systems)
PYTHON_EXECUTABLE="python3"

# --- Utility Functions ---

log_info() {
    echo "INFO: $1"
}

log_warning() {
    echo "WARNING: $1" >&2
}

log_error() {
    echo "ERROR: $1" >&2
    exit 1
}

# --- Prerequisites Check ---
check_prerequisites() {
    log_info "Checking build prerequisites..."

    command -v "${PYTHON_EXECUTABLE}" >/dev/null || log_error "${PYTHON_EXECUTABLE} not found. Please install Python 3.10+."
    command -v "rustup" >/dev/null || log_error "rustup not found. Please install Rust via rustup.rs."
    command -v "cargo" >/dev/null || log_error "cargo not found. It should be installed with rustup."
    command -v "pip" >/dev/null || log_error "pip not found. Please install pip."

    # Check for maturin specifically, as it's a Python package
    if ! "${PYTHON_EXECUTABLE}" -m pip show maturin &>/dev/null; then
        log_error "maturin not found. Please install it with '${PYTHON_EXECUTABLE} -m pip install maturin'."
    fi

    log_info "All build prerequisites met."
}

# --- Cleanup Previous Builds ---
clean_artifacts() {
    log_info "Cleaning previous build artifacts..."
    rm -rf "${BUILD_DIR}" || true
    rm -rf "${DIST_DIR}" || true
    # Maturin/Cargo build artifacts within the project root's target directory
    rm -rf "${PROJECT_ROOT}/target" || true
    # Maturin cache/state directory
    rm -rf "${PROJECT_ROOT}/.maturin" || true
    # Python bytecode caches
    find "${PROJECT_ROOT}" -type d -name "__pycache__" -exec rm -rf {} +
    log_info "Cleanup complete."
}

# --- Python Virtual Environment Setup ---
setup_virtual_env() {
    log_info "Setting up Python virtual environment at ${VENV_DIR}..."
    if [ ! -d "${VENV_DIR}" ]; then
        "${PYTHON_EXECUTABLE}" -m venv "${VENV_DIR}" || log_error "Failed to create virtual environment."
    fi

    # Activate the virtual environment
    # Note: 'source' command is shell-specific, use '.' for POSIX compatibility
    . "${VENV_DIR}/bin/activate" || log_error "Failed to activate virtual environment."
    log_info "Virtual environment activated: ${VIRTUAL_ENV}"

    # Ensure pip and setuptools are up-to-date within the venv
    pip install --upgrade pip setuptools wheel || log_error "Failed to update pip/setuptools."
    log_info "pip and setuptools updated in virtual environment."
}

# --- Build and Install the Python package (with Rust core) ---
build_and_install_package() {
    log_info "Building the '${APP_NAME}' Python package (including Rust core) using Maturin..."

    # Change to project root because pyproject.toml is located there
    # Pushd/popd manage directory stack
    pushd "${PROJECT_ROOT}" > /dev/null || log_error "Failed to change to project root: ${PROJECT_ROOT}"

    # Maturin builds the 'sanchay' wheel which includes the compiled Rust core
    # --release for optimized build, --strip for smaller binaries, --locked to use Cargo.lock
    maturin build --release --strip --locked || log_error "Maturin build failed."
    log_info "Maturin build completed successfully. Looking for generated wheel."

    # Find the generated wheel file in the target/wheels directory
    SANCHAY_WHEEL=$(find "${PROJECT_ROOT}/target/wheels/" -name "${APP_NAME}-*.whl" -print -quit)
    if [ -z "${SANCHAY_WHEEL}" ]; then
        log_error "Failed to find the '${APP_NAME}' wheel file after maturin build. Check target/wheels/."
    fi
    log_info "Found ${APP_NAME} wheel: ${SANCHAY_WHEEL}"

    # Install the generated wheel into the virtual environment
    pip install "${SANCHAY_WHEEL}" || log_error "Failed to install ${APP_NAME} wheel."
    log_info "${APP_NAME} package (with Rust core) installed in virtual environment."

    # Install PyInstaller and PySide6-rcc (needed for Qt resource handling)
    pip install pyinstaller pyside6-rcc || log_error "Failed to install PyInstaller or pyside6-rcc."
    log_info "PyInstaller and PySide6-rcc installed in virtual environment."

    popd > /dev/null || log_warning "Failed to return to original directory."
}

# --- Bundle Application with PyInstaller ---
bundle_application() {
    log_info "Bundling application into a standalone executable using PyInstaller..."

    # Create PyInstaller's working directories
    mkdir -p "${BUILD_DIR}/pyinstaller_work"
    mkdir -p "${BUILD_DIR}/pyinstaller_spec"

    # PyInstaller command to create a one-file, windowed (GUI) executable
    # --add-data handles including extra files/directories: "<source>:<destination_in_bundle>"
    pyinstaller \
        --noconfirm \
        --onefile \
        --windowed \
        --name "${APP_NAME}" \
        --icon "${APP_ICON}" \
        --distpath "${DIST_DIR}" \
        --workpath "${BUILD_DIR}/pyinstaller_work" \
        --specpath "${BUILD_DIR}/pyinstaller_spec" \
        --add-data "${PROJECT_ROOT}/assets:assets" \
        --add-data "${PROJECT_ROOT}/config:config" \
        --hidden-import "sanchay_core" \
        "${PYTHON_APP_SOURCE_DIR}/__main__.py"

    if [ $? -ne 0 ]; then
        log_error "PyInstaller bundling failed. Check the PyInstaller logs in ${BUILD_DIR}/pyinstaller_spec."
    fi

    log_info "Application bundled successfully! Executable available at: ${DIST_DIR}/${APP_NAME}"
    log_info "Depending on your OS, the executable might be named ${APP_NAME}.exe (Windows) or just ${APP_NAME} (Linux/macOS)."
}

# --- Main Script Execution Flow ---
main() {
    log_info "--- Starting Project Sanchay Build Process ---"

    check_prerequisites
    clean_artifacts
    setup_virtual_env
    build_and_install_package
    bundle_application

    # Deactivate the virtual environment
    if [ -n "${VIRTUAL_ENV}" ]; then
        deactivate
        log_info "Virtual environment deactivated."
    fi

    log_info "--- Project Sanchay Build Process Finished Successfully ---"
}

# Execute the main function
main "$@"
```