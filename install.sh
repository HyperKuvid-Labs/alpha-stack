#!/bin/bash

# AlphaStack Installation Script

echo "🚀 Installing AlphaStack..."

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo "❌ pip could not be found. Please install Python and pip first."
    exit 1
fi

# Install the package in editable mode (or regular mode)
echo "📦 Installing dependencies and package..."
pip install .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation complete!"
    echo "🎉 You can now run 'alphastack' in any terminal."
    echo ""
    echo "To enable the '/alphastack' shortcut, add the following to your shell config (.bashrc/.zshrc):"
    echo "alias /alphastack='alphastack'"
else
    echo "❌ Installation failed. Please check the errors above."
fi

