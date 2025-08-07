#!/bin/bash

# This script builds the Python project using uv.
# It creates a source distribution and a wheel.

# Exit immediately if a command exits with a non-zero status.
set -e

# The directory where this script is located.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

echo "Changing to project directory: $SCRIPT_DIR"
cd "$SCRIPT_DIR"

echo "Cleaning up old build artifacts..."
rm -rf dist

echo "Building the project with uv..."
uv build

echo "Build complete. The following packages have been created:"
ls -l dist
