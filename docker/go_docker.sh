#!/bin/bash

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Run the Docker container
docker run -it --rm \
    -v "$PROJECT_DIR":/workspace \
    -w /workspace \
    -e TERM=xterm-256color \
    -e PYTHONPATH=/workspace \
    rose:latest
