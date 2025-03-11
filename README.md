# ROSE - Yet Another ROS Bag Filter Tool

A high-performance ROS bag filtering tool that allows you to extract specific topics from ROSv1 bag files. Built with C++ core and Python interface, it provides both command-line and TUI interfaces for efficient bag file processing.


>inspired by [rosbag_editor](https://github.com/facontidavide/rosbag_editor)


## Aesthetic 

> The cassette tape, a modest analog artifact, has evolved into a retro-futurism icon, demonstrating that technological advancement can coexist with human touch. Its tactile interface and physical limitations serve as poignant reminders of our technological heritage.

> 磁带盒不仅是一种技术遗物，更是复古未来主义的艺术品和精神图腾。简单的按钮、褪色的塑料外壳和有限的存储容量，既是怀旧的载体，也是对数字霸权的温柔反抗。它时刻提醒着我们：技术的突飞猛进不应该以牺牲人性为代价，克制的设计往往更能打动人心。

The TUI embraces the **cassette futurism** aesthetic - a design philosophy that reimagines future interfaces through the lens of 20th century technological fossils. This intentional retrofuturism features:

- **Nostalgic minimalism**: Low-resolution displays and monochromatic schemes that evoke 1980s computing
- **Tactile authenticity**: Visual metaphors of physical media like magnetic tapes and CRT textures
- **Humanized technology**: Warm color palettes and "imperfect" interfaces that resist digital sterility

More than mere retro styling, this approach serves as poetic resistance to digital hegemony. The cassette tape - our central metaphor - embodies this duality: 


![splash](splash.png)

## Key Features and Todos

- High-performance C++ processing core (Optional,ROS required)
- 🎉 ROS Environment independent. current rosbag and later to [rosbags](https://pypi.org/project/rosbags/)
- 🌟 Interactive TUI for easy operation
- 🌟 Command-line interface for automation
- Filter ROS bag files 
  - 🌟 with whitelists 
  - with manually selected topics
  - by time range (only TUI tested)
- 🌟 Fuzzy search topic in TUI
- 🌟 Multi-selection mode for batch processing in TUI (note:partially supported, rename and time range based filtering not supported yet) 
   - 🌟 parallel processing for Multi-selection mode
- Docker support for cross-platform usage
- 🌟 cassette futurism theme for dark and light mode
- 🚧 Message view in TUI
- 🚧 Support dynamic file/whitelist refresh in TUI

## Getting Started

### Installation

1. Install rose-bag from pypi
```bash
pip install rose-bag
```

2. Install from the source
```bash
# Clone the repository
git clone https://github.com/hanxiaomax/rose.git
cd rose

# Run the installation script
chmod +x install.sh
./install.sh
```

To uninstall Rose, run the following command:
```bash
pip uninstall rose-bag
```

### Terminal Setup

To ensure proper color display in your terminal, set the following environment variable:
```bash
# Add this to your bashrc or zshrc
export TERM=xterm-256color
```

No ROS bag file? No problem! Download [webviz demo.bag](https://storage.googleapis.com/cruise-webviz-public/demo.bag) and give it a try!

> [!NOTE]
> Want to try C++ Parser instead of [Python API(lib rosbag)](https://wiki.ros.org/rosbag/Code%20API#Python_API)?
> 
> Since Rose's C++ parser depends on [ROS Noetic](https://wiki.ros.org/noetic/Installation) environment, you need to install it first.
>
> Option 1: Install ROS Noetic (Ubuntu 20.04), refer to [ROS Noetic Installation](http://wiki.ros.org/noetic/Installation)
>
> Option 2: Use docker image
> 1. Build the Docker image:
>    ```bash
>    cd docker
>    docker build -t rose .
>    ```
> 2. Run the container:
>    ```bash
>    ./go_docker.sh
>    ```
> Once you have ros environment installed, you can build `rosbag_io_py` lib which is required by roseApp to operate.
> 1. Build the ROS project:
>    ```bash
>    cd ros
>    ./build.sh
>    ```
> 2. Set up environment which will make sure `rosbag_io_py` add to `PYTHONPATH`
>    ```bash
>    source setup.sh
>    ```
> **You are all set! Now you can use RoseApp to filter ROS bag files.**
>
> Note: Rose's C++ parser is very simple and not support ROS2. It is slightly faster than Python API(lib rosbag) (Refer to [benchmark](./benchmark/README.md)). But I am not sure if it is worth the effort to maintain it.




## Usage

> [!IMPORTANT]
> If you experience color display issues in your terminal, set the following environment variable:
> ```bash
> export TERM=xterm-256color
> ```
> This ensures proper color rendering in both CLI and TUI interfaces.

### Command Line Interface

Rose provides several command-line tools for bag file operations:


1. Analyze topics and create whitelist:
   ```bash
   # Show all topics in the bag file
   ./rose.py inspect input.bag

   # Filter topics by pattern and show
   ./rose.py inspect input.bag -p ".*gps.*"

   # Filter topics and save to whitelist
   ./rose.py inspect input.bag -p ".*sensor.*" -s sensor_whitelist.txt

   # Output in JSON format
   ./rose.py inspect input.bag --json
   ```

2. Filter bag file:
   ```bash
   # Filter using whitelist file
   ./rose.py filter input.bag output.bag -w whitelist.txt

   # Filter by specific topics
   ./rose.py filter input.bag output.bag --topics /topic1 --topics /topic2

   # Filter by time range
   ./rose.py filter input.bag output.bag -w whitelist.txt -t "23/01/01 00:00:00,23/01/01 00:10:00"

   # Dry run to preview changes
   ./rose.py filter input.bag output.bag -w whitelist.txt --dry-run
   ```

Common workflow example:
```bash
# 1. First inspect the bag file
./rose.py info demo.bag

# 2. Create a whitelist with GPS related topics
./rose.py inspect demo.bag -p ".*gps.*" -s gps_whitelist.txt

# 3. Filter the bag file using the whitelist
./rose.py filter demo.bag gps_only.bag -w gps_whitelist.txt
```

### TUI Interface

To launch the TUI:
```bash
python3 rose.py tui
```

2. Some key bindings:
   - `q`: to quit
   - `f`: to filter bag files
   - `w`: to load whitelist
   - `s`: to save whitelist
   - `a`: to toggle select all topics

#### Configuration

Rose is configured with `roseApp/config.json`.
```json
{
    "show_splash_screen": true,
    "theme": "cassette-walkman",
    "load_cpp_parser": false,
    "whitelists": {
        "demo": "./whitelists/demo.txt",
        "radar": "./whitelists/radar.txt",
        "invalid": "./whitelists/invalid.txt"
    }
}
```

- `show_splash_screen`: whether to show the splash screen, default is true
- `theme`: the theme of the TUI, default is `cassette-walkman`, check [Theme](#theme) for more details
- `load_cpp_parser`: whether to use C++ implementation for better performance, default is false
- `whitelists`: the whitelists of the TUI, default is empty, check [Whitelist](#whitelist) for more details

> [!NOTE]
> The `load_cpp_parser` option is set to false by default to improve startup time. Enable it only if you need better performance and have the C++ implementation properly installed.

#### Theme
RoseApp TUI provides two built-in themes: `cassette-walkman` (default light theme) and `cassette-dark`. You can configure the theme in two ways:

| cassette-walkman | cassette-dark |
|------------|-------------|
| ![Light Theme TUI](main-light.png) | ![Dark Theme TUI](main-dark.png) |

1. Modify `config.json` to specify your preferred theme:

```json
{
    "theme": "cassette-dark",
}
```
2. Switch Theme in TUI with command palette(the buttom in bottom right corner or keybinding ^p)


#### Whitelist

You can filter bag files with pre-configured whitelist. To select pre-configured whitelists, press `w` in TUI. But before that, you need to create your own whitelist.

You can create your own whitelist in 3 ways:

1. Create topic whitelist from command line:
   ```bash
   ./rose.py inspect input.bag | awk '{print $1}' > whitelist/example.txt
   ```

2. Create topic whitelist with your favorite text editor and save it to `whitelist/`:

3. Create topic in TUI by press `s` to save current selected topics as whitelist file to `whitelist/` directory:

After whitelist created, add it to `config.json` so RoseApp can find it:
```json
{
    "whitelists": {
        "demo": "./whitelists/demo.txt",
        "radar": "./whitelists/radar.txt",
        "invalid": "./whitelists/invalid.txt"
    }
}
```

## Development

### Run locally in docker

```bash
python roseApp/rose.py
```

### Publishing to PyPI

To publish a new version to PyPI:

1. Update version in `pyproject.toml`
2. Install required tools:
```bash
pip install keyring keyrings.alt
```

3. Configure PyPI credentials:
```bash
# Using environment variables
export HATCH_INDEX_USER=__token__
export HATCH_INDEX_AUTH=your_pypi_token

# Or using hatch config
hatch config set pypi.auth.username __token__
hatch config set pypi.auth.password your_pypi_token
```

4. Build and publish:
```bash
# Build the package
hatch build

# Publish to PyPI
hatch publish
```

### Project Structure
```
project_root/
├── ros/            # ROS C++ core
│   ├── CMakeLists.txt
│   ├── devel/      # ros development folder
│   ├── build/      # build folder
│   ├── src/        # source code folder
|   ├── setup.sh    # setup script
|   └── build_rosecode.sh # build script
├── roseApp/        # Python application
│   ├── rose.py     # main script
│   ├── themes/     
│   ├── components/ # components 
│   ├── core/       # data types and utils
|   |── tui.py      # main tui script
│   ├── whitelists/ # topic whitelist folder
│   ├── config.json # config file
│   └── style.tcss   # style sheet
├── docker/              # Docker support
│   └── Dockerfile
│   └── go_docker.sh
├── docs/         # documentation
├── requirements.txt # dependencies
├── README.md     
```

### Tech stack

- **[Textual](https://textual.textualize.io/)**: A Python framework for building sophisticated TUI (Text User Interface) applications. Used for creating the interactive terminal interface.
- **[Click](https://click.palletsprojects.com/)**: A Python package for creating beautiful command line interfaces in a composable way. Used for building the CLI interface.
- **[Rich](https://rich.readthedocs.io/)**: A Python library for rich text and beautiful formatting in the terminal. Used for enhancing the visual presentation of both CLI and TUI.
- **[Pybind11](https://pybind11.readthedocs.io/)**: A lightweight header-only library that exposes C++ types in Python and vice versa. Used for wrapping ROS C++ interfaces to Python.

### Rough ideas - data driven rendering

![1](docs/notes/sketch.png)



>[!TIP]
> Before you start with Textual, there are some docs worth reading:
>
> - [Textual devtools](https://textual.textualize.io/guide/devtools/) on how to use `textual run <your app> --dev` to go into dev mode and how to handle logs
> - [Design a layout](https://textual.textualize.io/how-to/design-a-layout/) 、[TextualCSS](https://textual.textualize.io/guide/CSS/) and [CSS Types](https://textual.textualize.io/css_types/) to understand how to design a layout and style your app with CSS. and more tips on [Styles](https://textual.textualize.io/guide/styles/) and its [reference](https://textual.textualize.io/styles/)
> - [Event and Messages](https://textual.textualize.io/guide/events/) are also important ideas to understand how Textual works so you can handle [actions](https://textual.textualize.io/guide/actions/)
> - Thanks to [Workers](https://textual.textualize.io/guide/workers/), asynchronous operations never been so easy. it can supppot asyncio or threads.



## Resources

- Demo bag file: [webviz demo.bag](https://storage.googleapis.com/cruise-webviz-public/demo.bag)
- [ROS Noetic Installation](http://wiki.ros.org/noetic/Installation)



