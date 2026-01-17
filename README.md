# ROSE - Yet Another ROS Bag Filter


![image](image.png)

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
- 🌟 Command-line interface for automation
- Filter ROS bag files 
  - 🌟 **Interactive Mode** (`-i`): Fuzzy search and multi-select topics for extraction
  - with topic selection (fuzzy matching supported via `--topic` in inspect)
  - with manually selected topics
  - by time range (available in extract command)
- 🌟 **Bag file compression support** - Reduce file sizes significantly
  - BZ2 compression (best compression ratio)
  - LZ4 compression (faster compression/decompression)
  - No compression (fastest processing)
- 🌟 **Advanced TUI Inspector**:
  - Full-featured terminal UI with Plotting and Data Tree
  - Real-time visualization with zoom/pan
  - Tabbed interface for Data and Plots
- 🌟 **Interactive Selection Widgets**:
  - **PathInput**: File picker with auto-completion and tree view (Ctrl+T to toggle)
  - **Question/MultiQuestion**: Single/multi-select widgets with fuzzy search
  - Keyboard navigation: Tab, Space, Enter, Arrow keys
- 🌟 Multi-file batch processing with parallel workers
- 🌟 Customizable cassette futurism theme via YAML configuration

## Documentation

For detailed information about the internal software design, please see the [Software Architecture](roseApp/docs/architecture.md) and [Detailed Design](roseApp/docs/design.md).

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

Rose provides a comprehensive set of CLI commands for ROS bag file operations.

```bash
# Show all available commands
rose --help

# Show help for specific command
rose <command> --help
```

### Available Commands

| Command    | Description                                     |
| ---------- | ----------------------------------------------- |
| `load`     | Load bag files into cache for faster operations |
| `extract`  | Extract specific topics from bag files          |
| `compress` | Compress bag files with different algorithms    |
| `inspect`  | Inspect bag file contents and statistics        |
| `list`     | List and manage cached bag files                |
| `config`   | Manage configuration                            |

### Load Command

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

# Build message index for deeper analysis (slower load)
rose load "*.bag" --build-index

# Preview what would be loaded
rose load "*.bag" --dry-run
```

### Extract Command

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

### Compress Command

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

### Inspect Command

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

# Force reload or load if missing
rose inspect demo.bag --load
rose inspect demo.bag --load --force
```

**Options:**
- `--topics, -t`: Filter specific topics
- `--show-fields`: Show field analysis for messages
- `--sort`: Sort topics by (name, count, frequency, size) [default: size]
- `--reverse`: Reverse sort order
- `--output, -o`: Save output to file
- `--load`: Load bag if not cached (quick mode)
- `--load-index`: Load bag with message index building
- `--force`: Force reload even if cached

### List Command (Cache Management)

List and manage cached bag metadata:

```bash
# Show all cached bags (Table view)
rose list

# Interactive management (TUI)
rose list -i

# Remove a specific bag from cache
rose list remove demo.bag

# Clear all cache
rose list clear
```

## Compression Support

Rose supports compression of bag files to significantly reduce file sizes. This is especially useful for storing and transferring large bag files.

### Available Compression Types

| Type   | Description     | Compression Ratio | Speed   | Use Case                              |
| ------ | --------------- | ----------------- | ------- | ------------------------------------- |
| `none` | No compression  | 0%                | Fastest | When processing speed is critical     |
| `bz2`  | BZ2 compression | ~80-90%           | Slower  | Best for long-term storage            |
| `lz4`  | LZ4 compression | ~60-70%           | Faster  | Good balance of speed and compression |

### Configuration

Rose uses a unified configuration system with automatic validation. The easiest way to configure Rose is via the interactive TUI:

![Configuration TUI](configuration.png)

```bash
# Launch interactive configuration manager
rose config
```

This interface lets you modify settings, toggle features, and switch themes with immediate visual feedback. Changes are validated and saved to `rose.config.yaml`.

**Example Configuration:**
```yaml
# Performance Settings
parallel_workers: 4
memory_limit_mb: 512

# Feature Toggles
enable_cache: true

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

## Theme System

Rose uses a simple YAML-based theme system to customize UI colors. By default, Rose uses an **orange cassette futurism** theme inspired by 1980s computing.

### Creating a Custom Theme

1. Copy the default theme file:
   ```bash
   cp rose.theme.default.yaml rose.theme.custom.yaml
   ```

2. Edit the colors in `rose.theme.custom.yaml`.

3. Update `rose.config.yaml` to use your theme:
   ```yaml
   theme_file: rose.theme.custom.yaml
   ```

## Development

### Run locally

```bash
python -m roseApp.rose --help
```

### Publishing to PyPI

To publish a new version to PyPI:

1. Update version in `pyproject.toml`
2. Install required tools: `pip install hatch`
3. Build and publish:
```bash
hatch build
hatch publish
```

### Project Structure
```
project_root/
├── roseApp/                # Python application
│   ├── rose.py             # Main entry script
│   ├── cli/                # CLI commands
│   │   ├── load.py         # Load command
│   │   ├── extract.py      # Extract command
│   │   ├── compress.py     # Compress command
│   │   ├── inspect.py      # Inspect command
│   │   ├── list.py         # List/Cache command
│   │   ├── config.py       # Config command
│   │   └── interactive.py  # Interactive mode helpers
│   ├── core/               # Core functionality
│   │   ├── parser.py       # Bag file reader (BagReader)
│   │   ├── writer.py       # Bag file writer (BagWriter)
│   │   ├── pipeline.py     # Command orchestration
│   │   ├── cache.py        # Caching system
│   │   ├── events.py       # Event system
│   │   ├── model.py        # Data models
│   │   ├── config.py       # Configuration management
│   │   └── output.py       # UI/Output
│   ├── tui/                # TUI applications
│   │   ├── inspect_app.py  # Bag inspector TUI
│   │   ├── config_app.py   # Configuration TUI
│   │   ├── list_app.py     # Cache management TUI
│   │   ├── theme.py        # Theme manager
│   │   ├── dialogs.py      # Modal dialogs
│   │   └── widgets/        # Custom TUI widgets
│   │       ├── question.py       # Single-select widget
│   │       ├── multi_question.py # Multi-select widget
│   │       └── path_search.py    # File picker widget
│   ├── tests/              # Test files
│   └── docs/               # Documentation
├── pyproject.toml          # Project metadata and dependencies
└── README.md               # Project documentation
```

### Tech stack

- **[Rich](https://rich.readthedocs.io/)**: For beautiful CLI output, tables, and progress indicators.
- **[Typer](https://typer.tiangolo.com/)**: For building the command-line interface.
- **[Textual](https://textual.textualize.io/)**: For building the TUI (Terminal User Interface) components.
- **[rosbags](https://pypi.org/project/rosbags/)**: High-performance pure Python library for reading/writing ROS bags.
- **[plotext](https://github.com/piccolomo/plotext)**: For terminal-based plotting in the inspector TUI.
- **[pandas](https://pandas.pydata.org/)**: For data manipulation and analysis.
