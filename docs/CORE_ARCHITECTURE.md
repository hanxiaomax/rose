# Core Architecture Documentation

## Overview

The Rose core directory (`./roseApp/core`) implements a sophisticated ROS bag file processing system with a layered architecture. The system provides high-performance bag analysis, filtering, and extraction capabilities using modern Python libraries and intelligent caching mechanisms.

## Architecture Layers

The system follows a clear layered architecture pattern:

1. **CLI Interface Layer** - User interface and command handling
2. **Management Layer** - High-level bag operations coordination
3. **Analysis Layer** - Asynchronous bag analysis with caching
4. **Parsing Layer** - Low-level bag file processing using rosbags
5. **Caching Layer** - Multi-level caching for performance optimization
6. **UI Layer** - Rich progress displays and result formatting
7. **Utility Layer** - Common utilities and helper functions

## System Architecture Diagram

```mermaid
graph TD
    subgraph "CLI Interface Layer"
        CLI[CLI Commands]
    end

    subgraph "Management Layer"
        BM[bag_manager.py<br/>Unified API]
    end

    subgraph "Analysis Layer"
        BA[analyzer.py<br/>Async Bag Analyzer]
        BA -->|ThreadPoolExecutor| TP[4 Worker Threads]
    end

    subgraph "Caching Layer"
        UC[UnifiedCache<br/>Multi-level Cache]
        subgraph "Memory Cache"
            MC[MemoryCache<br/>512MB LRU]
        end
        subgraph "File Cache"
            FC[FileCache<br/>2GB SQLite]
        end
        UC --> MC
        UC --> FC
    end

    subgraph "Parsing Layer"
        BP[parser.py<br/>rosbags-based]
        subgraph "rosbags Library"
            AR[AnyReader]
            RW[Rosbag1Writer]
            TS[TypeStore]
        end
        BP --> AR
        BP --> RW
        BP --> TS
    end

    subgraph "UI Layer"
        UC2[ui_control.py<br/>Rich UI System]
        subgraph "Progress Types"
            AP[Analysis Progress]
            EP[Extraction Progress]
            TLP[Topic-level Progress]
            RP[Responsive Progress]
        end
        UC2 --> AP
        UC2 --> EP
        UC2 --> TLP
        UC2 --> RP
    end

    subgraph "Utility Layer"
        UT[util.py<br/>Common Utilities]
        BV[bag_validator.py<br/>Validation]
    end

    %% Data Flow Connections
    CLI -->|extract_bag| BM
    CLI -->|inspect_bag| BM
    CLI -->|profile_bag| BM
    CLI -->|diagnose_bag| BM

    BM -->|analyze_bag_async| BA
    BM -->|display_progress| UC2

    BA -->|get_comprehensive_bag_info| BP
    BA -->|get| UC
    BA -->|put| UC

    BP -->|cache| UC
    BP -->|validate| BV

    UC -->|stats| BA
    UC -->|optimize| BA

    BM -->|render_result| UC2
    BM -->|export_result| UC2

    %% Cache optimization
    UC -.->|preheat| BA
    UC -.->|performance_analysis| BA

    style CLI fill:#e1f5fe
    style BM fill:#fff3e0
    style BA fill:#f3e5f5
    style UC fill:#e8f5e8
    style BP fill:#fff8e1
    style UC2 fill:#fce4ec
    style UT fill:#f3e5f5
    style BV fill:#f3e5f5
```

## Component Architecture

### 1. BagManager.py - Core Bag Management
- **Purpose**: Manages bag file lifecycle and topic operations
- **Key Classes**: `Bag`, `BagManager`
- **Responsibilities**: 
  - Load/unload bag files
  - Topic selection and filtering
  - Bag metadata management

### 2. bag_manager.py - Unified High-Level Interface
- **Purpose**: Provides async interface for complete bag operations
- **Key Methods**: 
  - `inspect_bag()` - Analyze bag contents
  - `extract_bag()` - Filter and extract topics
  - `profile_bag()` - Performance profiling
  - `diagnose_bag()` - Health diagnostics
- **Integration**: Coordinates between analyzer, parser, and UI

