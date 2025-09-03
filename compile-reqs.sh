#!/bin/bash
#
# compile-reqs.sh - Compiles requirements.in to requirements.txt using pip-tools.
#
set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="$SCRIPT_DIR/.venv"
SERVER_DIR="$SCRIPT_DIR/server"

echo "--- Compiling Python Requirements ---"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at '$VENV_DIR'." >&2
    echo "Please run the install.sh script first." >&2
    exit 1
fi

# Activate venv and run pip-compile
source "$VENV_DIR/bin/activate"
echo "Compiling '$SERVER_DIR/requirements.in' -> '$SERVER_DIR/requirements.txt'..."
pip-compile "$SERVER_DIR/requirements.in" --output-file="$SERVER_DIR/requirements.txt"

echo "✅ Compilation complete."
