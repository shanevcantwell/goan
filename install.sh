#!/bin/bash
#
# install.sh - Sets up the Python backend environment for the 'goan' server.
#
# This script performs the following actions:
# 1. Validates that Python 3 is installed.
# 2. Creates a virtual environment in the '.venv' directory at the project root.
# 3. Installs all required packages from 'server/requirements.txt'.
# 4. Creates a 'run.sh' script to easily start the FastAPI server.
#

# --- Configuration ---
set -e # Exit immediately if a command exits with a non-zero status.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="$SCRIPT_DIR/.venv"
SERVER_DIR="$SCRIPT_DIR/server"
REQUIREMENTS_FILE="$SERVER_DIR/requirements.txt"
RUNNER_SCRIPT="$SCRIPT_DIR/run.sh"

# --- Main Logic ---

echo "--- Goan Backend Setup ---"

# 1. Validate Python 3 installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not found. Please install Python 3 and ensure it's in your PATH." >&2
    exit 1
fi
echo "✅ Python 3 found."

# 2. Create/Recreate the virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "Found existing virtual environment. Recreating for a clean install..."
    rm -rf "$VENV_DIR"
fi
echo "Creating virtual environment at '$VENV_DIR'..."
python3 -m venv "$VENV_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to create the virtual environment." >&2
    exit 1
fi
echo "✅ Virtual environment created."

# 3. Install dependencies
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Error: 'requirements.txt' not found at '$REQUIREMENTS_FILE'." >&2
    exit 1
fi
echo "Installing dependencies from '$REQUIREMENTS_FILE'..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE"
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies." >&2
    exit 1
fi
echo "✅ Dependencies installed."

# 4. Create the runner script
echo "Creating server runner script at '$RUNNER_SCRIPT'..."
cat << EOF > "$RUNNER_SCRIPT"
#!/bin/bash
# This script starts the goan FastAPI server.
# It automatically activates the virtual environment.

# Get the directory of this script (the project root)
SCRIPT_DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="\$SCRIPT_DIR/.venv"

# Activate the virtual environment
source "\$VENV_DIR/bin/activate"

echo "Starting Goan FastAPI server on http://0.0.0.0:8000"
echo "Press CTRL+C to stop."

# Run the server from the project root
# Pass any additional arguments (like --reload) to uvicorn
uvicorn server.main_api:app --port 8000 --host 0.0.0.0 "\$@"
EOF

chmod +x "$RUNNER_SCRIPT"
echo "✅ Runner script 'run.sh' created."

echo ""
echo "--- Setup Complete ---"
echo "To start the server, run the following command from the project root:"
echo "  ./run.sh"
echo ""
