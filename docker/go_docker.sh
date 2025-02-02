#!/bin/bash
CURRENT_DIR=$(dirname "$(pwd)")
docker run -it --rm \
    -v "$CURRENT_DIR":/workspace \
    -w /workspace \
    -p 127.0.0.1:8000:8000 \
    $(env | grep -E '^(ROS_|PYTHON)' | sed 's/^/-e /') \
    rose:latest
