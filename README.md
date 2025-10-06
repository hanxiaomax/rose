# ROSE - Yet Another ROS Bag Filter Tool

A high-performance ROS bag filtering tool that allows you to extract specific topics from ROSv1 bag files. Built with Python and provides both command-line and interactive interfaces for efficient bag file processing.


>inspired by [rosbag_editor](https://github.com/facontidavide/rosbag_editor)


## Aesthetic 

> The cassette tape, a modest analog artifact, has evolved into a retro-futurism icon, demonstrating that technological advancement can coexist with human touch. Its tactile interface and physical limitations serve as poignant reminders of our technological heritage.

> 磁带盒不仅是一种技术遗物，更是复古未来主义的艺术品和精神图腾。简单的按钮、褪色的塑料外壳和有限的存储容量，既是怀旧的载体，也是对数字霸权的温柔反抗。它时刻提醒着我们：技术的突飞猛进不应该以牺牲人性为代价，克制的设计往往更能打动人心。

The interface embraces the **cassette futurism** aesthetic - a design philosophy that reimagines future interfaces through the lens of 20th century technological fossils. This intentional retrofuturism features:

- **Nostalgic minimalism**: Low-resolution displays and monochromatic schemes that evoke 1980s computing
- **Tactile authenticity**: Visual metaphors of physical media like magnetic tapes and CRT textures
- **Humanized technology**: Warm color palettes and "imperfect" interfaces that resist digital sterility

More than mere retro styling, this approach serves as poetic resistance to digital hegemony. The cassette tape - our central metaphor - embodies this duality: 



## Key Features

- 🎉 ROS Environment independent using [rosbags](https://pypi.org/project/rosbags/)
- 🌟 Interactive Environment with REPL-style interface
- 🌟 Command-line interface for automation
- 🌟 Tab completion and workspace management
- Filter ROS bag files 
  - 🌟 with topic selection (fuzzy matching supported)
  - with manually selected topics
  - by time range (available in extract command)
- 🌟 **Bag file compression support** - Reduce file sizes significantly
  - BZ2 compression (best compression ratio)
  - LZ4 compression (faster compression/decompression)
  - No compression (fastest processing)
- 🌟 Multi-file batch processing with parallel workers
- 🌟 Docker support for cross-platform usage
- 🌟 Customizable cassette futurism theme via YAML configuration
- 🌟 **Plugin System** - Extensible architecture for custom functionality
  - 🔌 Hot-loadable plugins with hook system
  - 📊 Data interface for safe bag data access
  - 🛠️ Custom CLI commands support
  - 📝 Multiple plugin templates (basic, data_processor, hook_example)

## Getting Started

### Installation

#### Option 1: Install from PyPI

```bash
pip install rose-bag
```

#### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/hanxiaomax/rose.git
cd rose

# Install dependencies
pip install -r requirements.txt
```

#### Option 3: Docker Installation

For cross-platform usage or isolated environments:

```bash
# Clone the repository
git clone https://github.com/hanxiaomax/rose.git
cd rose

# Build Docker image
./docker/build.sh

# Run Rose in Docker container
./docker/go_docker.sh
```

The Docker container includes:
- All required dependencies pre-installed
- ROS bag processing libraries (rosbags, rosbag)
- Interactive terminal with color support
- Volume mounting for accessing local bag files

**Docker Usage Examples:**

```bash
# After running ./docker/go_docker.sh, you're inside the container

# Process bag files in your mounted directory
rose load *.bag
rose inspect demo.bag
rose extract input.bag --topics gps imu

# Interactive mode
rose
```

To uninstall Rose, run:
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

## Usage

Rose provides multiple interfaces for different workflows:
- **Direct CLI**: Quick operations with direct commands
- **Interactive Mode**: REPL-style environment with tab completion and workspace management

### Command Line Interface

Rose offers a comprehensive set of CLI commands for ROS bag file operations:

```bash
# Show all available commands
rose --help

# Show help for specific command
rose <command> --help
```

#### Available Commands

| Command | Description |
|---------|-------------|
| `load` | Load bag files into cache for faster operations |
| `extract` | Extract specific topics from bag files |
| `compress` | Compress bag files with different algorithms |
| `inspect` | Inspect bag file contents and statistics |
| `data` | Data manipulation and export commands |
| `cache` | Cache management operations |
| `plugin` | Plugin system management |

#### Load Command

Load bag files into cache for faster subsequent operations:

```bash
# Load all bag files in current directory
rose load "*.bag"

# Load specific files
rose load bag1.bag bag2.bag

# Load with parallel processing
rose load "*.bag" --workers 4

# Force reload even if cached
rose load "*.bag" --force

# Build message index for data analysis
rose load "*.bag" --build-index

# Preview what would be loaded
rose load "*.bag" --dry-run
```

#### Extract Command

Extract specific topics from bag files:

```bash
# Extract from all bag files
rose extract "*.bag" --topics gps imu

# Extract from single file with output pattern
rose extract input.bag --topics /gps/fix -o "{input}_filtered.bag"

# Extract from multiple files, exclude topics
rose extract bag1.bag bag2.bag --topics tf --reverse

# Parallel extraction with compression
rose extract "*.bag" --topics gps --compression lz4 --workers 4

# Preview without extraction
rose extract "*.bag" --topics gps --dry-run
```

**Options:**
- `--topics`: Topics to keep (supports fuzzy matching, use multiple times)
- `--reverse`: Exclude specified topics instead of including them
- `--compression`: Compression type (none, bz2, lz4)
- `--output, -o`: Output pattern (use `{input}` for filename, `{timestamp}` for timestamp)
- `--workers, -w`: Number of parallel workers
- `--dry-run`: Preview without executing
- `--yes, -y`: Answer yes to all prompts
- `--interactive, -i`: Enter interactive mode

#### Compress Command

Compress bag files with different algorithms:

```bash
# Compress all bag files with LZ4
rose compress "*.bag" --compression lz4

# Compress single file with BZ2
rose compress input.bag --compression bz2 -o "{input}_{compression}.bag"

# Parallel compression
rose compress bag1.bag bag2.bag --compression lz4 --workers 4

# Preview compression
rose compress "*.bag" --compression bz2 --dry-run
```

**Options:**
- `--compression, -c`: Compression type (bz2, lz4) [default: lz4]
- `--output, -o`: Output pattern (use `{input}`, `{timestamp}`, `{compression}`)
- `--workers, -w`: Number of parallel workers
- `--validate`: Validate compressed files after compression
- `--dry-run`: Preview without compressing

#### Inspect Command

Inspect bag file contents and display comprehensive analysis:

```bash
# Inspect a bag file
rose inspect demo.bag

# Filter specific topics
rose inspect demo.bag --topics gps imu

# Show field analysis for messages
rose inspect demo.bag --show-fields

# Sort topics by different criteria
rose inspect demo.bag --sort frequency --reverse

# Save inspection results to file
rose inspect demo.bag -o report.txt
```

**Options:**
- `--topics, -t`: Filter specific topics
- `--show-fields`: Show field analysis for messages
- `--sort`: Sort topics by (name, count, frequency, size) [default: size]
- `--reverse`: Reverse sort order
- `--output, -o`: Save output to file

#### Cache Command

Manage cache data:

```bash
# Show cache status
rose cache

# Show detailed cache content
rose cache --content

# Export cache entries to file
rose cache export output.json

# Clear cache data
rose cache clear

# Clear cache for specific files
rose cache clear --bags bag1.bag bag2.bag
```

#### Data Command

Data manipulation and export:

```bash
# Show data information
rose data info demo.bag

# Export bag data to CSV
rose data export demo.bag --topics /gps/fix --output gps_data.csv

# Export with time filtering
rose data export demo.bag --topics imu --start-time 1.0 --end-time 10.0

# Merge multiple topics
rose data export demo.bag --topics gps imu --merge
```

#### Plugin Command

Plugin system management:

```bash
# List all available plugins
rose plugin list

# Show plugin information
rose plugin info my_plugin

# Create a new plugin
rose plugin create my_plugin --template basic

# Install plugin from file
rose plugin install /path/to/plugin.py

# Run plugin command
rose plugin run my_plugin hello

# Enable/disable plugins
rose plugin enable my_plugin
rose plugin disable my_plugin

# Reload plugin
rose plugin reload my_plugin
```

### Interactive Environment

Rose provides a powerful REPL-style interactive environment for bag file operations:

```bash
# Launch interactive mode (default when no command specified)
rose

# Or explicitly
rose --help  # Shows you can just run 'rose' for interactive mode
```

**Key Features:**
- **Automatic Workspace Status**: See working directory, configuration, cache, loaded bags, and selected topics at startup
- **Background Task Execution**: Long operations don't block the interface
- **Smart Auto-completion**: Tab completion for commands, files, and topics
- **Natural Language Queries**: Ask questions directly without commands
- **Session Management**: Context-aware commands that adapt to your current state

**Workspace Status Display:**

On startup, Rose displays comprehensive workspace information:

```
╭───────────────── Interactive Environment ─────────────────╮
│ Interactive Environment                                   │
│                                                           │
│ Workspace Status:                                         │
│   Working Directory: /workspaces/rose                     │
│   Configuration: rose.config.yaml                         │
│   Cache: 3 entries, 2.5 MB                                │
│   Loaded Bags: 2 bag(s)                                   │
│   Selected Topics: 5 topic(s)                             │
│                                                           │
│ Available commands:                                       │
│   /load      - Load bag files                             │
│   /extract   - Extract topics from bags                   │
│   /inspect   - Inspect bag contents                       │
│   ...                                                     │
╰───────────────────────────────────────────────────────────╯
```

**Interactive Commands:**

| Command | Description |
|---------|-------------|
| `/load [files]` | Load bag files with glob pattern support |
| `/extract` | Extract topics with interactive selection |
| `/compress` | Compress bag files interactively |
| `/inspect` | Inspect bag contents and statistics |
| `/bags` | Manage loaded bags in workspace |
| `/topics` | Manage topic selection |
| `/cache` | Cache management operations |
| `/data` | Data export and analysis |
| `/plugin` | Plugin management |
| `/configuration` | Edit configuration file |
| `/help` | Show comprehensive help |
| `/clear` | Clear console screen |
| `/exit` or `/quit` | Exit interactive mode |

**Workflow Example:**

```bash
# Start Rose
rose

# Load bag files
> /load *.bag

# Inspect a specific bag
> /inspect demo.bag

# Extract topics
> /extract
# (Interactive prompts guide you through selection)

# Check cache status
> /cache

# Exit
> /exit
```

See [Interactive Help](roseApp/interactive/help.md) for detailed documentation.

### Plugin System

Rose features a powerful plugin system for extending functionality. See [Plugin System](#plugin-command) section above for command-line usage.

**Plugin Features:**
- 🔌 **Hot-loadable plugins**: Load and reload plugins without restarting
- 🎣 **Hook system**: Execute custom logic before/after Rose operations
- 📊 **Data interface**: Safe access to bag data and DataFrames
- 🛠️ **Custom CLI commands**: Plugins can provide their own commands
- 📝 **Multiple templates**: Basic, data processor, and hook examples

**Plugin Templates:**
- `basic` - Simple plugin with CLI commands
- `data_processor` - Advanced data analysis and processing
- `hook_example` - Demonstrates hook system usage

**Quick Start:**

```bash
# Create a new plugin
rose plugin create my_analyzer --template data_processor

# List available plugins
rose plugin list

# Enable/disable plugins
rose plugin enable my_analyzer
rose plugin disable my_analyzer

# Run plugin
rose plugin run my_analyzer process demo.bag
```

See [Plugin Documentation](docs/PLUGIN_README.md) for detailed guides and examples.

## Compression Support

Rose supports compression of bag files to significantly reduce file sizes. This is especially useful for storing and transferring large bag files.

### Available Compression Types

| Type | Description | Compression Ratio | Speed | Use Case |
|------|-------------|------------------|-------|----------|
| `none` | No compression | 0% | Fastest | When processing speed is critical |
| `bz2` | BZ2 compression | ~80-90% | Slower | Best for long-term storage |
| `lz4` | LZ4 compression | ~60-70% | Faster | Good balance of speed and compression |

**Example compression results:**
- Original bag file: 696.15 MB
- After BZ2 compression: 92.03 MB  
- **Compression ratio: 86.8%**

### Using Compression

**Via CLI:**

```bash
# Compress bag files directly
rose compress "*.bag" --compression lz4

# Extract with compression
rose extract input.bag --topics gps --compression bz2

# Compress multiple files in parallel
rose compress *.bag --compression lz4 --workers 4
```

**Via Interactive Mode:**

```bash
rose

> /compress
# (Interactive prompts guide you through compression)

> /extract
# (Option to compress during extraction)
```

**Programmatic Usage:**

```python
from roseApp.core.BagManager import BagManager
from roseApp.core.parser import create_parser, ParserType
from pathlib import Path

# Create parser and bag manager
parser = create_parser(ParserType.PYTHON)
bag_manager = BagManager(parser)

# Load bag and select topics
bag_manager.load_bag(Path("input.bag"))
bag_manager.select_topic("/your_topic")

# Get filter configuration with desired compression
bag = bag_manager.get_single_bag()
config = bag.get_filter_config(compression="bz2")  # or "none", "lz4"

# Filter with specified compression
bag_manager.filter_bag(Path("input.bag"), config, Path("output.bag"))
```

> **Note**: LZ4 compression requires additional system dependencies. If LZ4 is not available, BZ2 compression will be used as fallback.

#### Configuration

Rose uses a unified configuration system with automatic validation. Configuration is loaded from `rose.config.yaml` in your project directory.

**Quick Start:**
```bash
# Copy example configuration
cp rose.config.yaml.example rose.config.yaml

# Edit configuration
nano rose.config.yaml
```

**Example Configuration:**
```yaml
# Performance Settings
parallel_workers: 4
memory_limit_mb: 512

# Feature Toggles
enable_cache: true
enable_plugins: true

# Default Behavior
compression_default: none
verbose_default: false
build_index_default: false

# Logging Settings
log_level: INFO
log_to_file: true

# UI Settings
theme_file: rose.theme.default.yaml
enable_colors: true

# Directory Settings
output_directory: output
```

**Configuration Hierarchy:**
1. Command-line arguments (highest priority)
2. Environment variables (`ROSE_*` prefix)
3. Configuration file (`rose.config.yaml`)
4. System defaults (lowest priority)

**Environment Variable Override:**
```bash
# Override parallel workers
export ROSE_PARALLEL_WORKERS=8

# Change log level
export ROSE_LOG_LEVEL=DEBUG

# Run Rose
rose load demo.bag
```

**Automatic Validation:**

Rose validates configuration on startup and displays warnings for potential issues:

```
Config: rose.config.yaml
Warning: Workers (32) > CPU count (8)
Warning: Theme file not found: custom-theme.yaml
```

See [Configuration Guide](docs/CONFIGURATION.md) for complete reference.

## Theme System

Rose uses a simple YAML-based theme system to customize UI colors. By default, Rose uses an **orange cassette futurism** theme inspired by 1980s computing.

### Creating a Custom Theme

**Quick Start:**

1. Copy the default theme file:
   ```bash
   cp rose.theme.default.yaml rose.theme.custom.yaml
   ```

2. Edit the colors in `rose.theme.custom.yaml`:
   ```yaml
   # Primary colors
   primary: blue
   accent: cyan
   
   # Status colors
   success: green
   warning: yellow
   error: red
   info: cyan
   
   # UI colors
   muted: grey50
   highlight: white
   path: cyan
   ```

3. Update `rose.config.yaml` to use your theme:
   ```yaml
   theme_file: rose.theme.custom.yaml
   ```

That's it! Run any Rose command to see your new theme.

### Available Color Names

You can use standard terminal color names:
- Basic: `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`
- Bright: `bright_red`, `bright_green`, `bright_cyan`, etc.
- Grey: `grey0` to `grey100`
- RGB: `rgb(255,128,0)` or `#ff8000`

### Terminal Color Support

If colors don't display correctly, ensure your terminal supports 256 colors:

```bash
# Add to your .bashrc or .zshrc
export TERM=xterm-256color
```

### Tips

- Keep your theme file in the same directory as `rose.config.yaml` for easy portability
- Use the default theme as a reference when creating custom themes
- Test your theme in different lighting conditions for better readability


## Working with Topics

### Topic Selection Methods

Rose provides flexible ways to select topics for extraction:

**1. Direct Topic Specification:**
```bash
# Specify exact topic names
rose extract demo.bag --topics /gps/fix /imu/data

# Use partial matching (fuzzy search)
rose extract demo.bag --topics gps imu
```

**2. Interactive Selection:**
```bash
# Use interactive mode for guided selection
rose extract demo.bag --interactive

# Or in interactive environment
rose
> /extract
```

**3. Reverse Selection (Exclude Topics):**
```bash
# Extract all topics except specified ones
rose extract demo.bag --topics tf --reverse
```

### Topic Whitelists

You can create reusable topic lists for repeated operations:

**1. Create a whitelist file:**
```bash
# Create a text file with one topic per line
cat > my_topics.txt << EOF
/gps/fix
/imu/data
/camera/image_raw
EOF
```

**2. Use the whitelist:**
```bash
# Load topics from file using shell redirection
rose extract demo.bag --topics $(cat my_topics.txt | xargs)
```

**3. Save selected topics:**

In interactive mode, after selecting topics for operations, you can document your workflow for future reference.

## Development

### Run locally

```bash
python -m roseApp.rose --help
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
├── roseApp/                # Python application
│   ├── rose.py             # Main entry script
│   ├── cli/                # CLI commands
│   │   ├── load.py         # Load command implementation
│   │   ├── extract.py      # Extract command implementation
│   │   ├── compress.py     # Compress command implementation
│   │   ├── inspect.py      # Inspect command implementation
│   │   ├── data.py         # Data manipulation commands
│   │   ├── cache.py        # Cache management commands
│   │   └── plugin.py       # Plugin management commands
│   ├── interactive/        # Interactive Environment
│   │   ├── core/           # Interactive core components
│   │   ├── commands/       # Interactive command handlers
│   │   └── components/     # UI components and utilities
│   ├── core/               # Core functionality
│   │   ├── parser.py       # Bag file parser
│   │   ├── BagManager.py   # Bag management
│   │   ├── config.py       # Configuration system
│   │   ├── cache.py        # Caching system
│   │   ├── errors.py       # Error handling
│   │   └── plugins/        # Plugin system
│   ├── ui/                 # UI components
│   │   ├── theme.py        # Theme system
│   │   └── *.py            # UI utilities
│   └── tests/              # Test files
├── docker/                 # Docker support
│   ├── Dockerfile          # Docker image definition
│   ├── build.sh            # Build script
│   └── go_docker.sh        # Run script
├── docs/                   # Documentation
├── pyproject.toml          # Project metadata and dependencies
├── requirements.txt        # Development dependencies
└── README.md               # Project documentation
```

### Tech stack

- **[Rich](https://rich.readthedocs.io/)**: A Python library for rich text and beautiful formatting in the terminal. Used for enhancing the visual presentation in CLI and interactive interfaces.
- **[InquirerPy](https://github.com/kazhala/InquirerPy)**: A Python library for building interactive command line interfaces with elegant prompts. Used for the interactive CLI.
- **[Typer](https://typer.tiangolo.com/)**: A Python library for building CLI applications. Used for building the command-line interface.
- **[rosbags](https://pypi.org/project/rosbags/)**: A pure Python library for reading and writing ROS bag files. Used for ROS bag file processing without ROS dependencies.
- **[Textual](https://textual.textualize.io/)**: Used for rich text display in help documentation and UI components.

### Development Notes

![1](docs/notes/sketch.png)

>[!TIP]
> Rose uses Rich and Textual for enhanced terminal output and help documentation:
>
> - **Rich** provides beautiful formatting for CLI output, tables, and progress indicators
> - **Textual** is used for rich text display in help documentation and interactive components
> - **InquirerPy** powers the interactive prompts and menu systems
> - All UI components follow the cassette futurism aesthetic with consistent theming

## Resources

- Demo bag file: [webviz demo.bag](https://storage.googleapis.com/cruise-webviz-public/demo.bag)