### 3. parser.py - ROS Bag Parser (rosbags-based)
- **Purpose**: High-performance bag parsing using rosbags library
- **Key Classes**: `RosbagsBagParser`, `ComprehensiveBagInfo`
- **Features**:
  - Memory-efficient chunked processing (10k messages/chunk)
  - Comprehensive caching (5min TTL)
  - Support for BZ2, LZ4, uncompressed formats
  - Single-pass statistics calculation

### 4. analyzer.py - Async Bag Analysis
- **Purpose**: Asynchronous bag analysis with intelligent caching
- **Key Classes**: `BagAnalyzer`, `AnalysisResult`
- **Features**:
  - ThreadPoolExecutor-based async operations
  - Message type structure analysis
  - Field extraction and analysis
  - Caching with 1-hour TTL

### 5. cache.py - Multi-Level Caching System
- **Purpose**: Unified caching with memory + file persistence
- **Key Classes**: `UnifiedCache`, `MemoryCache`, `FileCache`
- **Specifications**:
  - Memory Cache: 512MB LRU with TTL support
  - File Cache: 2GB SQLite-backed with compression
  - Performance analysis and optimization

### 6. ui_control.py - Rich UI System
- **Purpose**: Comprehensive UI management with progress bars and theming
- **Key Features**:
  - 4 types of progress bars (analysis, extraction, topic-level, responsive)
  - Theme system (light/dark/auto modes)
  - Export capabilities (JSON, YAML, CSV, XML, HTML, Markdown)
  - Rich formatting and display

### 7. util.py - Common Utilities
- **Purpose**: Shared utilities and helper functions
- **Key Features**:
  - Logging configuration
  - Time conversion utilities
  - Compression validation
  - Platform compatibility

## Data Flow Architecture

```mermaid
flowchart TD
    Start([User Command]) --> CMD[CLI Command]
    
    CMD -->|extract| EXTRACT[bag_manager.extract_bag]
    CMD -->|inspect| INSPECT[bag_manager.inspect_bag]
    CMD -->|profile| PROFILE[bag_manager.profile_bag]
    CMD -->|diagnose| DIAGNOSE[bag_manager.diagnose_bag]
    
    EXTRACT --> INIT_PROGRESS[Initialize Progress UI]
    INSPECT --> INIT_PROGRESS
    PROFILE --> INIT_PROGRESS
    DIAGNOSE --> INIT_PROGRESS
    
    INIT_PROGRESS --> CACHE_CHECK{Cache Check}
    CACHE_CHECK -->|Cache Hit| USE_CACHE[Use Cached Result]
    CACHE_CHECK -->|Cache Miss| ANALYZE[BagAnalyzer.analyze_bag_async]
    
    ANALYZE -->|Step 1| LOAD_INFO[Load Bag Info
via RosbagsBagParser]
    ANALYZE -->|Step 2| CALC_STATS[Calculate Statistics]
    ANALYZE -->|Step 3| EXTRACT_FIELDS[Extract Message Fields]
    
    LOAD_INFO -->|get_comprehensive_bag_info| PARSER[RosbagsBagParser]
    PARSER -->|AnyReader| ROSBAGS_LIB[rosbags Library]
    
    CALC_STATS -->|cache results| CACHE[UnifiedCache]
    EXTRACT_FIELDS -->|cache results| CACHE
    
    USE_CACHE --> DISPLAY[Display Results via UIControl]
    ANALYZE --> DISPLAY
    
    DISPLAY -->|render_result| UI_SYS[ui_control.py]
    DISPLAY -->|export_result| EXPORT[Export Formats
JSON/YAML/CSV/XML/HTML/Markdown]
    
    style Start fill:#4f46e5
    style CMD fill:#14b8a6
    style CACHE fill:#f59e0b
    style PARSER fill:#22c55e
    style UI_SYS fill:#ec4899
```

## Calling Relationships

### Primary Call Chain
1. **CLI → bag_manager.py**: User commands initiate operations
2. **bag_manager.py → analyzer.py**: Request async analysis with caching
3. **analyzer.py → parser.py**: Parse bag file using rosbags
4. **analyzer.py → cache.py**: Store/fetch analysis results
5. **bag_manager.py → ui_control.py**: Display progress and results

### Detailed Call Flow

