#!/bin/bash

# AlphaStack Installation Script

echo " Installing AlphaStack..."

if ! command -v python3 &> /dev/null; then
    echo " python3 could not be found. Please install Python 3 first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo " pip could not be found. Please install Python and pip first."
    exit 1
fi

# Bump project version before install
echo " Bumping project version..."
python3 scripts/bump_version.py --part patch

if [ $? -ne 0 ]; then
    echo " Version bump failed. Aborting install."
    exit 1
fi

# Install the package in editable mode (or regular mode)
echo " Installing dependencies and package..."
python3 -m pip install .

if [ $? -eq 0 ]; then
    echo ""
    echo "Installation complete!"
    echo "You can now run 'alphastack' in any terminal."
    echo ""
    echo "Run Claude-style terminal UI + backend with one command:"
    echo "  alphastack terminal"
    echo ""
    if command -v bun &> /dev/null || command -v npm &> /dev/null || command -v pnpm &> /dev/null; then
        echo "Detected a JS package manager. 'alphastack terminal' can auto-install website dependencies if needed."
    else
        echo "Note: install bun, npm, or pnpm to use 'alphastack terminal'."
    fi
    echo ""
    echo "Optional aliases for shell config (.bashrc/.zshrc):"
    echo "alias ast='alphastack'"
    echo "alias ast-terminal='alphastack terminal'"
else
    echo "Installation failed. Please check the errors above."
fi

