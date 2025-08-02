#!/usr/bin/env python3
"""
Inspect command for ROS bag files - Using ResultHandler for rendering and export
"""
import asyncio
from pathlib import Path
from typing import Optional, List

import typer
from ..core.model import AnalysisLevel
from ..core.ui_control import UIControl, OutputFormat, ExportOptions, DisplayConfig, Message
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.cache import create_bag_cache_manager

app = typer.Typer(help="Inspect ROS bag files")


@app.command()
def inspect(
    bag_path: Path = typer.Argument(..., help="Path to the ROS bag file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Filter specific topics"),
    topic_filter: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter topics by pattern"),
    show_fields: bool = typer.Option(False, "--show-fields", help="Show field analysis for messages"),
    sort_by: str = typer.Option("size", "--sort", help="Sort topics by (name, count, frequency, size)"),
    reverse_sort: bool = typer.Option(False, "--reverse", help="Reverse sort order"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit number of topics shown"),
    as_format: str = typer.Option("table", "--as", help="Output format (table, list, summary, json, yaml, csv, xml, html, markdown)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Show debug logs"),

):
    """
    Inspect a ROS bag file and display comprehensive analysis
    
    NOTE: The bag file must be loaded into cache first using 'rose load <bag_file>'
    
    This command uses cached bag analysis for fast inspection without progress bars.
    """
    # Use UIControl for unified output management
    ui = UIControl()
    
    # Validate bag file exists
    if not bag_path.exists():
        ui.show_error(f"Bag file not found: {bag_path}")
        raise typer.Exit(1)
    
    # Check if bag is loaded in cache
    cache_manager = create_bag_cache_manager()
    cached_entry = cache_manager.get_analysis(bag_path)
    
    if not cached_entry or not cached_entry.is_valid(bag_path):
        ui.show_error(f"Bag file '{bag_path}' is not loaded in cache.")
        ui.get_console().print(f"[yellow]Please load the bag first using:[/yellow] [bold]rose load {bag_path}[/bold]")
        raise typer.Exit(1)
    
    # Convert string format to enum
    try:
        output_format = OutputFormat(as_format.lower())
    except ValueError:
        supported = [fmt.value for fmt in OutputFormat]
        ui.show_unsupported_format_error(as_format, supported)
        raise typer.Exit(1)
    
    # Configure logging based on debug flag
    if not debug:
        # Suppress logs in standard output unless debug mode
        import logging
        logging.getLogger().setLevel(logging.CRITICAL)
        logging.getLogger('cache').setLevel(logging.CRITICAL)
        logging.getLogger('root').setLevel(logging.CRITICAL)
    
    # Create options object (simplified since we're using cache directly)
    class SimpleInspectOptions:
        def __init__(self):
            self.topics = topics
            self.topic_filter = topic_filter
            self.show_fields = show_fields
            self.sort_by = sort_by
            self.reverse_sort = reverse_sort
            self.limit = limit
            self.output_format = output_format
            self.output_file = output
            self.verbose = verbose
    
    options = SimpleInspectOptions()
    
    # Run the async inspection
    asyncio.run(_run_inspect(bag_path, options, debug))


async def _run_inspect(bag_path: Path, options, debug: bool = False):
    """Run the bag inspection asynchronously using BagManager and ResultHandler"""
    
    # Use UIControl for unified output management
    ui = UIControl()
    console = ui.get_console()
    
    # No longer need BagManager - we use cache directly
    
    try:
        # Get cached bag analysis directly
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(bag_path)
        
        if not cached_entry or not cached_entry.is_valid(bag_path):
            ui.show_error(f"Bag file '{bag_path}' is not loaded in cache.")
            console.print(f"[yellow]Please load the bag first using:[/yellow] [bold]rose load {bag_path}[/bold]")
            raise typer.Exit(1)
        
        console.print("[dim]Using cached bag analysis...[/dim]")
        
        # Convert cached bag info to result format expected by UI
        bag_info = cached_entry.bag_info
        
        # Calculate total messages from message_counts
        total_messages = 0
        if bag_info.message_counts:
            total_messages = sum(bag_info.message_counts.values())
        elif bag_info.total_messages:
            total_messages = bag_info.total_messages
        
        # Get file size
        file_size = 0
        try:
            file_size = bag_path.stat().st_size
        except:
            pass
        
        # Create the result structure expected by UIControl
        result = {
            'file_path': str(bag_path),
            'topics': [],
            'duration': bag_info.duration_seconds or 0,
            'analysis_level': bag_info.analysis_level.value if bag_info.analysis_level else 'none',
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'file_size': file_size,
                'topics_count': len(bag_info.topics) if bag_info.topics else 0,
                'total_messages': total_messages,
                'duration_seconds': bag_info.duration_seconds or 0,
                'analysis_time': 0.0,  # From cache, so analysis time is 0
                'cached': True
            }
        }
        
        # Convert topics to expected format
        if bag_info.topics:
            for i, topic_name in enumerate(bag_info.topics):
                topic_info = {
                    'name': topic_name,
                    'message_type': bag_info.connections.get(topic_name, 'unknown') if bag_info.connections else 'unknown',
                    'message_count': bag_info.message_counts.get(topic_name, 0) if bag_info.message_counts else 0,
                    'frequency': 0.0,  # Calculate if needed
                    'size_bytes': bag_info.topic_sizes.get(topic_name, 0) if bag_info.topic_sizes else 0
                }
                
                # Calculate frequency if we have duration and message count
                if bag_info.duration_seconds and topic_info['message_count'] > 0:
                    topic_info['frequency'] = topic_info['message_count'] / bag_info.duration_seconds
                
                # Add field analysis if available
                if options.show_fields and bag_info.message_fields:
                    msg_type = topic_info['message_type']
                    if msg_type in bag_info.message_fields:
                        topic_info['field_paths'] = bag_info.message_fields[msg_type]
                
                result['topics'].append(topic_info)
        
        # Add field analysis if requested
        if options.show_fields and bag_info.message_fields and bag_info.connections:
            # Convert message_fields structure to topic-based field_analysis
            field_analysis = {}
            for topic_name, msg_type in bag_info.connections.items():
                if msg_type in bag_info.message_fields:
                    # Extract hierarchical field paths from the message fields structure
                    field_paths = _build_hierarchical_field_paths(bag_info.message_fields, msg_type)
                    
                    if field_paths:
                        field_analysis[topic_name] = {
                            'message_type': msg_type,
                            'field_paths': sorted(field_paths)
                        }
            
            if field_analysis:
                result['field_analysis'] = field_analysis
        
        # Determine if we should export to file or render to console
        if options.output_file:
            # Export to file
            export_options = ExportOptions(
                format=options.output_format,
                output_file=options.output_file,
                pretty=True,
                include_metadata=True
            )
            
            success = UIControl.export_result(result, export_options)
            if not success:
                ui.show_export_failed_error()
                raise typer.Exit(1)
        else:
            # Display results in panel
            display_config = DisplayConfig(
                show_summary=True,
                show_details=True,
                show_cache_stats=True,
                verbose=options.verbose,
                full_width=True
            )
            UIControl.display_inspection_result(result, display_config, console)
            
            # Handle fields display separately if requested
            if options.show_fields:
                field_analysis = result.get('field_analysis', {})
                topics = result.get('topics', [])
                if field_analysis or any('field_paths' in topic for topic in topics):
                    # Use unified UI method for field panel display
                    ui.show_fields_panel(field_analysis, topics)
            
    except Exception as e:
        ui.show_error(f"Error during bag inspection: {e}")
        raise typer.Exit(1)
    finally:
        pass


