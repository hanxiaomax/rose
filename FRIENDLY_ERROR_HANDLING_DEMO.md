# Friendly Error Handling Demo

This document demonstrates the new friendly error handling system implemented in the Rose CLI tool.

## Overview

The friendly error handling system provides:

1. **Clear, user-friendly error messages** - No Python tracebacks for common errors
2. **Helpful suggestions** - File suggestions, closest matches, and examples
3. **Consistent formatting** - All error messages follow the same format
4. **Contextual help** - Relevant examples and guidance for each command

## Features Demonstrated

### 1. Main Help System

When no command is provided, the system shows a helpful command overview:

```bash
$ python -m roseApp.rose

Available commands:
╭─────────┬─────────────────────────────────────────┬─────────────────────────────────────────────────────────────╮
│ Command │ Description                             │ Example                                                     │
├─────────┼─────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ filter  │ Filter ROS bag files by topics          │ rose filter input.bag output/                               │
│ inspect │ Inspect ROS bag file contents           │ rose inspect input.bag                                      │
│ plot    │ Plot data from ROS bag files            │ rose plot input.bag --series /topic:field --output plot.png │
│ prune   │ Remove unwanted topics from bag files   │ rose prune input.bag --topics /unwanted                     │
│ cli     │ Interactive CLI tool                    │ rose cli                                                    │
│ tui     │ Text-based user interface               │ rose tui                                                    │
╰─────────┴─────────────────────────────────────────┴─────────────────────────────────────────────────────────────╯

Use rose <command> --help for detailed help on any command
```

### 2. File Not Found Errors

Smart file suggestions when files don't exist:

```bash
$ python -m roseApp.rose inspect nonexistent.bag

Error: Bag file not found
Path: nonexistent.bag
Did you mean one of these?
  • ./test.bag
  • ./test_filtered.bag
  • ./demo.bag
  • ./sample.bag
```

### 3. Invalid Option Values

Clear listing of valid options with closest match suggestions:

```bash
$ python -m roseApp.rose inspect tests/demo.bag --as invalidformat

Error: Invalid value for --as: 'invalidformat'
Command: inspect

Valid options:
  • table
  • list
  • summary
  • csv
  • html
```

### 4. Missing Required Options

Helpful examples for missing required parameters:

```bash
$ python -m roseApp.rose plot tests/demo.bag --output test.png

Error: Missing required option: --series
Command: plot

Examples:
  • rose plot input.bag --series /odom:pose.pose.position.x --output plot.png
  • rose plot input.bag --series /tf:transform.translation.x,transform.translation.y --output plot.png

Use --help to see all available options
```

### 5. Invalid Parameter Formats

Detailed format explanations with examples:

```bash
$ python -m roseApp.rose plot tests/demo.bag --series invalid_format --output test.png

Error: Invalid series format: 'invalid_format'
Expected format: topic:field1,field2

Examples:
  • /odom:pose.pose.position.x
  • /tf:transform.translation.x,transform.translation.y
```

### 6. Topic Validation

Specific guidance for ROS topic naming:

```bash
$ python -m roseApp.rose plot tests/demo.bag --series odom:pose.pose.position.x --output test.png

Error: Topic must start with '/': 'odom'
Correct format: /odom:pose.pose.position.x
```

### 7. Compression and Sort Options

Clear enumeration of valid values:

```bash
$ python -m roseApp.rose filter-bag tests/demo.bag output/ --compression invalidcompression

Error: Invalid value for --compression: 'invalidcompression'
Command: filter

Valid options:
  • none
  • bz2
  • lz4
```

### 8. Dependency Missing Errors

Installation instructions for missing dependencies:

```bash
$ python -m roseApp.rose plot tests/demo.bag --series /tf:transform --output test.png

Error: Missing required dependency: matplotlib
Required for: plotting functionality

To install:
  pip install matplotlib

After installation, try running the command again
```

## Implementation Details

### Error Handler Classes

1. **FriendlyErrorHandler** - Base class with common error handling methods
2. **CommandErrorHandlers** - Command-specific validation and error handling

### Key Methods

- `file_not_found()` - Handles missing files with suggestions
- `missing_required_option()` - Provides examples for missing options
- `invalid_option_value()` - Lists valid alternatives
- `dependency_missing()` - Shows installation instructions
- `show_available_commands()` - Displays command overview

### Integration Points

- **Main CLI** - Shows friendly command list instead of raw help
- **All Commands** - Use consistent error handling patterns
- **No Tracebacks** - Python exceptions are caught and formatted nicely

## Testing

The system includes comprehensive tests covering:

- Individual error handler methods
- Command-specific error validation
- CLI integration testing
- Error message quality verification
- Traceback suppression verification

Run tests with:
```bash
python -m pytest tests/cli/test_friendly_errors.py -v
```

## Benefits

1. **Improved User Experience** - Clear, actionable error messages
2. **Reduced Support Burden** - Self-explanatory errors with examples
3. **Faster Learning Curve** - Contextual help and suggestions
4. **Professional Polish** - Consistent, clean error formatting
5. **Maintainable Code** - Centralized error handling logic

## Future Enhancements

Potential improvements:

1. **Fuzzy Command Matching** - Suggest similar commands for typos
2. **Interactive Error Recovery** - Prompt for corrections
3. **Context-Aware Suggestions** - File suggestions based on current directory
4. **Localization Support** - Multi-language error messages
5. **Error Analytics** - Track common error patterns

This friendly error handling system significantly improves the user experience by providing clear, helpful guidance when things go wrong, making the Rose CLI tool more accessible and professional. 