#### Bag Inspection Flow
```
CLI.inspect_bag() → bag_manager.inspect_bag() 
                → BagAnalyzer.analyze_bag_async() 
                → RosbagsBagParser.get_comprehensive_bag_info()
                → UnifiedCache.get() / UnifiedCache.put()
                → UIControl.display_inspection_result()
```

#### Bag Extraction Flow
```
CLI.extract_topics() → bag_manager.extract_bag()
                   → BagAnalyzer.analyze_bag_async() [optional]
                   → RosbagsBagParser.filter_bag()
                   → UIControl.extraction_progress()
                   → BagValidator.validate_bag()
```

#### Caching Flow
```
Any Component → UnifiedCache.get(key)
             → MemoryCache.get() [512MB LRU]
             → FileCache.get() [2GB SQLite] 
             → Performance analysis and optimization
```

## Component Interaction Sequence

```mermaid
sequenceDiagram
    participant CLI
    participant bag_manager
    participant BagAnalyzer
    participant RosbagsBagParser
    participant UnifiedCache
    participant UIControl
    
    CLI->>bag_manager: extract_bag(bag_path, topics)
    bag_manager->>UnifiedCache: get(analysis_key)
    alt Cache Miss
        bag_manager->>BagAnalyzer: analyze_bag_async(bag_path)
        BagAnalyzer->>UnifiedCache: get(analysis_key)
        alt Cache Miss
            BagAnalyzer->>RosbagsBagParser: get_comprehensive_bag_info(bag_path)
            RosbagsBagParser->>RosbagsBagParser: Single-pass analysis
            RosbagsBagParser-->>BagAnalyzer: ComprehensiveBagInfo
            BagAnalyzer->>UnifiedCache: put(analysis_key, result, ttl=3600)
        else Cache Hit
            UnifiedCache-->>BagAnalyzer: Cached AnalysisResult
        end
        BagAnalyzer-->>bag_manager: AnalysisResult
    else Cache Hit
        UnifiedCache-->>bag_manager: Cached AnalysisResult
    end
    
    bag_manager->>RosbagsBagParser: filter_bag(input, output, topics)
    bag_manager->>UIControl: extraction_progress(description)
    RosbagsBagParser-->>bag_manager: Extraction complete
    bag_manager->>BagValidator: validate_bag(output)
    bag_manager->>UIControl: display_extraction_result(result)
```

## Performance Optimizations

### Memory Management
- **Chunked Processing**: 10,000 messages per chunk to prevent memory overflow
- **Memory Limits**: 64MB per chunk, 512MB memory cache
- **Streaming Processing**: Process messages in streaming fashion

### Caching Strategy
- **Multi-Level Cache**: Memory (fast) + File (persistent)
- **Smart TTL**: 5min for bag info, 1hr for analysis results
- **Cache Warming**: Preheat based on access patterns
- **Eviction Policy**: LRU with size-based eviction

### Async Processing
- **ThreadPoolExecutor**: 4 worker threads for parallel operations
- **Non-blocking I/O**: All file operations use async patterns
- **Progress Callbacks**: Real-time progress updates

## Error Handling

### Validation Layer
- **Bag Health Checks**: Validate extracted files
- **Format Validation**: Ensure rosbags compatibility
- **Compression Checks**: Validate BZ2/LZ4 availability

### Error Recovery
- **Graceful Degradation**: Fallback to uncached processing
- **Partial Results**: Return available data on errors
- **Comprehensive Logging**: Detailed error tracking and reporting

## Integration Points

### External Dependencies
- **rosbags**: High-performance ROS bag processing
- **rich**: Terminal UI and progress bars
- **asyncio**: Async processing framework
- **SQLite**: File-based caching

### Compatibility
- **ROS1**: Full compatibility with ROS1 bag formats
- **Python 3.8+**: Modern Python features
- **Cross-Platform**: Windows, macOS, Linux support

## Configuration

### Cache Settings
- Memory Cache: 512MB (configurable)
- File Cache: 2GB (configurable)
- Cache Directory: System temp + `rose_cache`

### Processing Settings
- Thread Count: 4 workers (configurable)
- Chunk Size: 10,000 messages (configurable)
- Memory Limit: 64MB per chunk (configurable)

This architecture provides a robust, scalable foundation for ROS bag file processing with excellent performance characteristics and user experience.