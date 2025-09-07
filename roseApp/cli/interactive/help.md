# Rose Interactive Environment Help

## Welcome to Rose Interactive Environment

Rose Interactive Environment provides a powerful REPL-style interface for ROS bag operations with background task execution, session management, and intelligent auto-completion.

## Core Features

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
- `/data [export|info]` - Data operations with CSV/JSON export
- `/cache [export|clear]` - Cache management operations

### Plugin System
- `/plugin [list|info|run|enable|disable|reload|install|uninstall|create]` - Plugin operations

### Session Management
- `/status` - Show workspace status and running tasks
- `/bags` - Manage loaded bags
- `/topics` - Manage topic selection
- `/workspace` - Workspace operations
- `/note <text>` - Add session note
- `/notes` - Show all session notes
- `/save [filename]` - Save current session
- `/session [filename]` - Load saved session
- `/export <type>` - Export notes/session/results

### System Operations
- `/undo` - Undo last operation
- `/cancel [task_id]` - Cancel running tasks
- `/clear` - Clear console
- `/help` - Show this help
- `/exit` or `/quit` - Exit interactive mode

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

1. **Natural Questions**: Just type your question without /ask
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
   > /status                    # Check progress
   > What's the status?         # Ask naturally
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
> /note Found interesting GPS data
> /status
```

### Topic Extraction
```
> /load my_data.bag
> /topics                     # Select topics interactively
> /extract                    # Extract selected topics
> /note Extracted GPS and IMU data
```

### Data Export
```
> /load sensor_data.bag
> /data export               # Interactive CSV export
> !ls -la *.csv             # Check exported files
```

### Session Management
```
> /load project_bags/*.bag
> /note Starting analysis session
> /save analysis_session
> /export session
```

## 🛠️ Advanced Features

### Plugin System
- List available plugins: `/plugin list`
- Run custom analysis: `/plugin run my_analyzer`
- Install new plugins: `/plugin install /path/to/plugin`

### Cache Management
- View cache status: `/cache`
- Export cache data: `/cache export cache_backup.json`
- Clear old cache: `/cache clear`

### Debugging and Monitoring
- Check running tasks: `/status`
- Cancel long operations: `/cancel`
- View session history: `/notes`
- Undo recent changes: `/undo`

## Troubleshooting

### Common Issues

1. **Tab completion not working**: Restart the session
2. **Bag file not found**: Use absolute paths or check current directory
3. **Long operations stuck**: Use `/cancel` to stop, then `/status` to check
4. **Cache issues**: Try `/cache clear` to reset

### Getting Help

- Type your question naturally: "How do I extract specific topics?"
- Use `/help` for this comprehensive guide
- Check `/status` for current workspace state
- Use `/notes` to review your session history

---

*Rose Interactive Environment - Making ROS bag processing intuitive and powerful* 🌹
