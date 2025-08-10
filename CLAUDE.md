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

### Key Classes
- **BagManager** (`roseApp/core/BagManager.py`) - Central orchestrator for bag operations
- **Parser** (`roseApp/core/parser.py`) - ROS bag file parsing using rosbags
- **ExportManager** (`roseApp/core/export_manager.py`) - Handles filtered bag output

## Development Commands

### Setup & Installation
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install locally for development
pip install -e .

# Verify installation
rose --help
```

### Testing
```bash
# Run all tests with coverage
python roseApp/tests/run_tests.py

# Run specific test file
python roseApp/tests/run_tests.py --file test_bag_manager

# Run fast unit tests only
python roseApp/tests/run_tests.py --fast

# Run tests with coverage report
python roseApp/tests/run_tests.py --coverage
```

### Development Workflow
```bash
# Run TUI in dev mode (with hot reload)
textual run --dev roseApp.tui.tui:app

# CLI commands
rose tui                    # Launch TUI
rose cli                    # Interactive CLI mode
rose filter input.bag output.bag -w whitelist.txt

# Inspect bag contents
rose inspect topics input.bag
rose inspect info input.bag

# Extract specific data
rose extract --help
```

## Interface Modes

### 1. TUI Mode (`rose tui`)
- Cassette futurism themes (`cassette-walkman`, `cassette-dark`)
- Fuzzy topic search with real-time filtering
- Multi-selection batch processing
- Whitelist management (load/save)
- Compression options (BZ2, LZ4, none)

### 2. Interactive CLI (`rose cli`)
- Menu-driven interface
- Guided workflows for filtering
- Batch processing capabilities
- Whitelist creation and management

### 3. Direct CLI Commands
- `rose filter` - Filter bags with topics/whitelists
- `rose inspect` - Analyze bag contents
- `rose extract` - Extract specific data
- `rose cache` - Manage parser cache

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

## Testing Structure

### Test Organization
- **Unit tests**: `roseApp/tests/test_*.py`
- **Integration tests**: Marked with `@pytest.mark.integration`
- **Slow tests**: Marked with `@pytest.mark.slow`
- **Test data**: Sample bag files in `roseApp/tests/`

### Test Commands
```bash
# Run specific test categories
python roseApp/tests/run_tests.py --file test_parser
python roseApp/tests/run_tests.py --fast
python roseApp/tests/run_tests.py --coverage
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
# Build Docker image
docker build -t rose-bag .

# Run with Docker
docker run -it --rm -v $(pwd):/data rose-bag rose tui
```

## Dependencies

### Core Dependencies
- **rosbags**: ROS bag file processing (no ROS required)
- **textual**: TUI framework
- **typer**: CLI framework
- **rich**: Terminal formatting
- **pydantic**: Data validation

### Optional Dependencies
- **lz4**: LZ4 compression support
- **matplotlib/plotly**: Visualization features