def _build_hierarchical_field_paths(message_fields, msg_type):
    """
    Build hierarchical field paths with dot notation from message field definitions
    
    The message_fields structure contains flattened field definitions where:
    - Top-level fields belong directly to the message type
    - Nested complex types are stored as separate entries with type names as keys
    - We need to reconstruct the hierarchy by following type relationships
    
    Args:
        message_fields: Dictionary of message field definitions (flattened)
        msg_type: Message type to analyze
    
    Returns:
        List of hierarchical field paths
    """
    if msg_type not in message_fields:
        return []
    
    # Get all fields for this message type
    msg_fields = message_fields[msg_type]
    
    # Build a mapping of which fields belong to which complex types
    # This helps us understand the structure
    type_field_map = {}
    
    # First pass: identify all the type definitions and their fields
    for field_name, field_info in msg_fields.items():
        if not isinstance(field_info, dict):
            continue
        
        field_type = field_info.get('type', '')
        
        # Skip MSG type markers - these indicate complex type definitions
        if field_type == 'MSG:':
            # This field_name is actually a type name, not a field
            type_field_map[field_name] = []
            continue
        
        # This is an actual field
        is_builtin = field_info.get('is_builtin', True)
        is_complex = field_info.get('is_complex', False)
        
        # Determine which type this field belongs to
        # Fields that come after a MSG: type definition belong to that type
        belongs_to_type = msg_type  # Default to main message type
        
        # Look backwards to find the most recent MSG: type definition
        field_items = list(msg_fields.items())
        field_index = field_items.index((field_name, field_info))
        
        for i in range(field_index - 1, -1, -1):
            prev_name, prev_info = field_items[i]
            if isinstance(prev_info, dict) and prev_info.get('type') == 'MSG:':
                belongs_to_type = prev_name
                break
        
        if belongs_to_type not in type_field_map:
            type_field_map[belongs_to_type] = []
        
        type_field_map[belongs_to_type].append({
            'name': field_name,
            'type': field_type,
            'is_builtin': is_builtin,
            'is_complex': is_complex,
            'info': field_info
        })
    
    # Second pass: build hierarchical paths
    def build_paths_for_type(type_name, prefix="", visited=None):
        if visited is None:
            visited = set()
        
        if type_name in visited:
            return []
        
        visited.add(type_name)
        paths = []
        
        if type_name not in type_field_map:
            return paths
        
        for field in type_field_map[type_name]:
            field_name = field['name']
            field_type = field['type']
            is_builtin = field['is_builtin']
            is_complex = field['is_complex']
            
            current_path = f"{prefix}.{field_name}" if prefix else field_name
            paths.append(current_path)
            
            # If it's a complex type, try to expand it
            if is_complex and not is_builtin:
                # Handle array types
                base_type = field_type.replace('[]', '')
                
                # Look for this type in our type_field_map
                matching_type = None
                if base_type in type_field_map:
                    matching_type = base_type
                else:
                    # Try to find by suffix matching
                    for type_key in type_field_map.keys():
                        if type_key.endswith(f'/{base_type}') or type_key.endswith(f'/msg/{base_type}'):
                            matching_type = type_key
                            break
                        # Also try exact name matching for common types
                        if type_key.split('/')[-1] == base_type:
                            matching_type = type_key
                            break
                
                if matching_type and matching_type != type_name:
                    sub_paths = build_paths_for_type(matching_type, current_path, visited.copy())
                    paths.extend(sub_paths)
        
        return paths
    
    # Start with the main message type
    return build_paths_for_type(msg_type)


if __name__ == "__main__":
    app() 