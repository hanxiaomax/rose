# Rose Interactive Environment Help

## Welcome to Rose Interactive Environment

Rose Interactive Environment provides a powerful REPL-style interface for ROS bag operations with background task execution, session management, and intelligent auto-completion.

## Core Features

- **Workspace Status Display**: Automatic status display on startup showing working directory, configuration, cache, and session info
- **Natural Language Queries**: Ask questions directly without commands
- **Background Task Execution**: Long operations don't block the interface  
- **Smart Auto-completion**: Tab completion for commands, files, and topics
- **Session Management**: Save and restore your work sessions
- **Context-aware Help**: Get suggestions based on your current state

## Available Commands

### Bag File Operations
- `/load [files]` - Load bag files (supports glob patterns, Tab completion)
- `/extract [args]` - Extract topics from bags (interactive selection)
- `/inspect` - Inspect bag contents and statistics
- `/compress [args]` - Compress bag files (bz2/lz4 options)

### Data Operations
- `/data [export|convert]` - Data operations with CSV/JSON export and conversion
- `/cache [clear|info|list]` - Cache management operations

### Plugin System
- `/plugin [list|info|run|enable|disable|reload|install|uninstall|create]` - Plugin operations

### Session Management
- `/bags` - Manage loaded bags
- `/topics` - Manage topic selection
- `/configuration` - Open Rose configuration file in editor

### System Operations
- `/clear` - Clear console
- `/help` - Show this help
- `/exit` - Exit interactive mode

## Special Symbols

### @ Symbol - Bag File References
- `@<bag_name>` - Reference cached bag files by name
- Examples: `@test.bag`, `@demo3_filtered_20250901_233347`
- Automatically resolves to full path of cached bag files
- Works with both full filename and stem (without extension)

### ! Symbol - Native Shell Commands
- `!<command>` - Execute native bash/shell commands
- Examples: `!ls -la`, `!pwd`, `!find . -name "*.bag"`
- Runs in current working directory
- Shows command output and exit codes

## Usage Tips

1. **Natural Questions**: Just type your question directly
   ```
   > What topics are in this bag?
   > How many messages does /cmd_vel have?
   > Show me the GPS data quality
   ```

2. **Tab Completion**: Use Tab key for auto-completion
   - Command names: `/lo` + Tab → `/load`
   - File paths: `/load test` + Tab → `/load test_data.bag`
   - Cached bags: `@te` + Tab → `@test.bag`

3. **Background Tasks**: Long operations run in background
   ```
   > /load large_dataset.bag    # Runs in background
   > /bags                      # Check loaded bags
   > /topics                    # View selected topics
   ```

4. **Context Awareness**: Commands adapt based on current state
   - If bags are loaded, `/extract` uses them automatically
   - If topics are selected, operations use the selection
   - Session state is preserved across commands

5. **File References**: Multiple ways to reference files
   ```
   > /load *.bag                # Glob patterns
   > /extract @my_data.bag      # Cached bag reference
   > !find . -name "*.bag"      # Shell command
   ```

## Workflow Examples

### Basic Bag Analysis
```
> /load data/*.bag
> What topics are available?
> /inspect
> /bags
```

### Topic Extraction
```
> /load my_data.bag
> /topics                     # Select topics interactively
> /extract                    # Extract selected topics
```

### Data Export
```
> /load sensor_data.bag
> /data export               # Interactive CSV export
> !ls -la *.csv             # Check exported files
```

### Configuration Management
```
> /configuration             # Open config file in editor
> /bags                      # Check loaded bags
```

### Using Special Symbols
```
> /load test_data.bag        # Load a bag file
> @test_data.bag             # Reference it by name later
> !find . -name "*.bag"      # Use shell commands
> /cache list                # See all cached files
```

## Advanced Features

### Plugin System
- List available plugins: `/plugin list`
- Show plugin information: `/plugin info [name]`
- Run custom analysis: `/plugin run [name]`
- Enable/disable plugins: `/plugin enable/disable [name]`
- Install new plugins: `/plugin install [path]`
- Uninstall plugins: `/plugin uninstall [name]`
- Create new plugins: `/plugin create`

### Cache Management
- View cache info: `/cache`
- List cached files: `/cache list`
- Clear old cache: `/cache clear`

### Debugging and Monitoring
- Edit configuration: `/configuration`

## Workspace Information

On startup, Rose displays comprehensive workspace status in the welcome panel:

```
Interactive Environment

Workspace Status:
  Working Directory: /workspaces/rose
  Configuration: rose.config.yaml
  Cache: 3 entries, 2.5 MB
  Loaded Bags: 2 bag(s)
  Selected Topics: 5 topic(s)

Available commands:
  ...
```

This provides instant visibility into:
- Current working directory
- Active configuration file
- Cache size and entries
- Loaded bag files (when present)
- Selected topics (when present)

## Troubleshooting

### Common Issues

1. **Tab completion not working**: Restart the session
2. **Bag file not found**: Use absolute paths or check current directory (shown in startup status)
3. **Long operations stuck**: Check workspace status displayed on startup for loaded bags and topics
4. **Cache issues**: Try `/cache clear` to reset (current cache size shown in startup status)
5. **Configuration not found**: Check the configuration path shown in startup status

### Getting Help

- Type your question naturally: "How do I extract specific topics?"
- Use `/help` for this comprehensive guide
- Check `/bags` and `/topics` for detailed workspace management
- Workspace status is automatically shown on startup and after `/clear`

---

*Rose Interactive Environment - Making ROS bag processing intuitive and powerful*
