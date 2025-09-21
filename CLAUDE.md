# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ROSE is a high-performance ROS bag filtering tool with distinctive cassette futurism aesthetic. It provides CLI, interactive CLI, and TUI interfaces for filtering ROS v1 bag files without ROS environment dependencies, using the `rosbags` library.

## Architecture

### Core Components
- **Entry Point**: `roseApp/rose.py:app` - Main Typer CLI dispatcher with subcommands
- **Core Engine**: `roseApp/core/` - Bag file parsing, filtering, and compression logic
- **CLI Tools**: `roseApp/cli/` - Command-line utilities and interactive interfaces  
- **TUI Interface**: `roseApp/tui/` - Textual-based terminal UI with retro styling
- **Plugin System**: `roseApp/core/plugins/` - Extensible plugin architecture with hooks and scripts

### Key Classes
- **BagManager** (`roseApp/core/BagManager.py`) - Central orchestrator for bag operations
- **Parser** (`roseApp/core/parser.py`) - ROS bag file parsing using rosbags
- **ExportManager** (`roseApp/core/export_manager.py`) - Handles filtered bag output and format exports
- **CacheManager** (`roseApp/core/cache.py`) - Persistent caching for parsed bag metadata
- **PluginManager** (`roseApp/core/plugins/manager.py`) - Plugin loading and execution
- **TUIApp** (`roseApp/tui/tui.py`) - Main TUI application with theme management

### Data Flow Architecture
- **Parser** → **BagManager** → **ExportManager**: Bag files are parsed into metadata, filtered by topics/time, then exported with optional compression
- **Cache System**: `roseApp/core/cache.py` provides persistent caching for parsed bag metadata to accelerate repeated operations
- **Plugin System**: Hot-loadable plugins with hook system for extending functionality
- **Theme System**: Multiple themes including cassette futurism and Claude-inspired themes

## Development Commands

### Setup & Installation
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install locally for development
pip install -e .

# Alternative: use install script
./install.sh

# Verify installation
rose --help
```

### Testing
```bash
# Run all tests using pytest
pytest roseApp/tests/ -v

# Run tests with coverage
pytest --cov=roseApp --cov-report=html roseApp/tests/

# Run specific test module
pytest roseApp/tests/test_bag_manager.py -v

# Run single test method
pytest roseApp/tests/test_bag_manager.py::TestBagManager::test_load_bag -v

# Run bash integration tests
cd tests/bash_tests && ./run_all_tests.sh

# Run individual bash tests
cd tests/bash_tests && ./test_inspect.sh

# Run example test demos
python example/test_parser_cache_demo.py
```

### Development Workflow
```bash
# Install in development mode
pip install -e .

# Run TUI in dev mode (with hot reload)
textual run --dev roseApp.tui.tui:app

# CLI commands for testing
rose tui                    # Launch TUI
rose cli                    # Interactive CLI mode
rose filter input.bag output.bag -w whitelist.txt

# Inspect bag contents
rose inspect topics input.bag
rose inspect info input.bag

# Plugin management
rose plugin list            # List available plugins
rose plugin create my_plugin --template basic

# Build package
hatch build

# Publish to PyPI
hatch publish

# Run basic syntax check
python -m py_compile roseApp/**/*.py
```

### Docker Development
```bash
# Build Docker image
docker build -t rose-bag .

# Run with Docker
docker run -it --rm -v $(pwd):/data rose-bag rose tui

# Development with Docker
docker run -it --rm -v $(pwd):/data -v $(pwd)/roseApp/tests:/data/roseApp/tests rose-bag bash
```

## Interface Modes

### 1. TUI Mode (`rose tui`)
- Cassette futurism themes (`cassette-walkman`, `cassette-dark`)
- Claude-inspired themes (`claude-dark`, `claude-light`, `claude-midnight`, `claude-high-contrast`)
- Fuzzy topic search with real-time filtering
- Multi-selection batch processing with parallel execution
- Whitelist management (load/save)
- Compression options (BZ2, LZ4, none)

### 2. Interactive CLI (`rose cli`)
- Menu-driven interface with InquirerPy
- Guided workflows for filtering and whitelist management
- Batch processing capabilities
- Progress indicators and detailed results

### 3. Direct CLI Commands
- `rose filter` - Filter bags with topics/whitelists and compression options
- `rose inspect` - Analyze bag contents and metadata
- `rose extract` - Extract specific data to various formats
- `rose cache` - Manage parser cache
- `rose plugin` - Plugin management and execution
- `rose data` - Data analysis and visualization commands

## Configuration

### TUI Configuration
File: `roseApp/tui/config.json`
```json
{
    "show_splash_screen": true,
    "theme": "cassette-walkman",
    "whitelists": {
        "demo": "./whitelists/demo.txt"
    }
}
```

### Environment Setup
```bash
# Ensure proper terminal colors
export TERM=xterm-256color

