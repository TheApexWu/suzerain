#!/bin/bash
#
# Suzerain Run Script
# Activates venv, loads .env, runs main.py
#
# Usage: ./scripts/run.sh [args...]
#

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check for virtual environment
VENV_DIR="$PROJECT_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at .venv"
    echo "Run: ./scripts/install.sh"
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Load .env file if it exists
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Change to project root for relative imports
cd "$PROJECT_ROOT/src"

# Run main.py with all passed arguments
exec python main.py "$@"
