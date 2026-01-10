#!/usr/bin/env python3
"""
Inspect command for ROS bag files.
"""
import asyncio
import re
import sys
import difflib
from pathlib import Path
from typing import Optional, List, Any, Dict
import typer
from rich.tree import Tree

from ..core.logging import get_logger
from ..core.output import get_output, create_step_manager
from ..core.pipeline import inspect_orchestrator
from ..core.events import LogEvent, ProgressEvent, ResultEvent

# Initialize logger
logger = get_logger(__name__)


def filter_topics(topic_list, pattern, exclude_pattern=None):
    """Simple topic filtering by regex pattern"""
    if pattern:
        regex = re.compile(pattern)
        topic_list = [t for t in topic_list if regex.search(t)]
    if exclude_pattern:
        exclude_regex = re.compile(exclude_pattern)
        topic_list = [t for t in topic_list if not exclude_regex.search(t)]
    return topic_list


def inspect(
    bag_path: Optional[Path] = typer.Argument(None, help="Path to the ROS bag file"),
    topics_filter: Optional[str] = typer.Option(None, "--topics", "-t", help="Filter topics by regex pattern"),
    show_fields: bool = typer.Option(False, "--show-fields", help="Show field analysis for messages"),
    sort_by: str = typer.Option("size", "--sort", help="Sort topics by (name, count, frequency, size)"),
    reverse_sort: bool = typer.Option(False, "--reverse", help="Reverse sort order"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Show debug logs"),
    load: bool = typer.Option(False, "--load", help="Load bag if not cached (without building index)"),
    load_index: bool = typer.Option(False, "--load-index", help="Load bag with index building if not cached"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reload even if already cached"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode (TUI)"),
    topic: Optional[str] = typer.Option(None, "--topic", help="Auto-select exact matching topic in interactive mode"),
):

    """
    Inspect a ROS bag file and display comprehensive analysis.
    
    The bag file must be loaded into cache first using 'rose load'.
    This command uses cached bag analysis for fast inspection.
    
    Examples:
        rose inspect demo.bag                      # Show basic bag info
        rose inspect demo.bag --load               # Auto load if not cached
        rose inspect demo.bag --load --force       # Force reload
        rose inspect demo.bag --load-index         # Auto load with index building
        rose inspect demo.bag -i --topic /gps/fix  # Open TUI with /gps/fix selected
    """
    out = get_output()
    steps = create_step_manager()
    
    # Check mutually exclusive options
    if load and load_index:
        out.error(
            "Options --load and --load-index are mutually exclusive",
            details="Use --load for quick load without index, or --load-index to build index"
        )
        raise typer.Exit(1)
        
    if topic and topics_filter:
        out.error(
            "Options --topic and --topics are mutually exclusive",
            details="--topic is for exact single topic match, --topics is for regex filtering."
        )
        raise typer.Exit(1)
    
    # Auto-enable interactive if no bag path provided
    if bag_path is None and not interactive:
        interactive = True

    if bag_path is None and interactive:
        # Launch interactive bag picker
        from .interactive import select_bags_interactive
        # If running interactive inspection, we prefer bags that are already indexed
        selected_files, idx_choice = select_bags_interactive(None, load_index, allow_multiple=False, require_index=True)
        
        if selected_files:
            if len(selected_files) > 1:
                out.warning(f"Inspect supports only one bag at a time. Selecting first one: {selected_files[0]}")
            bag_path = Path(selected_files[0])
            if idx_choice:
                load_index = True

    if not bag_path:
        out.error("Bag file path is required")
        raise typer.Exit(1)

    # Determine effective load mode
    should_load = load or load_index
    build_index = load_index
    
    try:
        # Run Orchestrator
        # We might need to run it twice if first time fails due to cache
        
        attempt_load = should_load
        
        # Generator for processing events
        def run_pipeline(load_flag):
            return inspect_orchestrator(bag_path, load_if_missing=load_flag, build_index=build_index, force=force)

        pipeline = run_pipeline(attempt_load)
        
        # State machine for CLI
        bag_info = None
        not_cached = False
        
        # Consume pipeline
        # We need to be able to restart if we decide to load interactively.
        # Since generator can't be restarted, we might break and create new one.
        
        # For simplicity in this structure: we run loop. If result is 'not_cached', we prompt and re-run.
        
        executed_events = []
        
        # Helper to process events from a pipeline generator
        def process_events(gen):
            nonlocal bag_info, not_cached
            from contextlib import ExitStack
            
            # Initial phase
            current_phase = "check"
            steps.section("Checking cache status")
            
            stack = ExitStack()
            try:
                live_status = stack.enter_context(out.live_status("Processing"))
                live_status.add_item("main", bag_path.name, "processing")
                
                for event in gen:
                    executed_events.append(event)
                    
                    if isinstance(event, LogEvent):
                        if event.level == "INFO":
                            # Transition detection
                            if "Loading bag" in event.message and current_phase == "check":
                                # Transition to loading phase
                                # Mark previous as proper status before switching?
                                # Actually "Loading bag" means check decided to load.
                                # So check is "done" (Analysis determined load needed) or "skip" (Not cached).
                                # Let's say check is done.
                                live_status.update_item("main", "done", "(Cache miss/Force)")
                                stack.close() # Close current live status
                                
                                # Start new section
                                load_desc = event.message
                                steps.section(load_desc.replace("...", ""))
                                stack = ExitStack()
                                live_status = stack.enter_context(out.live_status("Processing"))
                                live_status.add_item("main", bag_path.name, "processing")
                                current_phase = "load"
                                continue

                            if "Reloading" in event.message:
                                live_status.update_item("main", "processing", "(Upgrading index...)")
                            elif event.message.startswith("Inspecting"):
                                # Suppress top-level start message to avoid UI clutter
                                pass
                            elif verbose:
                                out.info(event.message)
                                
                        elif event.level == "WARN":
                             if "Bag not in cache" in event.message:
                                 live_status.update_item("main", "skip", "(Not in cache)")
                             if verbose:
                                out.warning(event.message)
                        elif event.level == "ERROR":
                             live_status.update_item("main", "error", f"Error: {event.message}")
                             out.error(event.message)
                        elif event.level == "DEBUG":
                             if debug:
                                 out.debug(event.message)
                                 
                    elif isinstance(event, ProgressEvent):
                        # Update loading progress
                        if "Loading" in event.description:
                             pct = f"{event.current}%"
                             live_status.update_item("main", "processing", f"(Loading {pct})")
                        
                    elif isinstance(event, ResultEvent):
                        data = event.data
                        if data.get('status') == 'success':
                            bag_info = data.get('bag_info')
                            live_status.update_item("main", "done", "(Ready)")
                        elif data.get('status') == 'not_cached':
                            not_cached = True
                            live_status.update_item("main", "warning", "(Not in cache)")
                        elif data.get('status') == 'error':
                            live_status.update_item("main", "error", "(Failed)")
                            raise typer.Exit(1)
            finally:
                stack.close()
                            
        # First run
        process_events(pipeline)
        
        if not_cached and not should_load:
            # Interactive prompt for loading
            out.newline()
            out.warning(f"Bag '{bag_path.name}' is not in cache.")
            
            # Use Rich Prompt if available or simple input
            # We'll use simple input with manual options
            sys.stdout.write("Load options: [l]oad quick, load with [i]ndex, [N]o? [l/i/N]: ")
            sys.stdout.flush()
            
            try:
                response = input().strip().lower()
                load_retry = False
                
                if response in ['l', 'y', 'yes', 'load']:
                    out.newline()
                    build_index = False
                    load_retry = True
                elif response in ['i', 'index']:
                    out.newline()
                    build_index = True
                    load_retry = True
                else:
                    out.info("Cancelled")
                    raise typer.Exit(0)
                
                if load_retry:
                    # Re-run pipeline with new settings
                    pipeline_retry = inspect_orchestrator(bag_path, load_if_missing=True, build_index=build_index)
                    # Reset flags
                    not_cached = False
                    bag_info = None
                    process_events(pipeline_retry)
                    
            except (EOFError, KeyboardInterrupt):
                out.newline()
                out.info("Cancelled")
                raise typer.Exit(0)
                
        if not bag_info:
            if not not_cached: 
                 out.error("Failed to retrieve bag analysis details.")
            raise typer.Exit(1)

        # Check for upgrade needed for interactive mode
        # TUI requires message index for plots and values
        if interactive and not bag_info.has_message_index():
            out.newline()
            out.warning("Interactive mode requires message index for full functionality (plots, values).")
            out.info(f"Current analysis level: {bag_info.analysis_level.name if hasattr(bag_info, 'analysis_level') else 'QUICK'}")
            
            sys.stdout.write("Build message index now? [Y/n]: ")
            sys.stdout.flush()
            
            try:
                resp = input().strip().lower()
                if resp in ['', 'y', 'yes']:
                    out.newline()
                    build_index = True
                    # Re-run pipeline for upgrade
                    pipeline_upgrade = inspect_orchestrator(bag_path, load_if_missing=True, build_index=True)
                    # Reset
                    bag_info = None
                    process_events(pipeline_upgrade)
                    
                    if not bag_info or not bag_info.has_message_index():
                         out.error("Index build failed. Cannot proceed with TUI.")
                         raise typer.Exit(1)
                else:
                    out.info("Index required for TUI. Exiting.")
                    raise typer.Exit(0)
            except (EOFError, KeyboardInterrupt):
                out.newline()
                out.info("Cancelled")
                raise typer.Exit(0)


        # Handle --topic non-interactive mode (Rich Tree output)
        if topic and not interactive:
            # Find exact topic
            target_topic = next((t for t in bag_info.topics if t.name == topic), None)
            if not target_topic:
                 out.error(f"Topic '{topic}' not found in bag.")
                 # Fuzzy Match
                 all_names = [t.name for t in bag_info.topics]
                 matches = difflib.get_close_matches(topic, all_names, n=5, cutoff=0.3)
                 if matches:
                     out.info(f"Did you mean: {', '.join(matches)}?")
                 else:
                     out.info(f"Available topics: {', '.join(all_names[:5])}...")
                 raise typer.Exit(1)
            
            # Create Rich Tree
            root = Tree(f"[bold {out.theme.primary}]{target_topic.name}[/]")
            root.add(f"Type: [{out.theme.muted}]{target_topic.message_type}[/]")
            root.add(f"Count: {target_topic.message_count}")
            
            # Get Fields
            msg_type_info = bag_info.find_message_type(target_topic.message_type)
            if msg_type_info and msg_type_info.fields:
                fields_node = root.add(f"[bold {out.theme.accent}]Fields[/]")
                
                paths = msg_type_info.get_all_field_paths()
                paths.sort()
                
                # Build tree from paths
                # Map path -> Tree Node
                node_map = {"": fields_node} 
                
                for path in paths:
                    parts = path.split('.')
                    # Ensure all parents check?
                    # Since paths might not include intermediate parents if they are just field names?
                    # get_all_field_paths usually returns leaves?
                    # If it returns leaves 'a.b.c', we need 'a' and 'a.b' nodes.
                    
                    current_path = ""
                    parent_node = fields_node
                    
                    for part in parts:
                        prev_path = current_path
                        current_path = f"{current_path}.{part}" if current_path else part
                        
                        if current_path not in node_map:
                            # Add new node to parent
                            # Style leaf differently?
                            # If it's the full path, it might be a leaf.
                            # But we are iterating, so we are building down.
                            # We don't know if it's a leaf yet easily, but Rich Tree handles it.
                            new_node = parent_node.add(f"[{out.theme.info}]{part}[/]")
                            node_map[current_path] = new_node
                            parent_node = new_node
                        else:
                            parent_node = node_map[current_path]
            
            out.print(root)
            raise typer.Exit(0)
            
        if interactive:
            from ..tui.inspect_app import InspectApp
            app = InspectApp(
                bag_path=str(bag_path), 
                bag_info=bag_info, 
                theme=out.theme,
                initial_topic=topic
            )
            app.run()
            raise typer.Exit(0)
            
        steps.section("Bag Inspection Results")
        
        duration = bag_info.duration_seconds or 0.0
        if duration > 60:
            duration_str = f"{int(duration // 60)}m {duration % 60:.1f}s"
        else:
            duration_str = f"{duration:.2f}s"
        out.newline()
        out.key_value({
            "File": bag_info.file_path,
            "Size": f"{bag_info.file_size_mb:.2f} MB",
            "Duration": duration_str,
            "Topics": len(bag_info.topics),
            "Messages": bag_info.total_messages or "N/A",
        },title="Bag Information")
        
        if verbose and bag_info.time_range:
            out.newline()
            out.key_value({
                "Start time": str(bag_info.time_range.start_time),
                "End time": str(bag_info.time_range.end_time),
            }, title="Time Range")
        
        # Get all topic names
        all_topic_names = [topic if isinstance(topic, str) else topic.name for topic in bag_info.topics]
        
        # Apply filtering
        if topics_filter:
            filtered_topic_names = filter_topics(all_topic_names, topics_filter, None)
        else:
            filtered_topic_names = all_topic_names
        
        # Build topics data
        topics_data = []
        for topic_info_obj in bag_info.topics:
            t_name = topic_info_obj.name
            if t_name not in filtered_topic_names:
                continue
            
            topic_data = {
                'name': t_name,
                'message_type': topic_info_obj.message_type,
                'message_count': topic_info_obj.message_count or 0,
                'frequency': topic_info_obj.message_frequency or 0.0,
                'size_bytes': topic_info_obj.total_size_bytes or 0
            }
            
            if show_fields:
                msg_type_info = bag_info.find_message_type(topic_info_obj.message_type)
                if msg_type_info and msg_type_info.fields:
                    topic_data['field_paths'] = msg_type_info.get_all_field_paths()
            
            topics_data.append(topic_data)
        
        # Sort
        if sort_by == "name":
            topics_data.sort(key=lambda t: t['name'], reverse=reverse_sort)
        elif sort_by == "count":
            topics_data.sort(key=lambda t: t.get('message_count', 0), reverse=not reverse_sort)
        elif sort_by == "frequency":
            topics_data.sort(key=lambda t: t.get('frequency', 0.0), reverse=not reverse_sort)
        elif sort_by == "size":
            topics_data.sort(key=lambda t: t.get('size_bytes', 0), reverse=not reverse_sort)
        
        # Display
        out.newline()
        filter_info = f" (filtered: {topics_filter})" if topics_filter else ""
        out.section(f"Topics ({len(topics_data)}{filter_info})")
        
        if verbose:
            columns = ["Topic", "Type", "Count", "Freq (Hz)", "Size"]
            rows = []
            for t in topics_data:
                size_kb = t['size_bytes'] / 1024 if t['size_bytes'] else 0
                rows.append([
                    f"[{out.theme.primary}]{t['name']}[/{out.theme.primary}]",
                    f"[{out.theme.muted}]{t['message_type']}[/{out.theme.muted}]",
                    str(t['message_count']),
                    f"{t['frequency']:.1f}",
                    f"{size_kb:.1f} KB" if size_kb > 0 else "-"
                ])
            out.table(None, columns, rows)
        else:
            for t in topics_data:
                out.print(f"  [{out.theme.primary}]{t['name']}[/{out.theme.primary}] ([{out.theme.muted}]{t['message_type']}[/{out.theme.muted}])")
        
        if show_fields and len(bag_info.message_types) > 0:
            out.newline()
            out.section("Field Analysis")
            for topic_data in topics_data:
                if 'field_paths' in topic_data and topic_data['field_paths']:
                    out.print(f"\n  [{out.theme.accent}]{topic_data['name']}[/{out.theme.accent}]:")
                    for field in sorted(topic_data['field_paths'])[:20]:
                        out.print(f"    - [{out.theme.info}]{field}[/{out.theme.info}]")
                    if len(topic_data['field_paths']) > 20:
                        out.debug(f"    ... and {len(topic_data['field_paths']) - 20} more fields")
        
        out.newline()
        if topics_filter:
            out.success(f"Showing {len(topics_data)} of {len(bag_info.topics)} topics")
        else:
            out.success(f"Inspection complete: {len(topics_data)} topics")
            
    except typer.Exit:
        raise
    except Exception as e:
        out.error(str(e))
        logger.error(f"Unexpected error during inspection: {e}")
        raise typer.Exit(1)


