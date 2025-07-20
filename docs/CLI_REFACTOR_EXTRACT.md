# Extract Command Refactor

## Overview

The `filter` command has been refactored and renamed to `extract` to better reflect its purpose of extracting specific topics from ROS bag files.

## Key Changes

### Command Rename
- **Old**: `rose filter input.bag --topics gps --output output.bag`
- **New**: `rose extract extract-topics input.bag --topics gps -o output.bag`

### New Commands
- **`list-topics`**: List available topics with filtering support
- **`extract-topics`**: Extract specific topics from bag files

### New Architecture
- Uses unified `BagManager` API instead of direct parser access
- Shares topic filtering logic with `inspect` command
- Leverages caching system for improved performance
- Consistent error handling and logging

### Topic Filtering
The extract command now uses the same fuzzy matching logic as the inspect command:

```python
# Smart matching: exact match first, then fuzzy match
def _filter_topics(all_topics, selected_topics, topic_filter):
    if selected_topics:
        filtered = []
        for pattern in selected_topics:
            # First try exact match
            exact_matches = [topic for topic in all_topics if topic == pattern]
            if exact_matches:
                filtered.extend(exact_matches)
            else:
                # If no exact match, try fuzzy matching (contains)
                fuzzy_matches = [topic for topic in all_topics if pattern.lower() in topic.lower()]
                filtered.extend(fuzzy_matches)
        return filtered
```

## Usage Examples

### List Available Topics
```bash
# List all topics in a bag file
rose extract list-topics demo.bag

# List topics matching patterns (fuzzy matching)
rose extract list-topics demo.bag -p gps
rose extract list-topics demo.bag -p gps -p radar

# Exact matching for specific topics
rose extract list-topics demo.bag -p /gps/fix --exact

# JSON output for programmatic use
rose extract list-topics demo.bag -p gps --format json
```

### Basic Topic Extraction
```bash
# Extract GPS-related topics (fuzzy matching)
rose extract extract-topics input.bag --topics gps

# Extract specific topics (multiple --topics options)
rose extract extract-topics input.bag --topics /gps/fix --topics /radar/points

# Extract multiple topic patterns
rose extract extract-topics input.bag --topics gps --topics imu --topics camera

# Specify custom output file
rose extract extract-topics input.bag --topics gps -o output.bag
```

### Advanced Options
```bash
# Use compression
rose extract extract-topics input.bag --topics gps --compression lz4

# Dry run to preview
rose extract extract-topics input.bag --topics gps --dry-run

# Reverse selection - exclude matching topics
rose extract extract-topics input.bag --topics tf --reverse

# Auto-confirm all questions
rose extract extract-topics input.bag --topics gps -y

# Custom output with compression
rose extract extract-topics input.bag --topics gps -o output.bag -c lz4
```

### Topic Matching Examples
```bash
# Match topics containing "gps"
--topics gps
# Matches: /gps/fix, /obs1/gps/time, /gps/rtkfix, etc.

# Match topics containing "fix" 
--topics fix
# Matches: /gps/fix, /obs1/gps/fix, /gps/rtkfix, etc.

# Multiple patterns
--topics gps --topics imu
# Matches: all topics containing "gps" OR "imu"

# Exact topic names
--topics /gps/fix --topics /radar/points
# Matches: exactly /gps/fix and /radar/points

# Reverse selection (exclude topics)
--topics tf --reverse
# Keeps all topics EXCEPT those containing "tf"
```

## Migration Guide

### From Old Filter Command
```bash
# Old command
rose filter input.bag --topics gps --output output.bag

# New equivalent
rose extract extract-topics input.bag --topics gps -o output.bag
```

### Key Differences
1. **Simplified format**: Only input bag is required, output path is optional with auto-generated names
2. **Topic matching**: Now supports fuzzy matching like inspect command
3. **Reverse selection**: `--reverse` option to exclude topics instead of including them
4. **Auto-confirmation**: `-y` option to skip all confirmation prompts
5. **Caching**: Automatic caching of bag analysis for faster repeated operations
6. **Better error handling**: More informative error messages and validation
7. **Default output**: Auto-generated filenames with timestamps when output not specified

## Benefits

1. **Consistency**: Same topic filtering logic as inspect command
2. **Performance**: Leverages caching system for faster operations
3. **Usability**: Fuzzy matching makes topic selection more intuitive
4. **Discoverability**: `list-topics` command helps users explore bag contents
5. **Flexibility**: Support for both fuzzy and exact matching
6. **Maintainability**: Uses unified BagManager API
7. **Extensibility**: Easy to add new features through BagManager

## Implementation Details

### BagManager Integration
The extract command uses two new methods in BagManager:

#### Topic Discovery
```python
async def get_topics(self, bag_path, patterns=None, exact_match=False) -> Dict[str, Any]:
    # Analyze bag to get available topics
    result = await self.analyzer.analyze_bag_async(bag_path, AnalysisType.METADATA)
    
    # Apply filtering if patterns are provided
    if patterns:
        if exact_match:
            filtered_topics = [topic for topic in all_topics if topic in patterns]
        else:
            # Use fuzzy matching logic
            filtered_topics = self._filter_topics(all_topics, patterns, None)
    
    # Return detailed topic information
```

#### Topic Extraction
```python
async def extract_bag(self, bag_path, options: ExtractOptions) -> Dict[str, Any]:
    # Analyze bag to get available topics
    result = await self.analyzer.analyze_bag_async(bag_path, AnalysisType.METADATA)
    
    # Apply topic filtering using same logic as inspect
    topics_to_extract = self._filter_topics(
        list(result.bag_info.topics),
        options.topics,
        options.topic_filter
    )
    
    # Perform extraction using parser
    # Return detailed results
```

### Shared Logic
Both `inspect` and `extract` commands now use the same `_filter_topics()` method in BagManager, ensuring consistent behavior across commands. 