# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ROSE is a high-performance ROS bag filtering tool with distinctive cassette futurism aesthetic. It provides CLI and TUI interfaces for filtering ROS v1 bag files without ROS environment dependencies, using the `rosbags` library. The system features a modern NDJSON event emitter for headless mode operation.

## Essential Development Commands

### Setup & Installation
```bash
# Install dependencies and development mode
pip install -e .

# Alternative: use install script for full setup
./install.sh

# Verify installation
rose --help
```

### Testing (Primary Method)
```bash
# Run all bash integration tests
cd tests/bash_tests && ./run_all_tests.sh

# Run individual command tests
cd tests/bash_tests && ./test_load.sh
cd tests/bash_tests && ./test_extract.sh
cd tests/bash_tests && ./test_compress.sh
cd tests/bash_tests && ./test_inspect.sh
cd tests/bash_tests && ./test_data.sh
cd tests/bash_tests && ./test_cache.sh
cd tests/bash_tests && ./test_plugin.sh

# Quick test script
cd tests/bash_tests && ./quick_test.sh
```

### Development Workflow
```bash
# Test CLI commands
rose load *.bag
rose extract input.bag --topics gps imu
rose compress *.bag --compression lz4
rose inspect demo.bag
rose data info demo.bag
rose cache
rose plugin list

# Plugin management
rose plugin create my_plugin --template basic

# Build and publish
hatch build
hatch publish
```

## Core Architecture

### NDJSON Event Emitter System
**Key Component**: `roseApp/core/event_emitter.py`

**Core Methods**:
- `emit_progress(percent, message="", step=None, total_steps=None)`
- `emit_data(data, label=None, count=None)`
- `emit_done(summary)`
- `emit_error(code, message, details=None)`

**Global Management**:
- `init_emitter()` - Initialize global emitter
- `get_emitter()` - Get current emitter instance
- `reset_emitter()` - Reset emitter state

**Manual Context Setup**:
```python
emitter = get_emitter()
emitter.set_context("command_name")
```

### Key Classes
- **BagManager** (`roseApp/core/BagManager.py`) - Central orchestrator
- **Parser** (`roseApp/core/parser.py`) - ROS bag parsing with rosbags
- **EventEmitter** (`roseApp/core/event_emitter.py`) - NDJSON protocol output
- **CacheManager** (`roseApp/core/cache.py`) - Persistent metadata caching
- **PluginManager** (`roseApp/core/plugins/manager.py`) - Plugin system

### Data Flow
- **Parser** → **BagManager** → **ExportManager** with NDJSON event emission
- **Cache System**: Persistent metadata caching in `~/.cache/rose/`
- **Plugin System**: Hot-loadable plugins with hook system

## Interface Modes

### CLI Commands (`roseApp/cli/`)
- `load.py` - Load bag files into cache
- `extract.py` - Extract specific topics
- `compress.py` - Compress bag files
- `inspect.py` - Analyze bag contents
- `data.py` - Data manipulation and export
- `cache.py` - Cache management
- `plugin.py` - Plugin system management

### TUI Interface (`roseApp/ui/`)
- Textual-based terminal UI with retro styling
- YAML-based theme system
- Module-specific UI components

## Configuration

### Essential Files
- `rose.config.yaml` - Main configuration
- `rose.theme.default.yaml` - Default color theme
- `rose.theme.yaml` - Custom theme (optional)

### Environment Setup
```bash
# Terminal colors
export TERM=xterm-256color

# Development debugging
export ROSE_DEBUG=1
export ROSE_LOG_LEVEL=DEBUG
```

## Key Features

### Compression Support
- **BZ2**: Best compression (~80-90% reduction)
- **LZ4**: Balanced speed/compression (~60-70% reduction)
- **None**: Fastest processing, no compression

### Filtering Capabilities
- Topic-based filtering with fuzzy matching
- Time range filtering
- Parallel processing for batch operations
- Dry-run mode for previewing

### Plugin System
- Hot-loadable plugins without restart
- Hook system for custom logic
- Data interface for safe bag data access
- Custom CLI commands support

## Testing Structure

### Primary Testing Approach
- **Bash integration tests**: `tests/bash_tests/` - Comprehensive command testing
- **Color-coded test runner**: `run_all_tests.sh` with detailed output
- **Individual command tests**: Separate scripts for each CLI command

### Test Execution
```bash
# Run with specific bag file
cd tests/bash_tests && ./run_all_tests.sh --bag roseApp/tests/test.bag

# Run with verbose output
cd tests/bash_tests && ./run_all_tests.sh --verbose
```

## Deployment

### PyPI Release
```bash
# Update version in pyproject.toml
hatch build
hatch publish
```

### Docker Support
```bash
# Build and run
docker build -t rose-bag .
docker run -it --rm -v $(pwd):/data rose-bag rose tui
```

## Dependencies

### Core Dependencies
- **rosbags**: ROS bag processing (no ROS required)
- **textual**: TUI framework
- **typer**: CLI framework
- **rich**: Terminal formatting
- **pydantic**: Data validation

### Development
- Uses hatchling build system
- Python 3.8+ support
- Tests excluded from wheel distribution

## Debugging & Performance

### Debugging
```bash
# Enable debug output
export ROSE_DEBUG=1
export ROSE_LOG_LEVEL=DEBUG

# Check cache
ls ~/.cache/rose/

# Test with debug
ROSE_LOG_LEVEL=DEBUG bash tests/bash_tests/test_load.sh
```

### Performance Testing
```bash
# Cache performance test
rm ~/.cache/rose/* && time rose inspect info test.bag

# Large file testing
time rose filter large.bag filtered.bag -w whitelist.txt
```

## Current State

### Recent Architecture
- **NDJSON Event Emitter**: Fully implemented for headless mode
- **CLI Commands**: All integrated with NDJSON output
- **Manual Context**: Commands use manual emitter initialization
- **Protocol Version**: `rose.ndjson v1.0`

### Development Guidelines
- **Type Hints**: Always use for function parameters and returns
- **Rich Formatting**: Use rich console for colored output
- **Error Handling**: Use `log_cli_error()` for consistency
- **Dry Run Support**: All destructive operations support `--dry-run`