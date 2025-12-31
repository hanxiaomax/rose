
# Theming System

Rose provides a flexible theming system powered by `Rich`.

## Theme Files

Themes are defined in YAML files (e.g., `rose.theme.default.yaml`). You can switch themes by setting `theme_file` in `rose.config.yaml`.

## Semantic Color Roles

Rose uses semantic roles to abstract direct color codes from the UI logic.

*   `primary`: Main brand color.
*   `accent`: Accent color for highlights and progress bars.
*   `success`: Success messages (√).
*   `warning`: Warning messages (!).
*   `error`: Error messages (X).
*   `info`: Informational details.
*   `muted`: De-emphasized text (debug info, previous states).
*   `highlight`: High-contrast text (headers).
*   `path`: File system paths.

## Base16 Support

Rose supports **Base16** theme definitions. If your theme file uses Base16 keys (`base00` - `base0F`), Rose will automatically map them to internal semantic roles.

### Base16 Mapping

| Rose Role   | Base16 Key | Description          |
| :---------- | :--------- | :------------------- |
| `primary`   | `base0D`   | Functions, Blue-ish  |
| `accent`    | `base09`   | Integers, Orange-ish |
| `success`   | `base0B`   | Strings, Green-sh    |
| `warning`   | `base0A`   | Classes, Yellow-ish  |
| `error`     | `base08`   | Variables, Red-ish   |
| `info`      | `base0C`   | Support, Cyan-ish    |
| `muted`     | `base03`   | Comments, Grey       |
| `highlight` | `base06`   | Light Foreground     |
| `path`      | `base0D`   | Same as primary      |

### Example Base16 Theme (YAML)

```yaml
# Rose Theme - Base16 Example
base00: "282828"
base01: "383838"
base02: "505050"
base03: "505050" # Muted
base04: "b0b0b0"
base05: "d0d0d0"
base06: "e0e0e0" # Highlight
base07: "f0f0f0"
base08: "fb4934" # Error
base09: "fe8019" # Accent
base0A: "fabd2f" # Warning
base0B: "b8bb26" # Success
base0C: "8ec07c" # Info
base0D: "83a598" # Primary/Path
base0E: "d3869b"
base0F: "d65d0e"
```

Just drop this into a `.yaml` file and point `theme_file` to it!
