# Interactive CLI Refactoring Design

## Overview

This document outlines the refactoring plan for the Rose interactive CLI to create a clean, maintainable architecture where the interactive interface serves as a pure user interface layer that delegates all actual work to the underlying CLI commands.

## Core Design Philosophy

**Interactive as pure user interface layer**, responsible for:
- User interaction and input processing
- Result display and formatting  
- Command routing and parameter parsing
- Actual execution delegated to underlying CLI commands

## Directory Structure

```
roseApp/interactive/
├── components/           # Core interaction components
│   ├── __init__.py
│   ├── path_completer.py    # Path completion (supports @ references)
│   ├── cli_executor.py      # CLI command executor (core)
│   └── result_formatter.py  # Result formatting
├── commands/             # Command interface layer
│   ├── __init__.py
│   ├── load_command.py     # /load → rose load
│   ├── extract_command.py  # /extract → rose extract
│   ├── inspect_command.py  # /inspect → rose inspect
│   ├── compress_command.py # /compress → rose compress
│   ├── data_command.py     # /data → rose data
│   ├── cache_command.py    # /cache → rose cache
│   ├── plugin_command.py   # /plugin → rose plugin
│   ├── status_command.py   # /status → internal status display
│   ├── bags_command.py     # /bags → internal bag management
│   ├── topics_command.py   # /topics → internal topic management
│   ├── configuration_command.py  # /configuration → editor
│   ├── help_command.py     # /help → internal help display
│   ├── clear_command.py    # /clear → internal console clear
│   └── exit_command.py     # /exit, /quit → internal exit handling
├── core/                 # Core infrastructure
│   ├── __init__.py
│   ├── interactive_runner.py # Main runner (lightweight)
│   └── command_router.py     # Command routing
└── __init__.py
```

## Core Components

### CLIExecutor Component

The heart of the system that delegates work to actual CLI commands:

```python
class CLIExecutor:
    """CLI command executor - delegates to actual command line"""
    
    def execute_command(self, command: str, args: List[str]) -> Dict[str, Any]:
        """Execute actual rose command line using subprocess"""
        # Builds: rose <command> <args>
        # Captures stdout, stderr, return code
        # Returns standardized result format
```

### PathCompleter Component

Handles intelligent path completion and @ reference resolution:

```python
class PathCompleter:
    """Path completion with @ reference resolution"""
    
    def resolve_at_references(self, input_text: str) -> str:
        """Resolve @symbol references to actual file paths"""
        # @test.bag → /actual/path/to/test.bag
        # Supports cached bag lookup and file system search
```

### ResultFormatter Component

Formats CLI command outputs for user-friendly display:

```python
class ResultFormatter:
    """Formats CLI command results for interactive display"""
    
    def format_cli_result(self, result: Dict[str, Any]) -> str:
        """Convert raw CLI output to formatted display"""
        # Extracts key information
        # Applies consistent styling
        # Handles errors gracefully
```

## Command Interface Layer

### Base Command Pattern

All commands inherit from this base class:

```python
class BaseCommand:
    """Base command - only does parameter conversion and result formatting"""
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """Execute command: convert args → call CLI → format result"""
        # 1. Parse interactive arguments
        # 2. Execute actual CLI command
        # 3. Format and return result
```

### Command Examples

#### LoadCommand
```python
class LoadCommand(BaseCommand):
    """Delegates to: rose load"""
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        # /load *.bag @test → rose load *.bag /actual/path/to/test.bag
        resolved_args = self.cli_executor.path_completer.resolve_at_references(interactive_args)
        return resolved_args.split()
```

#### ExtractCommand
```python
class ExtractCommand(BaseCommand):
    """Delegates to: rose extract"""
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        # Handles topic selection parameters
        # Converts to rose extract compatible format
```

#### ConfigurationCommand
```python
class ConfigurationCommand(BaseCommand):
    """Handles /configuration - opens config file in editor"""
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        # Opens configuration file using system default editor
        # Falls back to common editors (nano, vim, code, notepad)
        # Returns editor execution result
```

## Main Runner (Lightweight)

```python
class InteractiveRunner:
    """Main runner - only responsible for routing and display"""
    
    def __init__(self):
        self.cli_executor = CLIExecutor()
        self.formatter = ResultFormatter()
        
        # Command registry mapping
        self.commands = {
            '/load': LoadCommand(self.cli_executor),
            '/extract': ExtractCommand(self.cli_executor),
            '/inspect': InspectCommand(self.cli_executor),
            '/compress': CompressCommand(self.cli_executor),
            '/data': DataCommand(self.cli_executor),
            '/cache': CacheCommand(self.cli_executor),
            '/plugin': PluginCommand(self.cli_executor),
            '/status': StatusCommand(self.cli_executor),
            '/bags': BagsCommand(self.cli_executor),
            '/topics': TopicsCommand(self.cli_executor),
            '/configuration': ConfigurationCommand(self.cli_executor),
            '/help': HelpCommand(self.cli_executor),
            '/clear': ClearCommand(self.cli_executor),
            '/exit': ExitCommand(self.cli_executor),
            '/quit': ExitCommand(self.cli_executor),  # Alias
        }
    
    def run_interactive(self):
        """Main interactive loop - routes commands and displays results"""
```

