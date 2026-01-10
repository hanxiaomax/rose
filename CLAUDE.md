# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ROSE (Yet Another ROS Bag Filter) is a Python CLI/TUI tool for analyzing, filtering, and manipulating ROS (Robot Operating System) bag files. It uses the "cassette futurism" aesthetic with retro-futuristic design elements.

**Current Context**: Branch `tui-for-all` with recent TUI widget enhancements (multi_selection.py, path_search.py, question.py).

**Key Technologies:**
- **ROS Bag Processing**: `rosbags` library (pure Python, ROS environment independent)
- **CLI Framework**: `typer` with `rich` for styled terminal output
- **TUI Framework**: `textual` with `plotext` for interactive visualization
- **Data Validation**: `pydantic` for configuration and models
- **Build System**: `hatchling` with PyPI distribution

## Development Commands

### Running the Application
```bash
# Run from source
python -m roseApp.rose --help

# Install and run globally
pip install -e .
rose --help
```

### Testing
```bash
# Run all tests
pytest roseApp/tests/

# Run specific test file
pytest roseApp/tests/test_sdk_events.py

# Run tests in specific directory
pytest roseApp/tests/core/

# Run with coverage
pytest --cov=roseApp roseApp/tests/

# Run with verbose output
pytest -v roseApp/tests/

# Run tests matching a pattern
pytest -k "event" roseApp/tests/
```

### Building and Publishing
```bash
# Build package
hatch build

# Publish to PyPI (requires credentials)
hatch publish

# Install development dependencies
pip install -r requirements-dev.txt
```

### Docker Development
```bash
# Build Docker image
./docker/build.sh

# Run in Docker container
./docker/go_docker.sh
```

## Architecture

### Layered Structure
1. **Core Layer** (`roseApp/core/`): Data processing, caching, ROS bag interaction
   - `parser.py`: BagReader for reading ROS bag files
   - `writer.py`: BagWriter for writing filtered bags
   - `pipeline.py`: Generator-based pipelines for async operations
   - `cache.py`: Unified caching system with file hashing
   - `events.py`: Event system for real-time progress updates

2. **CLI Layer** (`roseApp/cli/`): Command-line interface
   - `load.py`: Load bag files into cache
   - `extract.py`: Extract specific topics with fuzzy matching
   - `compress.py`: Compress bags (BZ2, LZ4, none)
   - `inspect.py`: Inspect bag contents and statistics
   - `list.py`: Cache management commands
   - `config.py`: Configuration management

3. **TUI Layer** (`roseApp/tui/`): Interactive terminal UI
   - `inspect_app.py`: Main Textual application for bag inspection
   - `widgets/`: Custom UI components (Tree, Plot, Timeline)
   - `theme.py`: Theme management with cassette futurism aesthetic

### Key Design Patterns
- **Pipeline Pattern**: All heavy operations use generator-based pipelines in `pipeline.py` for non-blocking progress updates
- **Event-Driven**: CLI and TUI consume events (`LogEvent`, `ProgressEvent`) for real-time feedback
- **Separation of Concerns**: Business logic returns pure data; UI layers handle rendering
- **Unified Cache**: Bag analysis results cached using file hashing for performance
- **Interactive Mode**: Commands support `-i` flag for fuzzy search and multi-select topic selection

## Configuration System

### Configuration Files
- `roseApp/config/rose.config.default.yaml`: Default configuration
- `roseApp/config/rose.config.yaml`: User configuration (overrides defaults)
- `roseApp/config/themes/`: Theme files (nord, gruvbox, claude, default, solarized)

### Theme System
The "cassette futurism" aesthetic is implemented via YAML theme files:
```yaml
# Example theme structure
colors:
  primary: "#FF6B35"  # Orange reminiscent of 1980s computing
  secondary: "#004E89"
  background: "#1A1A2E"
  text: "#E6E6E6"
```

## Development Guidelines

### Code Style & Linting
- **Type Hints**: Strict mypy compliance, use Python 3.10+ syntax (`|`)
- **Docstrings**: Google-style for all functions, clear help strings for CLI commands
- **Formatting**: Black and Ruff standards
- **Path Handling**: Always use `pathlib.Path`, never `os.path`

```bash
# Install linting tools
pip install black ruff mypy

# Format code
black roseApp/

# Lint and auto-fix
ruff check --fix roseApp/
ruff format roseApp/

# Type checking
mypy roseApp/
```

### Error Handling
- Use custom exception classes in `roseApp/core/errors.py`
- Catch domain errors at CLI entry point for user-friendly messages
- Handle SIGINT (Ctrl+C) gracefully with clean exit messages

### Performance Considerations
- **Lazy Imports**: Heavy libraries imported within commands for fast `--help`
- **Parallel Processing**: Use `--workers` flag for CPU-intensive operations
- **Caching**: Bag metadata cached to avoid repeated expensive operations

## Testing Strategy

### Test Structure
- `roseApp/tests/core/`: Core functionality tests
- `roseApp/tests/bash_tests/`: Integration tests using bash scripts
- `test_sdk_events.py`: Event system tests

### Testing Patterns
- Mock external dependencies (file system, ROS bag libraries)
- Test both CLI and TUI interfaces
- Include integration tests for end-to-end workflows

## Docker Support

### Container Features
- All dependencies pre-installed
- ROS bag processing libraries (rosbags, rosbag)
- Volume mounting for accessing local bag files
- Cross-platform compatibility

### Development Workflow
1. Build image: `./docker/build.sh`
2. Run container: `./docker/go_docker.sh`
3. Access mounted directories for bag file processing

## Project Structure Reference

```
rose/
├── roseApp/                    # Main Python package
│   ├── rose.py                # CLI entry point
│   ├── cli/                   # CLI command implementations
│   ├── core/                  # Core business logic
│   ├── tui/                   # Textual-based TUI
│   ├── config/                # Configuration and themes
│   └── tests/                 # Test files
├── docker/                    # Docker support files
├── docs/                      # Documentation
├── pyproject.toml             # Project metadata and dependencies
└── requirements*.txt          # Dependency lists
```

## Common Development Tasks

### Adding a New CLI Command
1. Create command file in `roseApp/cli/` following existing patterns
2. Implement business logic in `roseApp/core/` (returns pure data, no printing)
3. Add command to `roseApp/rose.py` app registration
4. Write tests in `roseApp/tests/`
5. Support interactive mode (`-i`) with fuzzy search when appropriate

### Modifying TUI Components
1. Update widgets in `roseApp/tui/widgets/` (current focus: multi_selection.py, path_search.py, question.py)
2. Modify theme in `roseApp/config/themes/`
3. Test with `python -m roseApp.tui.inspect_app`
4. Maintain "cassette futurism" aesthetic

### Updating Dependencies
1. Update `pyproject.toml` for main dependencies
2. Update `requirements-dev.txt` for development dependencies
3. Rebuild Docker image if needed: `./docker/build.sh`

## Notes for Claude Code

- This project uses **Chinese for conversation** but **English for all code, comments, and docstrings**
- Follow the "Unix Philosophy": silence is golden for pipeable output, use stderr for logs
- Maintain the "cassette futurism" aesthetic in UI components
- ROS environment independence is a key feature - avoid ROS-specific dependencies
- The cache system uses file hashing; changes to bag parsing may require cache invalidation logic