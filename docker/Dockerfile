# Use Python base image
FROM python:3.9-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    textual>=0.40.0 \
    textual-dev \
    rich>=13.0.0 \
    pytest \
    pytest-asyncio \
    typing-extensions \
    art \
    matplotlib>=3.5.0 \
    typer>=0.9.0 \
    InquirerPy \
    numpy \
    pycryptodomex \
    rosbags>=0.9.16 \
    pydantic>=2.0.0 \
    click>=8.0.0 \
    plotly>=5.0.0 \
    pandas>=1.3.0 

# Install rosbag Python package
RUN pip install --no-cache-dir --extra-index-url https://rospypi.github.io/simple/ \
    rosbag 

# Create workspace directory
WORKDIR /workspace

# Set mount point
VOLUME /workspace

# Set default command
CMD ["bash"]
