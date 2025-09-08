#!/bin/bash
# This script starts the goan FastAPI server.
# It automatically activates the virtual environment.

# Get the directory of this script (the project root)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="$SCRIPT_DIR/.venv"

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

echo "Starting Goan FastAPI server on http://0.0.0.0:8000"
echo "Press CTRL+C to stop."

# Run the server from the project root
# Pass any additional arguments (like --reload) to uvicorn
uvicorn server.main_api:app --port 8000 --host 0.0.0.0 "$@"
