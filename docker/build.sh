#!/bin/bash

# Exit on error
set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building Rose Docker image..."
docker build -t rose:latest "$SCRIPT_DIR"

echo "Docker image built successfully!"
echo "Run './docker/go_docker.sh' to start the container." 