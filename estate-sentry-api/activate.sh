#!/bin/bash
# Quick activation script for the virtual environment
# Usage: source activate.sh

if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
    echo "✅ Virtual environment activated (Windows)"
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated (Unix)"
else
    echo "❌ Virtual environment not found at .venv/"
    echo "Run: python -m venv .venv"
    exit 1
fi

echo "📦 Python: $(python --version)"
echo "📍 Location: $(which python)"
echo ""
echo "Ready to develop! Run:"
echo "  python manage.py runserver  - Start development server"
echo "  python manage.py test       - Run tests"
echo "  python manage.py --help     - See all commands"
