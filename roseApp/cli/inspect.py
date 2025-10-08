#!/usr/bin/env python3
"""
Inspect command for ROS bag files.
Headless NDJSON mode - pure event emission.
"""
import asyncio
from pathlib import Path
from typing import Optional, List
import typer

from ..core.model import AnalysisLevel
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.cache import create_bag_cache_manager
from ..core.event_emitter import get_emitter

# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(help="Inspect ROS bag files")


def filter_topics(topic_list, pattern, exclude_pattern=None):
    """Simple topic filtering by regex pattern"""
    import re
    if pattern:
        regex = re.compile(pattern)
        topic_list = [t for t in topic_list if regex.search(t)]
    if exclude_pattern:
        exclude_regex = re.compile(exclude_pattern)
        topic_list = [t for t in topic_list if not exclude_regex.search(t)]
    return topic_list


@app.command()
def inspect(
    bag_path: Optional[Path] = typer.Argument(None, help="Path to the ROS bag file"),
    topics_filter: Optional[str] = typer.Option(None, "--topics", "-t", help="Filter topics by regex pattern"),
    show_fields: bool = typer.Option(False, "--show-fields", help="Show field analysis for messages"),
    sort_by: str = typer.Option("size", "--sort", help="Sort topics by (name, count, frequency, size)"),
    reverse_sort: bool = typer.Option(False, "--reverse", help="Reverse sort order"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Show debug logs"),
):
    """
    Inspect a ROS bag file and display comprehensive analysis.
    
    The bag file must be loaded into cache first using 'rose load'.
    This command uses cached bag analysis for fast inspection.
    
    Examples:
        rose inspect demo.bag                      # Show basic bag info
        rose inspect demo.bag -v                   # Show detailed statistics
        rose inspect demo.bag --show-fields        # Include field analysis
        rose inspect demo.bag -t "/camera.*"       # Filter topics by regex
    """
    try:
        # Get event emitter
        emitter = get_emitter()
        emitter.set_context("inspect")
        
        # Validate bag file exists
        if not bag_path:
            emitter.emit_error(
                "INVALID_ARGUMENT",
                "Bag file path is required",
                details={"suggestions": ["Provide a bag file path: rose inspect demo.bag"]}
            )
            raise typer.Exit(1)
        
        if not bag_path.exists():
            emitter.emit_error(
                "BAG_NOT_FOUND",
                f"Bag file not found: {bag_path}",
                details={
                    "path": str(bag_path),
                    "suggestions": [
                        "Check the file path",
                        "Ensure the file exists"
                    ]
                }
            )
            raise typer.Exit(1)
        
        # Get cache manager and check current status
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(bag_path)
        
        # Check if bag is in cache
        if cached_entry is None:
            emitter.emit_error(
                "BAG_NOT_CACHED",
                f"Bag file not in cache: {bag_path}",
                details={
                    "path": str(bag_path),
                    "suggestions": [
                        f"Load the bag first: rose load {bag_path}",
                        "Run 'rose load' to cache all bags in directory"
                    ]
                }
            )
            raise typer.Exit(1)
        
        # Emit progress: starting inspection
        emitter.emit_progress(0, "Starting inspection")
        
        # Convert cached bag info to result format
        bag_info = cached_entry.bag_info
        
        # Refresh statistics from DataFrames if available
        if bag_info.has_any_dataframes():
            emitter.emit_progress(30, "Refreshing statistics")
            bag_info.refresh_all_statistics_from_dataframes()
        
        # Emit bag metadata
        emitter.emit_progress(50, "Analyzing metadata")
        metadata = {
            'file_path': bag_info.file_path,
            'file_name': Path(bag_info.file_path).name,
            'file_size': bag_info.file_size or 0,
            'file_size_mb': bag_info.file_size_mb,
            'topics_count': len(bag_info.topics),
            'total_messages': bag_info.total_messages or 0,
            'duration_seconds': bag_info.duration_seconds or 0.0,
            'time_range': bag_info.time_range.to_dict() if bag_info.time_range else None,
            'cached': True,
            'has_dataframes': bag_info.has_any_dataframes()
        }
        
        emitter.emit_data(
            data=metadata,
            label="metadata"
        )
        
        # Get all topic names for filtering
        all_topic_names = [topic if isinstance(topic, str) else topic.name for topic in bag_info.topics]
        
        # Apply topic filtering if specified
        if topics_filter:
            filtered_topic_names = filter_topics(all_topic_names, topics_filter, None)
        else:
            filtered_topic_names = all_topic_names
        
        # Emit progress: analyzing topics
        emitter.emit_progress(70, "Analyzing topics")
        
        # Convert topics to output format
        topics_output = []
        for topic_info_obj in bag_info.topics:
            if topic_info_obj.name not in filtered_topic_names:
                continue
            
            if verbose:
                topic_info = {
                    'name': topic_info_obj.name,
                    'message_type': topic_info_obj.message_type,
                    'message_count': topic_info_obj.message_count or 0,
                    'frequency': topic_info_obj.message_frequency or 0.0,
                    'size_bytes': topic_info_obj.total_size_bytes or 0
                }
            else:
                topic_info = {
                    'name': topic_info_obj.name,
                    'message_type': topic_info_obj.message_type
                }
            
            # Add field paths if requested
            if show_fields:
                msg_type_info = bag_info.find_message_type(topic_info_obj.message_type)
                if msg_type_info and msg_type_info.fields:
                    topic_info['field_paths'] = msg_type_info.get_all_field_paths()
            
            topics_output.append(topic_info)
        
        # Sort topics
        if sort_by == "name":
            topics_output.sort(key=lambda t: t['name'], reverse=reverse_sort)
        elif sort_by == "count" and verbose:
            topics_output.sort(key=lambda t: t.get('message_count', 0), reverse=reverse_sort)
        elif sort_by == "frequency" and verbose:
            topics_output.sort(key=lambda t: t.get('frequency', 0.0), reverse=reverse_sort)
        elif sort_by == "size" and verbose:
            topics_output.sort(key=lambda t: t.get('size_bytes', 0), reverse=reverse_sort)
        
        # Emit topics data
        emitter.emit_data(
            data=topics_output,
            label="topics",
            count=len(topics_output)
        )
        
        # Add field analysis if requested
        if show_fields and len(bag_info.message_types) > 0:
            emitter.emit_progress(90, "Analyzing fields")
            
            field_analysis = {}
            for topic_info_obj in bag_info.topics:
                if topic_info_obj.name not in filtered_topic_names:
                    continue
                    
                msg_type_info = bag_info.find_message_type(topic_info_obj.message_type)
                if msg_type_info and msg_type_info.fields:
                    field_paths = msg_type_info.get_all_field_paths()
                    if field_paths:
                        field_analysis[topic_info_obj.name] = {
                            'message_type': topic_info_obj.message_type,
                            'field_paths': sorted(field_paths)
                        }
            
            if field_analysis:
                emitter.emit_data(
                    data=field_analysis,
                    label="fields"
                )
        
        # Emit done event
        emitter.emit_progress(100, "Inspection complete")
        
        emitter.emit_done({
            "topics_count": len(topics_output),
            "total_topics": len(bag_info.topics),
            "filtered": topics_filter is not None,
            "show_fields": show_fields,
            "sort_by": sort_by,
            "verbose": verbose
        })
    
    except typer.Exit:
        raise
    except Exception as e:
        # Emit error event
        emitter = get_emitter()
        emitter.emit_error(
            code=type(e).__name__.upper(),
            message=str(e),
            details={'verbose': verbose or False}
        )
        
        logger.error(f"Unexpected error during inspection: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
