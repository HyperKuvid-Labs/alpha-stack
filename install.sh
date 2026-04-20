#!/bin/bash

# AlphaStack Installation Script
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUI_GO_DIR="$REPO_ROOT/tui-go"
BIN_DIR="$REPO_ROOT/bin"
TUI_BIN="$BIN_DIR/alphastack-tui"
INSTALL_BIN_DIR="${ALPHASTACK_INSTALL_BIN_DIR:-$HOME/.local/bin}"

echo " Installing AlphaStack..."

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo " pip could not be found. Please install Python and pip first."
    exit 1
fi

# Check if go is installed (required for the Bubbletea TUI)
if ! command -v go &> /dev/null; then
    echo ""
    echo " Go is required to build the AlphaStack TUI but was not found."
    echo " Install Go (>= 1.22) from one of:"
    echo "   - mise:   mise use -g go@latest"
    echo "   - asdf:   asdf plugin add golang && asdf install golang latest"
    echo "   - apt:    sudo apt install golang-go"
    echo "   - brew:   brew install go"
    echo "   - manual: https://go.dev/dl/"
    echo ""
    echo " Re-run install.sh after Go is on your PATH."
    exit 1
fi

GO_VERSION="$(go version | awk '{print $3}')"
echo " Found ${GO_VERSION}."

# Bump project version before install
echo " Bumping project version..."
python3 scripts/bump_version.py --part patch
if [ $? -ne 0 ]; then
    echo " Version bump failed. Aborting install."
    exit 1
fi

# Install the python package (editable so runtime imports track the source
# tree — prevents stale shadowed copies in site-packages).
echo " Installing dependencies and python package..."
pip install -e .
if [ $? -ne 0 ]; then
    echo " Python package install failed."
    exit 1
fi

# Build the Bubbletea TUI binary
echo " Building Bubbletea TUI (Go)..."
mkdir -p "$BIN_DIR"
(
    cd "$TUI_GO_DIR"
    go build -trimpath -ldflags "-s -w" -o "$TUI_BIN" ./cmd/alphastack-tui
)
if [ ! -x "$TUI_BIN" ]; then
    echo " Failed to build $TUI_BIN."
    exit 1
fi
echo " Built $TUI_BIN."

# Install the TUI binary into a directory on PATH so the python launcher can
# find it via shutil.which("alphastack-tui").
mkdir -p "$INSTALL_BIN_DIR"
cp "$TUI_BIN" "$INSTALL_BIN_DIR/alphastack-tui"
chmod +x "$INSTALL_BIN_DIR/alphastack-tui"
echo " Installed alphastack-tui to $INSTALL_BIN_DIR."

case ":$PATH:" in
    *":$INSTALL_BIN_DIR:"*) ;;
    *)
        echo ""
        echo " NOTE: $INSTALL_BIN_DIR is not on your PATH."
        echo "       Add this line to your shell config (.bashrc/.zshrc):"
        echo "         export PATH=\"$INSTALL_BIN_DIR:\$PATH\""
        ;;
esac

echo ""
echo " Installation complete!"
echo " Run 'alphastack' in any terminal — the Bubbletea TUI launches by default."
echo " To force the legacy Rich TUI, set ALPHASTACK_NO_GO_TUI=1."
echo ""
echo " To enable the '/alphastack' shortcut, add to your shell config:"
echo "   alias /alphastack='alphastack'"
