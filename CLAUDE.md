# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ROSE is a high-performance ROS bag filtering tool with distinctive cassette futurism aesthetic. It provides CLI, interactive CLI, and TUI interfaces for filtering ROS v1 bag files without ROS environment dependencies, using the `rosbags` library.

## Architecture

### Core Components
- **Entry Point**: `roseApp/rose.py:app` - Main Typer CLI dispatcher with subcommands
- **Core Engine**: `roseApp/core/` - Bag file parsing, filtering, and compression logic
- **CLI Tools**: `roseApp/cli/` - Command-line utilities (load, extract, compress, inspect, data, cache, plugin)
- **Interactive CLI**: `roseApp/interactive/` - Guided CLI operations with command routing
- **TUI Interface**: `roseApp/ui/` - Textual-based terminal UI with retro styling
- **Plugin System**: `roseApp/core/plugins/` - Extensible plugin architecture with hooks and scripts

### Key Classes
- **BagManager** (`roseApp/core/BagManager.py`) - Central orchestrator for bag operations
- **Parser** (`roseApp/core/parser.py`) - ROS bag file parsing using rosbags
- **ExportManager** (`roseApp/core/export_manager.py`) - Handles filtered bag output and format exports
- **CacheManager** (`roseApp/core/cache.py`) - Persistent caching for parsed bag metadata
- **PluginManager** (`roseApp/core/plugins/manager.py`) - Plugin loading and execution
- **ThemeLoader** (`roseApp/ui/theme.py`) - Theme management for UI components

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
# Run bash integration tests (primary testing method)
cd tests/bash_tests && ./run_all_tests.sh

# Run individual bash tests
cd tests/bash_tests && ./test_inspect.sh
cd tests/bash_tests && ./test_load.sh
cd tests/bash_tests && ./test_extract.sh
cd tests/bash_tests && ./test_compress.sh
cd tests/bash_tests && ./test_data.sh
cd tests/bash_tests && ./test_cache.sh
cd tests/bash_tests && ./test_plugin.sh

# Run example test demos
python example/test_parser_cache_demo.py

# Quick test script
cd tests/bash_tests && ./quick_test.sh
```

### Development Workflow
```bash
# Install in development mode
pip install -e .

# Alternative: use install script for full setup
./install.sh

# CLI commands for testing
rose --help                 # Show all commands
rose load *.bag            # Load bag files
rose extract input.bag --topics gps imu  # Extract specific topics
rose compress *.bag --compression lz4    # Compress bag files
rose inspect demo.bag      # Inspect bag contents
rose data info demo.bag    # Show data information
rose cache                 # Manage cache
rose plugin list           # List available plugins

# Plugin management
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

### 1. UI Components (`roseApp/ui/`)
- **Common UI utilities**: `common_ui.py` - Shared UI components and helpers
- **Command builders**: `command_builder.py` - CLI command construction
- **Module-specific UIs**: `load_ui.py`, `extract_ui.py`, `compress_ui.py`, `inspect_ui.py`, `cache_ui.py`
- **Theme system**: `theme.py` - YAML-based theme management
- **Interactive components**: `interactive_common.py` - Shared interactive UI logic

### 2. CLI Commands (`roseApp/cli/`)
- **Load**: `load.py` - Load bag files into cache
- **Extract**: `extract.py` - Extract specific topics from bags
- **Compress**: `compress.py` - Compress bag files with different algorithms
- **Inspect**: `inspect.py` - Analyze bag contents and statistics
- **Data**: `data.py` - Data manipulation and export commands
- **Cache**: `cache.py` - Cache management operations
- **Plugin**: `plugin.py` - Plugin system management
- **Config**: `config.py` - Configuration management
- **Utility**: `util.py` - Shared CLI utilities

### 3. Core Engine (`roseApp/core/`)
- **BagManager**: `BagManager.py` - Central orchestrator for bag operations
- **Parser**: `parser.py` - ROS bag file parsing using rosbags
- **ExportManager**: `export_manager.py` - Handles filtered bag output and format exports
- **Cache**: `cache.py` - Persistent caching for parsed bag metadata
- **Configuration**: `config.py` - Configuration system with validation
- **Directories**: `directories.py` - Directory management utilities
- **Errors**: `errors.py` - Custom exception classes
- **Models**: `model.py` - Data models and type definitions
- **Utilities**: `util.py` - Shared utility functions
- **Plugins**: `plugins/` - Plugin system implementation

## Configuration

### Configuration Files
- **Main Configuration**: `rose.config.yaml` - Application settings and defaults
- **Default Configuration**: `rose.config.default.yaml` - Template configuration file
- **Theme Configuration**: `rose.theme.default.yaml` - Default color theme
- **Custom Theme**: `rose.theme.yaml` - User custom theme (optional)

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
- **Bash integration tests**: `tests/bash_tests/` - Comprehensive command testing
- **Test data**: Sample bag files in `roseApp/tests/`
- **Example demos**: `example/` - Usage examples and performance testing
- **Test scripts**: Individual test scripts for each command (`test_load.sh`, `test_extract.sh`, etc.)

### Test Commands
```bash
# Run all bash tests
cd tests/bash_tests && ./run_all_tests.sh

# Run specific command tests
cd tests/bash_tests && ./test_inspect.sh
cd tests/bash_tests && ./test_load.sh
cd tests/bash_tests && ./test_extract.sh

# Run tests with specific log level
ROSE_LOG_LEVEL=DEBUG bash tests/bash_tests/test_inspect.sh
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

## Current State & Recent Changes

### Recent Refactoring
- **Interactive CLI removed**: The interactive CLI components (`roseApp/interactive/`) have been removed in favor of direct CLI commands
- **UI components consolidated**: All UI logic moved to `roseApp/ui/` with module-specific UI files
- **Theme system simplified**: YAML-based theme configuration with fallback defaults

### Development Guidelines

### Code Style & Patterns
- **CLI/Interactive Parity**: Same parameters and validation logic for both CLI and interactive modes
- **Error Handling**: Use `log_cli_error()` for consistent error reporting
- **Type Hints**: Always use type hints for function parameters and return values
- **Rich Formatting**: Use rich console for colored output and progress indicators
- **Dry Run Support**: All destructive operations must support `--dry-run`

### Architecture Patterns
- **Factory Pattern**: Use `create_parser()` for parser instantiation
- **Interface-based Design**: Abstract base classes for extensibility
- **Cache-first Strategy**: Persistent metadata caching for performance
- **Modular Design**: Separate concerns between parsing, filtering, UI, and plugins

### Debugging
```bash
# Enable debug logging
export ROSE_DEBUG=1
export ROSE_LOG_LEVEL=DEBUG

# Run with debug output
rose --help --verbose

# Check cache directory
ls ~/.cache/rose/

# Run tests with debug output
ROSE_LOG_LEVEL=DEBUG bash tests/bash_tests/test_load.sh
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

# List available plugins
rose plugin list

# Enable/disable plugins
rose plugin enable my_analyzer
rose plugin disable my_analyzer
```