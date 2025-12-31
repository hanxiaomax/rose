
# Rose Key Modules Documentation

This document provides an overview of the key modules in the Rose application `core`.

## Core Modules

### 1. `roseApp.core.model`

Defines the core data structures for ROS bag analysis.

**Key Classes:**

*   **`BagInfo`**: The central data structure holding all information about a bag file.
    *   `file_path`: Path to the bag file.
    *   `topics`: List of `TopicInfo` objects.
    *   `message_types`: List of `MessageTypeInfo` objects.
    *   `file_size`: Size of the file in bytes.
    *   `file_mtime`: Modification time of the file (for cache validation).
    *   `analysis_level`: `AnalysisLevel.QUICK` or `AnalysisLevel.INDEX`.

*   **`TopicInfo`**: Metadata for a single topic.
    *   `name`: Topic name.
    *   `message_type`: ROS message type string.
    *   `message_count`: Total number of messages.

### 2. `roseApp.core.parser`

Handles parsing of ROS bag files using the `rosbags` library.

**Key Classes:**

*   **`BagReader`**: Singleton class for loading bag files.
    *   `load_bag_async(path, level)`: Asynchronously loads a bag file. Supports `QUICK` (metadata only) and `INDEX` (full message parsing) levels.
    *   `clear()`: Clears internal state.

### 3. `roseApp.core.pipeline`

Orchestrates complex operations like loading, extracting, and compressing.

**Key Functions:**

*   **`load_orchestrator(patterns, force, ...)`**: Finds and loads bag files, managing the cache.
*   **`extract_orchestrator(patterns, topics, ...)`**: Extracts specific topics from bags to new files.
*   **`compress_orchestrator(patterns, output, ...)`**: Compresses bag files.
*   **`inspect_orchestrator(pattern)`**: Retrieves detailed information about a bag.

### 4. `roseApp.core.cache`

Manages caching of analysis results to speed up operations.

**Key Classes:**

*   **`Cache`**: Core caching system using `pickle` for persistence.
    *   `get_bag_analysis(path)`: Retrieves `BagInfo` if cached and valid.
    *   `put_bag_analysis(path, info)`: Caches analysis results.
    *   Validation is performed using `file_size` and `file_mtime`.

*   **`BagCacheManager`**: Simplified interface for bag-specific caching operations.

### 5. `roseApp.core.config`

Manages configuration settings.

**Key Classes:**

*   **`RoseConfig`**: Pydantic model for configuration settings.
    *   Loads from `rose.config.yaml` (in `roseApp/config/` or user home) and environment variables.
    *   Settings include: `cache_dir`, `parallel_workers`, `compression_default`, etc.

## CLI Modules

Located in `roseApp.cli`, these modules map commands to core orchestrators.

*   `load.py`: Handling `rose load`.
*   `list.py`: Handling `rose list`.
*   `inspect.py`: Handling `rose inspect`.
*   `extract.py`: Handling `rose extract`.
*   `compress.py`: Handling `rose compress`.
