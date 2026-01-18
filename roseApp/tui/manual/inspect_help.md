# Rose Inspector Help

Welcome to the Rose Inspector TUI!

## Navigation

- **Tab Switch**: Click on tabs to switch between Data, Plot, and Help views.
- **Tree Navigation**:
    - `Up/Down`: Navigate tree nodes
    - `Right/Enter`: Expand node
    - `Left`: Collapse node
- **Message Navigation**:
    - `h` or `Left`: Previous message
    - `l` or `Right`: Next message
    - `g`: Jump to specific frame index

## Search & Filtering

- Press `/` to open search.
- Type to find topics (e.g. `gps`, `imu`).
- Select a topic to view its structure and messages.
- You can filter fields using dot notation in search (e.g. `/gps/fix.latitude`).

## Plotting

- Go to **Plot Tab**.
- Navigate to a numeric field in the **Data Tree** and press `Enter`.
- If the field is numeric, it will be plotted automatically.
- *Requirement*: `textual-plotext` must be installed.

## Timeline

- Click anywhere on the timeline bottom bar to jump to that position in the bag.
