#!/usr/bin/env python3
"""
Inspect command for ROS bag files.
"""
import re
from pathlib import Path
from typing import Optional
import typer

from ..core.logging import get_logger
from ..core.cache import create_bag_cache_manager
from ..core.output import get_output

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(help="Inspect ROS bag files")


def filter_topics(topic_list, pattern, exclude_pattern=None):
    """Simple topic filtering by regex pattern"""
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
    out = get_output()
    
    try:
        # Validate bag file exists
        if not bag_path:
            out.error(
                "Bag file path is required",
                details="Provide a bag file path: rose inspect demo.bag"
            )
            raise typer.Exit(1)
        
        if not bag_path.exists():
            out.error(
                f"Bag file not found: {bag_path}",
                details="Check the file path and ensure the file exists"
            )
            raise typer.Exit(1)
        
        # Get cache manager and check current status
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(bag_path)
        
        # Check if bag is in cache
        if cached_entry is None:
            out.error(
                f"Bag file not in cache: {bag_path}",
                details=f"Load the bag first: rose load {bag_path}"
            )
            raise typer.Exit(1)
        
        # Get bag info from cache
        bag_info = cached_entry.bag_info
        
        # Refresh statistics from DataFrames if available
        if bag_info.has_any_dataframes():
            if debug:
                out.debug("Refreshing statistics from DataFrames...")
            bag_info.refresh_all_statistics_from_dataframes()
        
        # Display bag metadata
        out.section("Bag Information")
        
        # Format duration
        duration = bag_info.duration_seconds or 0.0
        if duration > 60:
            duration_str = f"{int(duration // 60)}m {duration % 60:.1f}s"
        else:
            duration_str = f"{duration:.2f}s"
        
        out.key_value({
            "File": bag_info.file_path,
            "Size": f"{bag_info.file_size_mb:.2f} MB",
            "Duration": duration_str,
            "Topics": len(bag_info.topics),
            "Messages": bag_info.total_messages or "N/A",
        })
        
        if verbose and bag_info.time_range:
            out.newline()
            out.key_value({
                "Start time": str(bag_info.time_range.start_time),
                "End time": str(bag_info.time_range.end_time),
            }, title="Time Range")
        
        # Get all topic names for filtering
        all_topic_names = [topic if isinstance(topic, str) else topic.name for topic in bag_info.topics]
        
        # Apply topic filtering if specified
        if topics_filter:
            filtered_topic_names = filter_topics(all_topic_names, topics_filter, None)
        else:
            filtered_topic_names = all_topic_names
        
        # Build topics data
        topics_data = []
        for topic_info_obj in bag_info.topics:
            if topic_info_obj.name not in filtered_topic_names:
                continue
            
            topic_data = {
                'name': topic_info_obj.name,
                'message_type': topic_info_obj.message_type,
                'message_count': topic_info_obj.message_count or 0,
                'frequency': topic_info_obj.message_frequency or 0.0,
                'size_bytes': topic_info_obj.total_size_bytes or 0
            }
            
            # Add field paths if requested
            if show_fields:
                msg_type_info = bag_info.find_message_type(topic_info_obj.message_type)
                if msg_type_info and msg_type_info.fields:
                    topic_data['field_paths'] = msg_type_info.get_all_field_paths()
            
            topics_data.append(topic_data)
        
        # Sort topics
        if sort_by == "name":
            topics_data.sort(key=lambda t: t['name'], reverse=reverse_sort)
        elif sort_by == "count":
            topics_data.sort(key=lambda t: t.get('message_count', 0), reverse=not reverse_sort)
        elif sort_by == "frequency":
            topics_data.sort(key=lambda t: t.get('frequency', 0.0), reverse=not reverse_sort)
        elif sort_by == "size":
            topics_data.sort(key=lambda t: t.get('size_bytes', 0), reverse=not reverse_sort)
        
        # Display topics
        out.newline()
        filter_info = f" (filtered: {topics_filter})" if topics_filter else ""
        out.section(f"Topics ({len(topics_data)}{filter_info})")
        
        if verbose:
            # Detailed table view
            columns = ["Topic", "Type", "Count", "Freq (Hz)", "Size"]
            rows = []
            for t in topics_data:
                size_kb = t['size_bytes'] / 1024 if t['size_bytes'] else 0
                rows.append([
                    t['name'],
                    t['message_type'].split('/')[-1] if '/' in t['message_type'] else t['message_type'],
                    str(t['message_count']),
                    f"{t['frequency']:.1f}",
                    f"{size_kb:.1f} KB" if size_kb > 0 else "-"
                ])
            out.table(None, columns, rows)
        else:
            # Simple list view
            for t in topics_data:
                out.print(f"  {t['name']} ({t['message_type']})")
        
        # Show field analysis if requested
        if show_fields and len(bag_info.message_types) > 0:
            out.newline()
            out.section("Field Analysis")
            
            for topic_data in topics_data:
                if 'field_paths' in topic_data and topic_data['field_paths']:
                    out.print(f"\n  {topic_data['name']}:")
                    for field in sorted(topic_data['field_paths'])[:20]:
                        out.print(f"    - {field}")
                    if len(topic_data['field_paths']) > 20:
                        out.debug(f"    ... and {len(topic_data['field_paths']) - 20} more fields")
        
        # Summary
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


if __name__ == "__main__":
    app()
