# Rose Headless Mode Guide

## Overview

Rose CLI now operates in **pure headless mode**, emitting structured NDJSON (Newline-Delimited JSON) events to `stdout`. This makes it easy to integrate Rose with frontend applications, scripts, and automation tools.

## Quick Start

All Rose commands emit NDJSON events. Each line is a complete JSON object:

```bash
$ rose cache
{"event":"data","timestamp":"2025-10-08T13:24:06.822Z","payload":{...},"context":{"command":"cache"},"protocol":{"name":"rose.ndjson","version":"1.0"}}
{"event":"done","timestamp":"2025-10-08T13:24:06.822Z","payload":{"summary":{...}},"context":{"command":"cache"},"protocol":{"name":"rose.ndjson","version":"1.0"}}
```

## Event Types

Rose emits 4 types of events:

### 1. `progress` - Progress Updates
```json
{
  "event": "progress",
  "timestamp": "2025-10-08T10:00:00.123Z",
  "payload": {
    "percent": 75.5,
    "message": "Processing files",
    "step": 3,
    "total_steps": 4
  },
  "context": {"command": "load"},
  "protocol": {"name": "rose.ndjson", "version": "1.0"}
}
```

### 2. `data` - Structured Data Output
```json
{
  "event": "data",
  "timestamp": "2025-10-08T10:00:00.456Z",
  "payload": {
    "label": "found_bags",
    "data": [
      {"path": "a.bag", "size_mb": 12.3},
      {"path": "b.bag", "size_mb": 45.6}
    ],
    "count": 2
  },
  "context": {"command": "load"},
  "protocol": {"name": "rose.ndjson", "version": "1.0"}
}
```

### 3. `done` - Success Completion
```json
{
  "event": "done",
  "timestamp": "2025-10-08T10:00:05.789Z",
  "payload": {
    "summary": {
      "processed": 10,
      "succeeded": 8,
      "failed": 2,
      "elapsed_time": 4.12
    }
  },
  "context": {"command": "load"},
  "protocol": {"name": "rose.ndjson", "version": "1.0"}
}
```

### 4. `error` - Error Events
```json
{
  "event": "error",
  "timestamp": "2025-10-08T10:00:02.345Z",
  "payload": {
    "code": "BAG_NOT_FOUND",
    "message": "Bag file not found: demo.bag",
    "details": {
      "path": "/path/demo.bag",
      "suggestions": ["Check file path", "Ensure file exists"]
    }
  },
  "context": {"command": "load"},
  "protocol": {"name": "rose.ndjson", "version": "1.0"}
}
```

## Protocol Guarantees

1. **Every execution ends with `done` or `error`**
2. **All events are valid JSON** (one per line)
3. **Progress is monotonic** (`percent` only increases)
4. **Timestamps are UTC** in ISO8601 format
5. **No mixed output** - only NDJSON on `stdout`, logs go to `stderr`

## Parsing Examples

### Python

```python
import sys
import json

for line in sys.stdin:
    if not line.strip():
        continue
    
    event = json.loads(line)
    
    if event['event'] == 'progress':
        print(f"Progress: {event['payload']['percent']:.1f}%")
    
    elif event['event'] == 'data':
        label = event['payload']['label']
        data = event['payload']['data']
        print(f"Data ({label}): {data}")
    
    elif event['event'] == 'done':
        print(f"Success: {event['payload']['summary']}")
        break
    
    elif event['event'] == 'error':
        print(f"Error: {event['payload']['code']} - {event['payload']['message']}")
        sys.exit(1)
```

### JavaScript/Node.js

```javascript
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

rl.on('line', (line) => {
  if (!line.trim()) return;
  
  const event = JSON.parse(line);
  
  switch (event.event) {
    case 'progress':
      console.log(`Progress: ${event.payload.percent}%`);
      break;
    
    case 'data':
      console.log(`Data (${event.payload.label}):`, event.payload.data);
      break;
    
    case 'done':
      console.log('Success:', event.payload.summary);
      process.exit(0);
    
    case 'error':
      console.error(`Error: ${event.payload.code} - ${event.payload.message}`);
      process.exit(1);
  }
});
```

### Bash/Shell

