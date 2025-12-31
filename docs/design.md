# Detailed Design

This document covers the low-level design of the Rose application, including class structures and sequence diagrams for key workflows.

## Class Design

### Data Models & Cache

Core data models reside in `roseApp.core.model` and form the backbone of the caching system.

```mermaid
classDiagram
    class BagInfo {
        +str path
        +int file_size
        +float file_mtime
        +List~TopicInfo~ topics
        +Dict~str, MsgTypeInfo~ msg_types_info
        +find_message_type(type_name)
    }

    class TopicInfo {
        +str name
        +str message_type
        +int message_count
        +Tuple~float, float~ first_message_time
    }

    class Cache {
        +Path cache_dir
        +get(key)
        +put(key, value)
        +get_bag_analysis(path)
        +put_bag_analysis(path, info)
    }

    class BagCacheManager {
        +Cache cache
        +get_analysis(path)
        +put_analysis(path, info)
    }

    Cache --* BagCacheManager : uses
    BagCacheManager ..> BagInfo : manages
    BagInfo *-- TopicInfo : contains
```

### CLI & Visualization

The CLI uses the `Output` wrapper for consistent theming, while `InspectApp` manages the Textual TUI state.

```mermaid
classDiagram
    class Output {
        +ThemeColors theme
        +Console _console
        +print(msg)
        +error(msg)
        +spinner(msg)
    }

    class InspectApp {
        +ComprehensiveBagInfo bag_info
        +AnyReader reader
        +compose()
        +on_mount()
        +action_focus_tree()
        +_update_plot()
    }

    InspectApp ..> BagInfo : visualizes
```

## Workflows

### 1. Load / Analysis Workflow

When a user runs `rose load` or `rose inspect`, the system ensures metadata is available.

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (Typer)
    participant Orch as Orchestrator
    participant Mgr as BagCacheManager
    participant Cache as Cache
    participant Reader as BagReader (rosbags)

    User->>CLI: rose inspect demo.bag
    CLI->>Orch: inspect_orchestrator(demo.bag)
    Orch->>Mgr: get_analysis(demo.bag)
    Mgr->>Cache: get_bag_analysis(demo.bag)
    
    alt Cache Hit
        Cache-->>Mgr: BagInfo
    else Cache Miss
        Cache-->>Mgr: None
        Mgr-->>Orch: None
        Orch->>Reader: Open & Scan
        Reader-->>Orch: Bag Data
        Orch->>Orch: Build BagInfo
        Orch->>Mgr: put_analysis(info)
        Mgr->>Cache: put_bag_analysis(info)
    end
    
    Orch-->>CLI: yielded Progress/Result
    CLI-->>User: Display TUI
```

### 2. TUI Data Inspection

Interactive data exploration inside `InspectApp`.

```mermaid
sequenceDiagram
    actor User
    participant App as InspectApp
    participant Tree as DataTree
    participant Reader as BagReader
    participant Plot as PlotWidget

    User->>App: Select Topic / Field
    App->>Tree: Highlight Node
    
    alt is numeric field
        App->>Reader: Query Messages (Time Series)
        Reader-->>App: List[Timestamp, Value]
        App->>Plot: update_plot(x, y)
        Plot-->>User: Render Ascii Chart
    else is complex/string
        App->>Plot: Clear / Show "No Numeric Data"
    end
```
