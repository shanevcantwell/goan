#!/bin/bash
#
# sync-reqs.sh - Syncs the virtual environment with requirements.txt using pip-tools.
#
set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="$SCRIPT_DIR/.venv"
SERVER_DIR="$SCRIPT_DIR/server"
REQUIREMENTS_FILE="$SERVER_DIR/requirements.txt"

echo "--- Syncing Python Environment ---"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at '$VENV_DIR'." >&2
    echo "Please run the install.sh script first." >&2
    exit 1
fi

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Error: '$REQUIREMENTS_FILE' not found." >&2
    echo "Please run the compile-reqs.sh script first." >&2
    exit 1
fi

# Activate venv and run pip-sync
source "$VENV_DIR/bin/activate"
echo "Syncing environment with '$REQUIREMENTS_FILE'..."
pip-sync "$REQUIREMENTS_FILE"

echo "✅ Environment is up to date."