```bash
#!/bin/bash

rose load "*.bag" | while IFS= read -r line; do
    event=$(echo "$line" | jq -r '.event')
    
    case "$event" in
        progress)
            percent=$(echo "$line" | jq -r '.payload.percent')
            echo "Progress: $percent%"
            ;;
        
        data)
            label=$(echo "$line" | jq -r '.payload.label')
            echo "Data: $label"
            ;;
        
        done)
            echo "Success!"
            break
            ;;
        
        error)
            code=$(echo "$line" | jq -r '.payload.code')
            message=$(echo "$line" | jq -r '.payload.message')
            echo "Error: $code - $message"
            exit 1
            ;;
    esac
done
```

## Command-Specific Data Labels

Each command emits different data labels:

### `rose load`
- `found_bags`: List of discovered bag files
- `load_plan`: Loading configuration
- `results`: Per-file loading results

### `rose inspect`
- `metadata`: Bag file metadata
- `topics`: Topic list with statistics
- `fields`: Field analysis (if `--show-fields`)

### `rose extract`
- `found_bags`: List of bags to extract
- `topics`: Selected topics
- `extraction_plan`: Extraction configuration
- `results`: Per-file extraction results

### `rose compress`
- `found_bags`: List of bags to compress
- `compression_plan`: Compression configuration
- `results`: Per-file compression results with ratios

### `rose cache`
- `cache_info`: Cache statistics and entries

## Exit Codes

- `0`: Success (always accompanied by `done` event)
- `1`: Error (always accompanied by `error` event)

## Common Patterns

### Wait for Completion

```python
def run_rose_command(cmd):
    import subprocess
    import json
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    for line in process.stdout:
        event = json.loads(line)
        
        if event['event'] == 'done':
            return event['payload']['summary']
        
        elif event['event'] == 'error':
            raise Exception(f"{event['payload']['code']}: {event['payload']['message']}")
    
    raise Exception("Command did not complete properly")
```

### Extract All Data Events

```python
def get_all_data(cmd):
    import subprocess
    import json
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    data_events = {}
    for line in result.stdout.splitlines():
        event = json.loads(line)
        if event['event'] == 'data':
            label = event['payload']['label']
            data_events[label] = event['payload']['data']
    
    return data_events
```

## Migration from Previous Versions

If you were using Rose with rich/ANSI output:

**Before:**
```bash
$ rose load demo.bag
Found 1 bag file(s):
  demo.bag
Loading 1 bag file(s) with 4 worker(s) (quick)...
✓ Loaded demo.bag
Ready: 1 bag(s) available for inspect and extract commands
```

**Now:**
```bash
$ rose load demo.bag
{"event":"data","timestamp":"...","payload":{"label":"found_bags","data":[{"path":"demo.bag","size_mb":12.3}],...},...}
{"event":"progress","timestamp":"...","payload":{"percent":0.0,"message":"Submitting demo.bag"},...}
{"event":"done","timestamp":"...","payload":{"summary":{"loaded_files":1,"total_ready":1}},...}
```

Use a parser script to display human-friendly output if needed.

## Frontend Integration

### React Example

```jsx
import { useState, useEffect } from 'react';

function RoseBagLoader({ bagPath }) {
  const [progress, setProgress] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    const proc = spawn('rose', ['load', bagPath]);
    
    proc.stdout.on('data', (chunk) => {
      const lines = chunk.toString().split('\n');
      
      lines.forEach(line => {
        if (!line.trim()) return;
        
        const event = JSON.parse(line);
        
        switch (event.event) {
          case 'progress':
            setProgress(event.payload.percent);
            break;
          
          case 'data':
            if (event.payload.label === 'results') {
              setData(event.payload.data);
            }
            break;
          
          case 'error':
            setError(event.payload.message);
            break;
        }
      });
    });
  }, [bagPath]);
  
  return (
    <div>
      {error ? (
        <div className="error">{error}</div>
      ) : (
        <>
          <ProgressBar value={progress} />
          {data && <DataTable data={data} />}
        </>
      )}
    </div>
  );
}
```

## Debugging

To see both NDJSON and debug logs:

```bash
# JSON to stdout, logs to stderr
rose load demo.bag 2> debug.log

# Pretty-print JSON for manual inspection
rose load demo.bag | jq
```

## Protocol Version

Current protocol version: **v1.0** (`rose.ndjson`)

The protocol is designed to be backward-compatible. Future versions will add optional fields but maintain the core structure.

## Additional Resources

- [Full Protocol Specification](HEADLESS_ENGINE_DESIGN.md)
- [Verification Report](VERIFICATION_REPORT.md)
- [API Reference](HEADLESS_ENGINE_DESIGN.md#eventemitter-api-reference)

