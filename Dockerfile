# 使用ROS Noetic基础镜像
FROM ros:noetic-ros-core

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3-dev \
    python3-pip \
    pybind11-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装ROS依赖
RUN apt-get update && apt-get install -y \
    ros-noetic-rosbag \
    ros-noetic-rosbag-storage \
    ros-noetic-roscpp \
    ros-noetic-tf2-msgs \
    ros-noetic-tf \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip install pybind11 textual click textual-dev art rich-pixels

# 创建工作目录
WORKDIR /workspace

# 设置挂载点
VOLUME /workspace

# 设置默认命令
CMD ["bash"]
