# Detailed Design

This document covers the low-level design of the Rose application, including class structures and sequence diagrams for key workflows.

## Data Models

### Core Models

```mermaid
classDiagram
    class BagInfo {
        +str file_path
        +int file_size
        +float file_mtime
        +List~TopicInfo~ topics
        +Dict~str, MsgTypeInfo~ message_types
        +TimeRange time_range
        +AnalysisLevel analysis_level
        +has_message_index() bool
        +find_message_type(type_name)
    }

    class TopicInfo {
        +str name
        +str message_type
        +int message_count
        +float message_frequency
        +int total_size_bytes
        +List~MessageIndex~ message_index
    }

    class MsgTypeInfo {
        +str name
        +List~FieldInfo~ fields
        +get_all_field_paths() List~str~
    }

    class Cache {
        +Path cache_dir
        +get(key)
        +put(key, value)
        +get_bag_analysis(path)
        +put_bag_analysis(path, info)
    }

    BagInfo *-- TopicInfo : contains
    BagInfo *-- MsgTypeInfo : contains
    Cache ..> BagInfo : manages
```

## TUI Widget Design

### Selection Widgets

```mermaid
classDiagram
    class Answer {
        +str text
        +str id
        +str kind
    }

    class Option {
        +int index
        +Content content
        +str key
        +watch_active()
    }

    class Question {
        +str question
        +List~Answer~ options
        +reactive~int~ selection
        +bool confirmed
        +action_selection_up()
        +action_selection_down()
        +action_confirm()
    }

    class MultiOption {
        +int index
        +Content content
        +reactive~bool~ checked
        +watch_checked()
    }

    class MultiQuestion {
        +str question
        +List~Answer~ options
        +Set~int~ checked_indices
        +action_toggle()
        +action_toggle_next()
        +action_select_all()
        +action_invert_selection()
        +action_confirm()
    }

    Question *-- Option : contains
    Question --> Answer : uses
    MultiQuestion *-- MultiOption : contains
    MultiQuestion --> Answer : uses
```

### PathInput Widget

```mermaid
classDiagram
    class PathInput {
        +str path
        +bool tree_mode
        +bool default_tree_mode
        +Callable validator
        +List~str~ suggestions
        +action_autocomplete()
        +action_toggle_tree()
        +action_cursor_up()
        +action_cursor_down()
        +action_submit()
    }

    class FilteredDirectoryTree {
        +reactive~str~ filter_text
        +filter_paths(paths) List~Path~
        +watch_filter_text()
    }

    class PathInputField {
        +Input field
    }

    PathInput *-- PathInputField : contains
    PathInput *-- FilteredDirectoryTree : contains
    PathInput *-- OptionList : contains
```

## Workflows

### 1. Load / Analysis Workflow

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (Typer)
    participant Orch as Orchestrator
    participant Mgr as BagCacheManager
    participant Cache as Cache
    participant Reader as BagReader

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
    
    Orch-->>CLI: yield Progress/Result
    CLI-->>User: Display TUI
```

### 2. Interactive Selection Flow

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI Command
    participant Dialog as DialogApp
    participant Widget as Question/MultiQuestion
    
    User->>CLI: rose inspect (no args)
    CLI->>Dialog: ask_question() or ask_multi_selection()
    Dialog->>Widget: Mount widget
    
    loop User Navigation
        User->>Widget: Arrow keys / Tab
        Widget->>Widget: Update selection
    end
    
    User->>Widget: Enter (confirm)
    Widget->>Dialog: Post Answers message
    Dialog->>CLI: Return selected Answer(s)
    CLI->>User: Proceed with selection
```

### 3. PathInput File Selection

```mermaid
sequenceDiagram
    actor User
    participant PathInput
    participant Tree as FilteredDirectoryTree
    participant Input as PathInputField
    
    User->>PathInput: Focus
    PathInput->>Tree: Show tree (default mode)
    
    User->>Input: Type filter text
    Input->>PathInput: on_input_changed
    PathInput->>Tree: Update filter_text
    Tree->>Tree: reload() with filter
    
    User->>PathInput: Tab
    PathInput->>Tree: Get cursor_node
    alt Directory selected
        PathInput->>Tree: Navigate into directory
        PathInput->>Input: Update path value
    else File selected
        PathInput->>PathInput: validate_and_submit()
    end
    
    User->>PathInput: Ctrl+T
    PathInput->>PathInput: Toggle tree_mode
    Note over PathInput: Switch between Tree and Suggestions view
```

### 4. TUI Data Inspection

```mermaid
sequenceDiagram
    actor User
    participant App as InspectApp
    participant Tree as DataTree
    participant Reader as BagReader
    participant Plot as PlotWidget

    User->>App: Select Topic
    App->>App: select_topic()
    App->>Reader: Seek to message
    Reader-->>App: Message data
    App->>Tree: Build tree from message
    
    User->>Tree: Select numeric field
    App->>App: Set plot_field
    App->>Reader: Query time series
    Reader-->>App: List[Timestamp, Value]
    App->>Plot: update_plot(x, y)
    Plot-->>User: Render ASCII chart
```

## Key Bindings Summary

### Question Widget

| Key      | Action            |
| -------- | ----------------- |
| `↑/↓`    | Navigate options  |
| `Enter`  | Confirm selection |
| `Escape` | Cancel            |

### MultiQuestion Widget

| Key      | Action                              |
| -------- | ----------------------------------- |
| `↑/↓`    | Navigate options                    |
| `Space`  | Toggle current option               |
| `Tab`    | Toggle + move to next (wrap-around) |
| `Ctrl+A` | Select all                          |
| `Ctrl+I` | Invert selection                    |
| `Enter`  | Confirm selection                   |
| `Escape` | Cancel                              |

### PathInput Widget

| Key      | Action                          |
| -------- | ------------------------------- |
| `↑/↓`    | Navigate suggestions/tree       |
| `Tab`    | Auto-complete / Enter directory |
| `Enter`  | Select file / Enter directory   |
| `Ctrl+T` | Toggle tree/suggestion view     |
| `Escape` | Cancel                          |