# For development debugging
export ROSE_DEBUG=1
export ROSE_LOG_LEVEL=DEBUG
```

## Key Features

### Compression Support
- **BZ2**: Best compression (~80-90% reduction)
- **LZ4**: Balanced speed/compression (~60-70% reduction)  
- **None**: Fastest processing, no compression

### Filtering Capabilities
- Topic-based filtering via whitelists or manual selection
- Time range filtering (TUI only)
- Parallel processing for batch operations
- Dry-run mode for previewing operations
- Multiple output formats via ExportManager (JSON, YAML, CSV, XML, HTML, Markdown)

### Plugin System
- **Hot-loadable plugins**: Load and reload without restarting
- **Hook system**: Execute custom logic before/after Rose operations
- **Data interface**: Safe access to bag data and DataFrames
- **Custom CLI commands**: Plugins can provide their own commands
- **Multiple templates**: Basic, data_processor, and hook examples

## Testing Structure

### Test Organization
- **Unit tests**: `roseApp/tests/test_*.py`
- **Integration tests**: Marked with `@pytest.mark.integration`
- **Slow tests**: Marked with `@pytest.mark.slow`
- **Test data**: Sample bag files in `roseApp/tests/`
- **Bash tests**: Integration tests in `tests/bash_tests/`

### Test Commands
```bash
# Run specific test categories
python -m pytest roseApp/tests/ -k "test_parser" -v
python -m pytest roseApp/tests/ -m "integration" -v
python -m pytest roseApp/tests/ -m "slow" -v

# Run with specific Python path
PYTHONPATH=. python -m pytest roseApp/tests/ -v

# Run tests with specific log level
ROSE_LOG_LEVEL=DEBUG python -m pytest roseApp/tests/ -v
```

## Deployment

### PyPI Release
```bash
# Update version in pyproject.toml
hatch build
hatch publish

# Test build locally
hatch build && pip install dist/*.whl
```

### Docker Support
```bash
# Build optimized Docker image
docker build -t rose-bag .

# Run with volume mounting
docker run -it --rm -v $(pwd)/data:/data rose-bag rose tui

# Development with source code mounting
docker run -it --rm -v $(pwd):/app -w /app python:3.11 bash
```

## Dependencies

### Core Dependencies
- **rosbags**: ROS bag file processing (no ROS required)
- **textual**: TUI framework
- **typer**: CLI framework
- **rich**: Terminal formatting
- **pydantic**: Data validation
- **InquirerPy**: Interactive CLI prompts

### Optional Dependencies
- **lz4**: LZ4 compression support
- **matplotlib/plotly**: Visualization features
- **pandas**: Data analysis and DataFrame support
- **yaml**: YAML export support

## Build Configuration
- Uses hatchling build system with pyproject.toml
- Tests and development files excluded from wheel
- Supports Python 3.8+
- Includes TCSS files and JSON configs in package

## Advanced Features

### Cache System
- **Persistent caching**: Parsed bag metadata cached in `~/.cache/rose/`
- **Automatic invalidation**: Cache invalidates when bag files are modified
- **Performance optimization**: Dramatically reduces repeated parse operations

### Theme System
- **cassette-walkman**: Light theme with retro styling
- **cassette-dark**: Dark theme variant
- **claude-dark**: Claude-inspired dark theme with signature purple/blue colors
- **claude-light**: Claude-inspired light theme
- **claude-midnight**: High-contrast midnight theme
- **claude-high-contrast**: Accessibility-focused high contrast theme

### Whitelist Management
- **Format**: Text files with one topic per line
- **Location**: `whitelists/` directory
- **Integration**: Reference in `roseApp/tui/config.json` for TUI access
- **CLI management**: Create, view, and manage via interactive CLI

## Development Tips

### Debugging
```bash
# Enable debug logging
export ROSE_DEBUG=1
export ROSE_LOG_LEVEL=DEBUG

# Run with debug output
rose --help --verbose

# Check cache directory
ls ~/.cache/rose/
```

### Performance Testing
```bash
# Test with large bag files
time rose filter large.bag filtered.bag -w whitelist.txt

# Test cache performance
rm ~/.cache/rose/* && time rose inspect info test.bag
```

### Plugin Development
```bash
# Create new plugin
rose plugin create my_analyzer --template data_processor

# Test plugin
rose plugin run my_analyzer process --help

# Install plugin from file
rose plugin install plugins/my_custom_plugin.py
```