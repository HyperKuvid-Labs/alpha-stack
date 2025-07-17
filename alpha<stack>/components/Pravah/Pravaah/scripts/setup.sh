```bash
#!/bin/bash
set -euo pipefail

echo "Pravah: High-Performance File & Data Processing Engine Development Environment Setup"
echo "--------------------------------------------------------------------------------"

# --- Configuration ---
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_MIN_VERSION="3.11"

# Colors for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# --- Helper Functions ---
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# --- 1. Navigate to Project Root ---
log_info "Navigating to project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT" || log_error "Failed to navigate to project root."

# --- 2. Check and Install Python ---
log_info "Checking Python ($PYTHON_MIN_VERSION+) installation..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is required but not found. Please install Python $PYTHON_MIN_VERSION+ from python.org or your system's package manager."
fi

CURRENT_PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
# Use 'bc -l' for floating point comparison
if (( $(echo "$CURRENT_PYTHON_VERSION < $PYTHON_MIN_VERSION" | bc -l) )); then
    log_error "Python version $CURRENT_PYTHON_VERSION detected. Python $PYTHON_MIN_VERSION+ is required. Please update your Python installation."
fi
log_info "Python $CURRENT_PYTHON_VERSION found."

# --- 3. Check and Install Rust Toolchain ---
log_info "Checking Rust toolchain installation..."
if ! command -v rustup &> /dev/null; then
    log_warn "Rustup (Rust toolchain installer) not found. Installing Rust toolchain. This may take a few minutes..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y || log_error "Failed to install Rustup."
    # Source cargo env vars for the current shell session
    # This ensures subsequent `cargo` or `rustup` commands work in this script
    source "$HOME/.cargo/env" || log_error "Failed to source Cargo environment variables. Please restart your terminal or manually source '$HOME/.cargo/env'."
    log_info "Rustup installed."
fi

log_info "Updating Rust toolchain to stable..."
rustup update stable || log_error "Failed to update Rust toolchain."

log_info "Installing rustfmt and clippy components (if not already present)..."
# Suppress output for component additions, they might already be there
rustup component add rustfmt clippy --toolchain stable &> /dev/null || log_warn "Could not add rustfmt/clippy components. This is usually fine if they are already installed."

# --- 4. Check and Install Poetry ---
log_info "Checking Poetry installation..."
if ! command -v poetry &> /dev/null; then
    log_warn "Poetry (Python package manager) not found. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 - || log_error "Failed to install Poetry."
    # Ensure Poetry's executable path is added to PATH for the current script session
    # This is often $HOME/.local/bin or similar for user-installed Python packages
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        export PATH="$HOME/.local/bin:$PATH"
    fi
    log_info "Poetry installed."
fi

# --- 5. Install Python Dependencies (including Rust core via Poetry) ---
log_info "Installing Python dependencies defined in pyproject.toml..."
log_info "This will also build and link the Rust core engine (pravah_core) using Maturin."
# Poetry automatically handles local path dependencies (like 'pravah_core')
# and uses the appropriate build backend (Maturin, if specified as a dev dependency in pyproject.toml)
poetry install || log_error "Failed to install Python dependencies or build Rust core. Check pyproject.toml and Rust compilation errors."

# --- 6. Set up Pre-commit Hooks ---
log_info "Setting up pre-commit hooks..."
# Install pre-commit into the Poetry environment if it's not already there
poetry run pip install pre-commit &> /dev/null || log_warn "Could not install pre-commit (might be already present)."
poetry run pre-commit install || log_error "Failed to install pre-commit hooks. Ensure .pre-commit-config.yaml is valid."
log_info "Pre-commit hooks installed."

# --- 7. Prepare Local Configuration File (.env) ---
log_info "Preparing local configuration file (.env)..."
if [ ! -f ".env" ]; then
    cp ".env.example" ".env" || log_error "Failed to copy .env.example to .env."
    log_warn "Created a new '.env' file from '.env.example'."
    log_warn "Please review and update '.env' with your local settings (e.g., DATABASE_URL, S3 credentials)."
else
    log_info "'.env' file already exists. Skipping creation."
fi

# --- 8. Final Instructions ---
echo "--------------------------------------------------------------------------------"
log_info "Pravah development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the Python virtual environment: ${YELLOW}poetry shell${NC}"
echo "2. If prompted, review and update your local configuration in the ${YELLOW}.env${NC} file."
echo "3. You can now run the application:"
echo "   - Web API: ${YELLOW}poetry run uvicorn app.main:app --reload${NC}"
echo "   - CLI:     ${YELLOW}poetry run python app/cli.py${NC}"
echo "--------------------------------------------------------------------------------"
```