#!/bin/bash
CURRENT_DIR=$(dirname "$(pwd)")
docker run -it --rm \
    -v "$CURRENT_DIR":/workspace \
    -w /workspace \
    -e TERM=xterm-256color \
    $(env | grep -E '^(ROS_|PYTHON)' | sed 's/^/-e /') \
    rose:latest
