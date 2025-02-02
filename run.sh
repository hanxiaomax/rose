#!/bin/bash

# 获取当前目录绝对路径
CURRENT_DIR=$(pwd)

# 运行容器并挂载当前目录
docker run -it --rm \
    -v "$CURRENT_DIR":/workspace \
    -w /workspace \
    -e PYTHONPATH=devel/lib:$PYTHONPATH \
    $(env | grep -E '^(ROS_|PYTHON)' | sed 's/^/-e /') \
    rose:latest
