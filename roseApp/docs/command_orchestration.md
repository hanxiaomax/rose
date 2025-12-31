# Command Orchestration & Phases

This document details the internal orchestration logic for Rose CLI commands, explaining the distinct phases of execution and the reuse of core "Headless SDK" components.

## Overview

All commands follow a similar **Orchestration Pattern**:
1.  **Discovery**: Find target bags (glob/regex).
2.  **Analysis/Cache Check**: Verify or load bag metadata via `BagCacheManager`.
3.  **Execution**: Perform the primary action (load, extract, compress).
4.  **Reporting**: Yield results to the CLI.

## Shared Core Functions (`roseApp/core/pipeline.py`)

These functions are atomic steps used across multiple commands.

| Generator Step      | Purpose                                                  | Used By                                                |
| :------------------ | :------------------------------------------------------- | :----------------------------------------------------- |
| `step_find_bags`    | Scans filesystem for bags matching pattern               | `load`, `compress`, `extract`                          |
| `step_load_bag`     | Loads a single bag into cache (Quick or Index)           | `load`, `inspect` (interactive), `extract` (auto-load) |
| `step_inspect_bag`  | Checks cache validity, potentially calls `step_load_bag` | `inspect`                                              |
| `step_compress_bag` | Compresses a bag to new format                           | `compress`                                             |
| `step_extract_bag`  | Extracts topics to new bag                               | `extract`                                              |

---

## Detailed Command Phases

### 1. `load` Command
**Goal**: Populate the cache for subsequent fast access.

*   **Orchestrator**: `load_orchestrator`
*   **Phases**:
    1.  **Discovery**: Calls `step_find_bags`.
    2.  **Processing Loop**:
        -   Iterates through found bags.
        -   Calls `step_load_bag(force=False/True, build_index=...)`.
        -   `step_load_bag` manages cache logic internally (skip if valid, load if not).

### 2. `inspect` Command
**Goal**: View details of a *single* bag (High interactivity).

*   **Orchestrator**: `inspect_orchestrator`
*   **Phases**:
    1.  **Validation**: Checks file existence (Single file target).
    2.  **Inspection**: Calls `step_inspect_bag`.
        -   **Sub-Phase: Cache Check**: Checks if valid cache exists.
        -   **Sub-Phase: Conditional Load**:
            -   buffer: If `force=True` or `load_if_missing=True`, calls `step_load_bag`.
            -   Else: Returns `not_cached` status.
    3.  **CLI Interactivity** (Outside Orchestrator):
        -   If `not_cached`, CLI prompts user.
        -   Re-calls orchestrator with `load_if_missing=True` if confirmed.

### 3. `compress` Command
**Goal**: Compress bags to LZ4/BZ2.

*   **Orchestrator**: `compress_orchestrator`
*   **Phases**:
    1.  **Discovery**: Calls `step_find_bags`.
    2.  **Processing Loop**:
        -   Iterates through bags.
        -   Calls `step_compress_bag`.
        -   **Sub-Phase: Metadata Read**:
            -   Needs list of topics to configure compression.
            -   Checks cache first (lightweight).
            -   If miss, performs quick temporary load (no index) to get topic list.
            -   Calls `BagParser.extract` with compression settings.

### 4. `extract` Command
**Goal**: Filter specific topics into a new bag.

*   **Orchestrator**: `extract_orchestrator`
*   **Phases**:
    1.  **Discovery**: Calls `step_find_bags`.
    2.  **Topic Analysis**:
        -   Needs global list of topics to validate user filters.
        -   Iterates all bags to build topic union.
        -   **Auto-Load**: If bag uncached, calls `step_load_bag(build_index=False)` to get metadata.
    3.  **Filter Resolution**: Matches user regex against global topic list.
    4.  **Processing Loop**:
        -   Iterates through bags.
        -   Calls `step_extract_bag` with resolved topic list.

## Orchestration Matrix

| Feature                |  `load`  |     `inspect`      |   `compress`   |          `extract`          |
| :--------------------- | :------: | :----------------: | :------------: | :-------------------------: |
| **Multi-file Support** |    ✅     |     ❌ (Single)     |       ✅        |              ✅              |
| **Cache Dependency**   |   Core   |        Core        |  Optimization  | Critical (Topic resolution) |
| **Auto-Load Logic**    |   N/A    | Interactive Prompt | Temporary Read |       Batch Auto-Load       |
| **Index Building**     | Optional |      Optional      |       No       |             No              |
