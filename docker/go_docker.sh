#!/bin/bash
CURRENT_DIR=$(dirname "$(pwd)")
docker run -it --rm \
    -v "$CURRENT_DIR":/workspace \
    -w /workspace \
    $(env | grep -E '^(ROS_|PYTHON)' | sed 's/^/-e /') \
    rose:latest
