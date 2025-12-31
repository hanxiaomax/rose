
# Configuration Guide

Rose uses a hierarchical configuration system.

## Configuration Priority

1.  **CLI Arguments**: Command-line flags override everything (e.g., `--workers 8`).
2.  **Environment Variables**: Variables starting with `ROSE_` (e.g., `ROSE_PARALLEL_WORKERS=8`).
3.  **Configuration File**: YAML file (`rose.config.yaml`).
4.  **Defaults**: System-defined default values.

## Config File Locations

Rose looks for `rose.config.yaml` in:
1.  Current working directory.
2.  `roseApp/config/rose.config.yaml` (Installation default).
3.  `~/.rose/rose.config.yaml` (User home directory).

## Available Settings

### Performance

*   `parallel_workers`: Number of parallel processes to use. Default: 4.
    *   *Usage*: `rose load` and `rose compress` use this for parallel processing.
*   `memory_limit_mb`: Memory usage limit guideline for buffer operations. Default: 512.


### Logging

*   `log_level`: Verbosity of logs (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Default: `INFO`.
*   `log_to_file`: Write logs to file system. Default: `true`.

### UI

*   `theme_file`: Theme definition file. Default: `rose.theme.default.yaml`.
*   `enable_colors`: Enable colored output. Default: `true`.

### Paths

*   `cache_dir`: Directory for storing cache files. Default: `~/.cache/rose`.
*   `logs_dir`: Directory for storing log files. Default: `logs`.

## Example `rose.config.yaml`

```yaml
parallel_workers: 8
log_level: DEBUG
theme_file: rose.theme.dracula.yaml
```
