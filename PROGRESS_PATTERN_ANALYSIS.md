# Rose CLI Progress Payload Design Specification

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Progress Modes](#progress-modes)
3. [Design Rationale](#design-rationale)
4. [Payload Examples](#payload-examples)
5. [EventEmitter API](#eventemitter-api-updates)
6. [Command Classification](#command-classification)
7. [Command-Specific Patterns](#command-specific-progress-patterns)
8. [Summary](#summary)

---

## Executive Summary

This document specifies the standardized progress reporting payload structure for Rose CLI's headless mode. The design eliminates the `percent` field (delegating calculation to clients), introduces explicit `mode` indicators, and provides semantic field naming to support three distinct progress patterns:

1. **Stage Mode**: Phase-based execution (stage x of y) with optional heartbeat
2. **Count Mode**: Item-based processing (item x of y) with known totals
3. **Heartbeat Mode**: Indeterminate progress with periodic keep-alive signals

**Key Design Decisions**:
- Backend reports **state**, clients decide **presentation**
- Semantic field names: `current`/`total` for items, `stage_index`/`total_stages` for phases
- Unified heartbeat mechanism: `current` without `total` in any mode

---

## Progress Modes

### Mode 1: Stage Mode

**Characteristics**:
- Phase-based execution with uncertain duration per phase
- Clear boundaries between stages
- Optional heartbeat using incremental counter within stage
- No predictable item count

**Use Cases**: Validation, initialization, metadata analysis

**Payload Structure**:
```python
{
    "mode": "stage",
    "message": "Analyzing metadata",
    "stage": "metadata_analysis",     # Stage identifier
    "stage_index": 2,                 # Current stage (1-based)
    "total_stages": 5,                # Total stages
    "current": 15,                    # Optional: heartbeat counter
    "elapsed": 45.3                   # Optional: elapsed time
}
```

### Mode 2: Count Mode

**Characteristics**:
- Known total count and current progress
- Updates after each item completion
- Clients can calculate percentage: `(current / total) * 100`
- Predictable progress trajectory

**Use Cases**: Batch file processing, iterative operations

**Payload Structure**:
```python
{
    "mode": "count",
    "message": "Loaded bag3.bag",
    "current": 6,                     # Current item (semantic: not "step")
    "total": 10,                      # Total items (semantic: not "total_steps")
    "elapsed": 12.5                   # Optional: elapsed time
}
```

### Mode 3: Heartbeat Mode

**Characteristics**:
- Indeterminate progress
- Periodic updates to indicate "still alive"
- No percentage calculation possible
- Used for operations with unknown duration

**Use Cases**: Long-running operations without measurable progress

**Payload Structure**:
```python
{
    "mode": "heartbeat",
    "message": "Processing (still running...)",
    "current": 42,                    # Just a counter, no total
    "elapsed": 120.0                  # Optional: elapsed time
}
```

---

## Command Classification

| Command | File | Concurrent | Primary Mode | Secondary Mode |
|---------|------|------------|--------------|----------------|
| **load** | load.py | ✅ Yes | Count | Stage (discovery) |
| **extract** | extract.py | ✅ Yes | Count | Stage (preparation) |
| **compress** | compress.py | ✅ Yes | Count | Stage + Heartbeat |
| **inspect** | inspect.py | ❌ No | Stage | - |
| **cache** | cache.py | ❌ No | Stage | Count (optional) |

---

## Payload Examples

### Stage Mode: Sequential Phases

```python
# Pure stage progression
emit_progress(
    mode="stage",
    stage="validation",
    stage_index=1,
    total_stages=4,
    message="Validating input"
)

emit_progress(
    mode="stage",
    stage="analysis",
    stage_index=2,
    total_stages=4,
    message="Analyzing metadata"
)
```

### Stage Mode: With Heartbeat

```python
# Long-running stage with periodic heartbeat
heartbeat_counter = 0
while processing_large_file:
    if should_emit_heartbeat():
        heartbeat_counter += 1
        emit_progress(
            mode="stage",
            stage="compression",
            stage_index=3,
            total_stages=4,
            current=heartbeat_counter,  # Proof of life
            message="Compressing... (still running)",
            elapsed=45.3
        )
```

### Count Mode: Item Processing

```python
# Processing known number of items
total_files = 10
for i, file in enumerate(files, 1):
    process_file(file)
    emit_progress(
        mode="count",
        current=i,
        total=total_files,
        message=f"Processed {file.name}",
        elapsed=time.time() - start
    )
```

### Count Mode: 2-Phase Concurrent

```python
# Concurrent processing with submit + execute phases
total_items = len(bags) * 2

# Phase 1: Queue submission (fast)
for i, bag in enumerate(bags, 1):
    submit_to_pool(bag)
    emit_progress(
        mode="count",
        current=i,
        total=total_items,
        message=f"Queued {bag}"
    )

# Phase 2: Result collection (slow)
for i, result in enumerate(completed, len(bags) + 1):
    emit_progress(
        mode="count",
        current=i,
        total=total_items,
        message=f"Completed {result}",
        elapsed=elapsed
    )
```

### Heartbeat Mode: Indeterminate Duration

```python
# Unknown duration, just prove we're alive
counter = 0
while operation_continues():
    counter += 1
    emit_progress(
        mode="heartbeat",
        current=counter,
        message="Processing... (indeterminate)",
        elapsed=elapsed
    )
    time.sleep(3)  # Heartbeat interval
```

---

## EventEmitter API Updates

### Current API
```python
def emit_progress(
    self,
    percent: float,
    message: str = "",
    step: Optional[int] = None,
    total_steps: Optional[int] = None
):
    ...
```

### Proposed API
```python
def emit_progress(
    self,
    message: str,
    mode: Literal["stage", "count", "heartbeat"],
    
    # Stage mode fields
    stage: Optional[str] = None,
    stage_index: Optional[int] = None,
    total_stages: Optional[int] = None,
    
    # Count mode fields
    current: Optional[int] = None,
    total: Optional[int] = None,
    
    # Optional fields
    elapsed: Optional[float] = None
):
    """
    Emit progress event with standardized payload.
    
    Args:
        message: Human-readable status message
        mode: Progress mode (stage/count/heartbeat)
        stage: Stage identifier for stage mode
        stage_index: Current stage index (1-based) for stage mode
        total_stages: Total number of stages for stage mode
        current: Current item count for count/heartbeat mode
        total: Total item count for count mode
        elapsed: Elapsed time in seconds
        
    Examples:
        # Stage mode
        emit_progress("Analyzing metadata", mode="stage", 
                     stage="analysis", stage_index=2, total_stages=5)
        
        # Count mode
        emit_progress("Loaded bag3.bag", mode="count",
                     current=3, total=10, elapsed=5.2)
        
        # Stage mode with heartbeat
        emit_progress("Compressing (running...)", mode="stage",
                     stage="compression", stage_index=3, total_stages=5,
                     current=15, elapsed=45.0)
    """
    payload = {
        "message": message,
        "mode": mode
    }
    
    if stage is not None:
        payload["stage"] = stage
    if stage_index is not None:
        payload["stage_index"] = stage_index
    if total_stages is not None:
        payload["total_stages"] = total_stages
    if current is not None:
        payload["current"] = current
    if total is not None:
        payload["total"] = total
    if elapsed is not None:
        payload["elapsed"] = elapsed
    
    self._emit_event(EventType.PROGRESS, payload)
```

---

## Migration Strategy

### Phase 1: Add New API (Backward Compatible)

Keep existing `emit_progress(percent, message, step, total_steps)` and add new signature.

### Phase 2: Update Commands One by One

Priority order:
1. **compress**: Needs heartbeat urgently
2. **cache**: Missing progress entirely
3. **load, extract**: Already good, just update API
4. **inspect**: Optional enhancement

### Phase 3: Deprecate Old API

After all commands migrated, remove old signature.

---

## Design Rationale

### Why No `percent` Field?

**Separation of Concerns**:
- Backend knows the progress **state** (which stage, how many items)
- Client decides how to **visualize** that state (percentage, bar, spinner)
- Different clients may calculate percentage differently

**Examples**:
- Terminal UI: May show "Stage 2/5" without percentage
- Web UI: May calculate `(2/5) * 100 = 40%` for progress bar
- API consumer: May use raw numbers for custom logic

**Client-side calculation** (if needed):
- Stage mode: `(stage_index / total_stages) * 100`
- Count mode: `(current / total) * 100`
- Heartbeat mode: No percentage applicable

### Why `current`/`total` Instead of `step`/`total_steps`?

**Semantic Clarity**:
- `step` implies procedural execution (step 1, step 2, step 3)
- `current` implies item processing (item 6 of 10)

**Count mode semantics**: "Processing **item** 6 **of** 10"
- More natural for: files, bags, entries, records
- `current=6, total=10` reads better than `step=6, total_steps=10`

**Stage mode semantics**: "In **stage** 2 **of** 5"
- `stage_index=2, total_stages=5` is explicit
- No confusion with count mode

### Why `current` in Stage Mode for Heartbeat?

**Problem**: Long-running stage with no item count
- Example: Compressing a single large file (30+ seconds)
- Client needs proof that process is still alive

**Solution**: Incremental `current` counter without `total`
```python
# Stage 3 is ongoing, but we prove we're alive
emitter.emit_progress(
    mode="stage",
    stage_index=3,
    total_stages=5,
    current=15,  # Increments every 3 seconds
    message="Compressing... (still running)"
)
```

**Benefits**:
- Stage context: "In stage 3/5"
- Heartbeat proof: `current` increments show activity
- No misleading percentage: We don't know when stage 3 will finish
- Unified field: Same `current` field used in both count and heartbeat contexts

---

## Command-Specific Progress Patterns

### load Command

**Pattern**: Stage → Count (2-phase)

```python
# Stage 1: Discovery (fast)
emit_progress(mode="stage", stage="discovery", stage_index=1, total_stages=2, 
              message="Finding bag files")

# Stage 2: Loading (count mode, 2-phase concurrent)
total_items = len(bags) * 2  # Submit phase + Execute phase

# Phase 1: Submit (fast)
for i in range(len(bags)):
    emit_progress(mode="count", current=i+1, total=total_items,
                  message=f"Queued {bags[i]}")

# Phase 2: Execute (variable duration)
for i in range(len(bags), total_items):
    emit_progress(mode="count", current=i+1, total=total_items,
                  message=f"Completed {result.name}", elapsed=elapsed)
```

### extract Command

**Pattern**: Multi-stage → Count (2-phase)

```python
# Stages 1-3: Preparation (fast)
emit_progress(mode="stage", stage="discovery", stage_index=1, total_stages=4,
              message="Finding bag files")
emit_progress(mode="stage", stage="cache_check", stage_index=2, total_stages=4,
              message="Checking cache")
emit_progress(mode="stage", stage="topic_analysis", stage_index=3, total_stages=4,
              message="Analyzing topics")

# Stage 4: Extraction (count mode, 2-phase concurrent)
total_items = len(bags) * 2
for i, bag in enumerate(bags):
    emit_progress(mode="count", current=i+1, total=total_items,
                  message=f"Queued {bag}")
for i, result in enumerate(completed, len(bags)+1):
    emit_progress(mode="count", current=i, total=total_items,
                  message=f"Extracted {result}", elapsed=elapsed)
```

### compress Command

**Pattern**: Multi-stage → Count with Heartbeat

```python
# Stages 1-2: Preparation (fast)
emit_progress(mode="stage", stage="discovery", stage_index=1, total_stages=3,
              message="Finding bag files")
emit_progress(mode="stage", stage="validation", stage_index=2, total_stages=3,
              message="Checking cache")

# Stage 3: Compression (stage mode with heartbeat)
# Option A: If processing one large file
heartbeat_counter = 0
while compressing:
    if time_for_heartbeat:
        heartbeat_counter += 1
        emit_progress(mode="stage", stage="compression", 
                      stage_index=3, total_stages=3,
                      current=heartbeat_counter,
                      message="Compressing... (still running)",
                      elapsed=elapsed)

# Option B: If processing multiple files (count mode)
total_items = len(bags) * 2
for i, bag in enumerate(bags):
    emit_progress(mode="count", current=i+1, total=total_items,
                  message=f"Queued {bag}")
for i, result in enumerate(completed, len(bags)+1):
    emit_progress(mode="count", current=i, total=total_items,
                  message=f"Compressed {result}", elapsed=elapsed)
```

### inspect Command

**Pattern**: Pure stage mode (sequential)

```python
stages = [
    ("start", "Starting inspection"),
    ("refresh", "Refreshing statistics"),      # Optional
    ("metadata", "Analyzing metadata"),
    ("topics", "Analyzing topics"),
    ("fields", "Analyzing fields")             # Optional
]

for idx, (stage_name, message) in enumerate(stages, 1):
    emit_progress(mode="stage", stage=stage_name,
                  stage_index=idx, total_stages=len(stages),
                  message=message)
    # Do work...
    perform_stage_work(stage_name)
```

### cache Command

**Pattern**: Adaptive (stage for small, count for large)

```python
# Threshold-based mode selection
entries = get_all_entries()

if len(entries) <= 10:
    # Stage mode for few entries (fast enough)
    emit_progress(mode="stage", stage="processing", 
                  stage_index=1, total_stages=2,
                  message="Processing entries")
    process_all(entries)
    
    emit_progress(mode="stage", stage="writing",
                  stage_index=2, total_stages=2, 
                  message="Writing output")
    write_output()
else:
    # Count mode for many entries (show progress)
    for i, entry in enumerate(entries, 1):
        process_entry(entry)
        emit_progress(mode="count", current=i, total=len(entries),
                      message=f"Processed entry {i}")
```

---

## Summary

### Core Design Principles

| Principle | Rationale |
|-----------|-----------|
| **No `percent` field** | Backend reports state, client decides presentation |
| **Semantic naming** | `current`/`total` for items, `stage_index`/`total_stages` for phases |
| **Explicit `mode`** | Eliminates ambiguity, enables validation |
| **Unified heartbeat** | `current` without `total` works in any mode |
| **Adaptive patterns** | Choose mode based on operation characteristics |

### Payload Specification

#### Required Fields (All Modes)

```python
{
    "mode": "stage" | "count" | "heartbeat",  # REQUIRED
    "message": str                              # REQUIRED
}
```

#### Mode-Specific Required Fields

| Mode | Required | Optional |
|------|----------|----------|
| **stage** | `stage_index`, `total_stages` | `stage`, `current`, `elapsed` |
| **count** | `current`, `total` | `elapsed` |
| **heartbeat** | `current` | `elapsed` |

#### Field Semantics

- `stage_index` / `total_stages`: Phase progression (1-based)
- `current` / `total`: Item counting (1-based for current)
- `current` (alone): Heartbeat counter or proof-of-life
- `elapsed`: Seconds since operation start
- `stage`: String identifier for the stage (e.g., "validation", "compression")

### Implementation Priority

| Priority | Command | Reason |
|----------|---------|--------|
| **P0** | compress | Needs heartbeat for long operations |
| **P1** | cache | Missing progress entirely |
| **P2** | load, extract | Update to new API, already functional |
| **P3** | inspect | Optional enhancement |

### Migration Strategy

1. **Add new API** (backward compatible): Keep old `emit_progress(percent, ...)` signature
2. **Update commands** one by one: Follow priority order above
3. **Deprecate old API**: Remove after all commands migrated

---

**Document Version**: 2.0  
**Date**: 2025-10-09  
**Status**: Design Specification  
**Scope**: Rose CLI Headless Mode Progress Reporting
