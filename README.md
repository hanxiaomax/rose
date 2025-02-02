# ROS Bag Filter Tool

A high-performance tool for filtering ROS bag files using a topic whitelist, built with C++ and exposed via pybind11.

## Features

- **Textual TUI Interface**:
  - Interactive file explorer
  - Topic selection with multi-select support
  - Task management with progress tracking
  - Real-time status updates

- **Command Line Interface**:
  - Bag file inspection
  - Topic filtering with whitelist
  - Performance measurement

## TUI Usage

1. **Start the TUI**:
```bash
./rose.py tui
```

2. **Main Interface**:
   - Left Panel: File explorer
   - Middle Panel: Topic selection
   - Right Panel: Task management
   - Bottom: Status bar

3. **Key Bindings**:
   - `q`: Quit the application
   - `f`: Toggle show only bag files
   - `w`: Load whitelist

4. **Filtering Process**:
   1. Select a bag file from the file explorer
   2. Choose topics to filter
   3. Set output file name
   4. Click "Add Task" to start filtering

5. **Task Management**:
   - Completed tasks are shown in the task table
   - Each task shows:
     - ID
     - Input bag file
     - Output bag file
     - Processing time

## Docker Usage

1. Build the Docker image:
```bash
docker build -t rose .
```

2. Run the container with directory mounting:
```bash
./run.sh
```

The container will:
- Mount current directory to /workspace
- Preserve all ROS and Python environment variables
- Provide an interactive terminal

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-repo/rose.git
cd rose
```

2. Build the project:
```bash
./build_rosecode.sh
```

3. Source the environment:
```bash
source env.sh
```

## Command Line Usage

### Basic Commands

1. **List topics in a bag file**:
```bash
./filter_rosbag.py input.bag --inspect
```

2. **Filter a bag file using whitelist**:
```bash
./filter_rosbag.py input.bag output.bag --whitelist path/to/whitelist.txt
```

### Whitelist Creation

1. Create a whitelist by inspecting your bag file:
```bash
./filter_rosbag.py input.bag --inspect
```

2. You can automatically generate a whitelist using grep and awk:
```bash
# Example: Create whitelist of all topics containing 'lidar'
./filter_rosbag.py input.bag --inspect | grep lidar | awk '{print $1}' > topic_whitelist.txt

# Example: Create whitelist of all topics except diagnostics
./filter_rosbag.py input.bag --inspect | grep -v diagnostics | awk '{print $1}' > topic_whitelist.txt
```

3. Copy the topics you want to keep into `src/rose_core/src/topic_whitelist.txt`

4. Edit the whitelist file:
- Keep one topic per line
- Remove topics you don't want to keep
- Lines starting with # are comments

Example whitelist:
```
# Auto-generated topic whitelist
/camera/image_raw
/imu/data
/odom
```

## Demo Bag

download from [webviz demo.bag](https://storage.googleapis.com/cruise-webviz-public/demo.bag)

## Whitelist Management

1. **Create Whitelist**:
```bash
mkdir -p whitelist
echo -e "/camera/image_raw\n/imu/data\n/odom" > whitelist/example.txt
```

2. **Add Whitelist to Config**:
Edit `config.json` to add your whitelist:
```json
{
    "whitelists": {
        "example": "whitelist/example.txt"
    }
}
```

3. **Use Whitelist in TUI**:
- Press `w` to load whitelist
- Select topics from the whitelist

```bash
./rose.py tui
```

