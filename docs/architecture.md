# Software Architecture

Rose is designed with a layered architecture focusing on modularity, performance, and aesthetic consistency.

## Overview

The system is divided into three main layers:
1.  **Core Layer**: Handles data processing, caching, and ROS bag interaction.
2.  **CLI Layer**: Provides command-line interface and terminal output styling.
3.  **TUI Layer**: Offers interactive visual inspection using Textual.

## System Diagram

```mermaid
graph TD
    User([User])
    
    subgraph "CLI Layer (Rose)"
        CmdInspect[Inspect Command]
        CmdExtract[Extract Command]
        CmdLoad[Load Command]
    end
    
    subgraph "Core Layer"
        Orchestrator[Pipeline Orchestrator]
        Cache["Unified Cache (Pickle)"]
        BagMgr[Bag Cache Manager]
        Reader["Bag Reader (rosbags)"]
    end
    
    subgraph "TUI Layer"
        InspectApp["InspectApp (Textual)"]
        Widgets["Widgets: Tree, Plot, Timeline"]
    end
    
    User --> CmdInspect
    User --> CmdExtract
    
    CmdInspect --> Orchestrator
    CmdExtract --> Orchestrator
    CmdExtract -.->|Interactive| BagMgr
    
    Orchestrator --> BagMgr
    BagMgr --> Cache
    BagMgr --> Reader
    
    CmdInspect -.->|Interactive| InspectApp
    InspectApp --> BagMgr
    InspectApp --> Widgets
```

## Component Details

### Core Layer

*   **Pipeline Pattern**: All heavy operations (loading, analysis, extraction) are implemented as generator-based pipelines in `roseApp.core.pipeline`. This allows the CLI and TUI to consume events (`LogEvent`, `ProgressEvent`) and render progress in real-time without blocking.
*   **Unified Cache**: To improve performance, bag analysis results (structure, message counts, types) are cached using `roseApp.core.cache`. The cache uses file hashing to ensure validity.
*   **Bag Abstraction**: Rose uses `rosbags` high-level `AnyReader` to support both legacy ROS1 (`.bag`) and ROS2 (`.mcap`) formats without requiring a full ROS environment.

### CLI Layer

*   **Typer & Rich**: Built with `Typer` for argument parsing and `Rich` for beautiful terminal output.
*   **Theme System**: Integrating a "Cassette Futurism" aesthetic, the `Output` class (`roseApp.core.output`) manages consistent coloring and formatting across all commands.

### TUI Layer

*   **Textual Framework**: The interactive inspector is a full TUI application using Textual.
*   **Async Event Handling**: TUI components update asynchronously based on user input and background data loading.
*   **Plotting**: Integration with `plotext` allows for real-time data visualization directly in the terminal.

## Key Workflows

### 1. Inspection Flow (TUI)
1.  **Initial Load**: `rose inspect` checks the cache. If missing, it triggers the Analysis Pipeline.
2.  **Launch**: Once analysis is ready, `InspectApp` is launched with the `ComprehensiveBagInfo`.
3.  **Interaction**: User navigates the message tree. Selecting a numeric field triggers a background read to load the full time-series data for the plot.
4.  **Plotting**: The plot is strictly updated with an "Inverse Pixel" marker technique for high visibility.

### 2. Extraction Flow
1.  **Input Resolution**: Supports glob patterns (`*.bag`).
2.  **Interactive Selection (`-i`)**:
    *   Scans bags for unique topics.
    *   Presents a fuzzy-searchable checkbox list using `InquirerPy`.
3.  **Execution**: The `extract_orchestrator` filters messages based on selection and writes to a new bag file (optionally compressed).