## Workflow

### Command Execution Flow

1. **User Input**: `/load @test.bag *.bag`
2. **Parameter Parsing**: PathCompleter resolves `@test.bag` → actual path
3. **Command Execution**: CLIExecutor executes `rose load /actual/path/test.bag *.bag`
4. **Result Capture**: Capture subprocess output and status
5. **Result Formatting**: ResultFormatter beautifies display
6. **User Feedback**: Display formatted result

### @ Reference Resolution

```
Input: /load @test.bag data/*.bag
↓
PathCompleter.resolve_at_references()
↓
Resolved: /load /absolute/path/to/test.bag data/*.bag
↓
CLIExecutor.execute_command("load", ["/absolute/path/to/test.bag", "data/*.bag"])
↓
subprocess.run(["rose", "load", "/absolute/path/to/test.bag", "data/*.bag"])
```

## Component Interfaces

### CLIExecutor Interface

```python
class CLIExecutor:
    def execute_command(command: str, args: List[str]) -> Dict[str, Any]:
        """
        Returns:
        {
            'success': bool,
            'stdout': str,
            'stderr': str,
            'returncode': int,
            'error': Optional[str]
        }
        """
```

### PathCompleter Interface

```python
class PathCompleter:
    def resolve_at_references(input_text: str) -> str:
        """Resolve @ references in input text"""
    
    def complete_bag_files(partial_path: str) -> List[str]:
        """Return completion suggestions for bag files"""
```

### ResultFormatter Interface

```python
class ResultFormatter:
    def format_cli_result(result: Dict[str, Any]) -> str:
        """Format CLI execution result for display"""
    
    def format_success(stdout: str) -> str:
        """Format successful command output"""
    
    def format_error(stderr: str, error: str) -> str:
        """Format error output"""
```

## Command Mapping Table

| Interactive Command | CLI Command | Description |
|---------------------|-------------|-------------|
| `/load`            | `rose load` | Load bag files |
| `/extract`         | `rose extract` | Extract topics from bags |
| `/inspect`         | `rose inspect` | Inspect bag contents |
| `/compress`        | `rose compress` | Compress bag files |
| `/data`            | `rose data` | Data operations and export |
| `/cache`           | `rose cache` | Cache management |
| `/plugin`          | `rose plugin` | Plugin system operations |
| `/status`          | (internal) | Show workspace status and running tasks |
| `/bags`            | (internal) | Manage loaded bag files in workspace |
| `/topics`          | (internal) | Manage topic selection for operations |
| `/configuration`   | (editor) | Open configuration file in default editor |
| `/help`            | (internal) | Show detailed help documentation |
| `/clear`           | (internal) | Clear console screen |
| `/exit`            | (internal) | Exit interactive mode |
| `/quit`            | (internal) | Exit interactive mode (alias) |

## Error Handling Strategy

### CLI Execution Errors
- Capture stderr and return code from subprocess
- Format error messages for user-friendly display
- Provide suggestions for common errors

### @ Reference Resolution Errors
- Graceful fallback when references cannot be resolved
- Clear error messages indicating resolution failure
- Option to use original @ reference as fallback

### Parameter Parsing Errors
- Validation of interactive parameters
- Clear error messages for invalid parameters
- Helpful suggestions for correction

## Performance Considerations

### CLI Command Execution
- Use subprocess with appropriate timeouts
- Stream output for long-running commands
- Cache frequently used CLI results

### @ Reference Resolution
- Cache resolved references during session
- Optimize file system searches
- Use efficient path matching algorithms

## Testing Strategy

### Unit Tests
- Test each component in isolation
- Mock CLIExecutor for command tests
- Test @ reference resolution logic

### Integration Tests
- Test full command execution flow
- Verify parameter conversion accuracy
- Test error handling scenarios

### Component Testing Matrix

| Component | Test Focus |
|-----------|------------|
| CLIExecutor | Subprocess execution, error handling |
| PathCompleter | @ reference resolution, path completion |
| ResultFormatter | Output formatting, error display |
| Command Classes | Parameter parsing, CLI delegation |

## Migration Plan

### Phase 1: Core Infrastructure
1. Create new directory structure
2. Implement CLIExecutor and PathCompleter
3. Create base command classes

### Phase 2: Command Migration
1. Migrate /load command first
2. Test and validate functionality
3. Migrate remaining commands one by one

### Phase 3: Integration
1. Update main runner to use new architecture
2. Test full interactive workflow
3. Remove old handler code

## Benefits

1. **Clear Separation**: Interactive only handles UI, CLI handles business logic
2. **Consistency**: Interactive and CLI behavior identical
3. **Maintainability**: No duplicate business logic
4. **Performance**: Heavy work done by optimized CLI
5. **Testability**: Components can be tested independently
6. **Extensibility**: Easy to add new commands

This design ensures the interactive interface remains lightweight and focused on user experience, while leveraging the full power of the underlying CLI commands for actual processing work.