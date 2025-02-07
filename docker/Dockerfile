# Use ROS Noetic base image
FROM ros:noetic-ros-core

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8

# Setup ROS repository
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

RUN sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list' \
    && curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | apt-key add -

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    python3-pip \
    pybind11-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install ROS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-noetic-rosbag \
    ros-noetic-rosbag-storage \
    ros-noetic-roscpp \
    ros-noetic-tf2-msgs \
    ros-noetic-tf \
    python3-rosdep \
    python3-rospy \
    && rm -rf /var/lib/apt/lists/*

# Initialize rosdep
RUN rosdep init && rosdep update

# Install Python dependencies
RUN pip install --no-cache-dir \
    pybind11 \
    textual \
    textual-dev \
    rich \
    pytest \
    pytest-asyncio \
    typing-extensions \
    click \
    art

RUN pip install --extra-index-url https://rospypi.github.io/simple rosbag

# Create workspace directory
WORKDIR /workspace

# Set mount point
VOLUME /workspace

# Set default command
CMD ["bash"]
