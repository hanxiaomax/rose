#!/usr/bin/env python3
"""
Cache command for ROS bag analysis utilities.
"""

import json
import yaml
import pickle
import time
from pathlib import Path
from typing import Optional, List
import typer

from ..core.cache import get_cache, BagCacheEntry
from ..core.output import get_output

app = typer.Typer(name="cache", help="Cache management commands")


@app.callback(invoke_without_command=True)
def cache_default(
    ctx: typer.Context,
    show_content: bool = typer.Option(False, "--content", "-c", help="Show detailed cache content"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """Show cache information (default command when no subcommand is provided)"""
    if ctx.invoked_subcommand is None:
        out = get_output()
        try:
            cache = get_cache()
            _show_cache_info(cache, show_content, verbose, out)
        except Exception as e:
            out.error(f"Error showing cache: {str(e)}")
            raise typer.Exit(1)


@app.command("export")
def cache_export(
    output_file: str = typer.Argument(..., help="Output file path"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Cache key or bag file name to export"),
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Original bag file path to find cache for"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, yaml, pickle"),
    include_messages: bool = typer.Option(False, "--messages", "-m", help="Include cached message data")
):
    """Export cache entries to file"""
    out = get_output()
    try:
        cache = get_cache()
        _export_cache_entries(cache, output_file, name, bag_path, format, include_messages, out)
    except Exception as e:
        out.error(f"Error exporting cache: {str(e)}")
        raise typer.Exit(1)


@app.command("clear")
def cache_clear(
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Clear cache for specific bag file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Clear cache data"""
    out = get_output()
    try:
        cache = get_cache()
        _clear_cache_entries(cache, bag_path, yes, out)
    except Exception as e:
        out.error(f"Error clearing cache: {str(e)}")
        raise typer.Exit(1)


# =============================================================================
# Helper Functions
# =============================================================================

def _show_cache_info(cache, show_content, verbose, out):
    """Show cache information and entries"""
    try:
        # Get all cache entries
        all_entries = _get_all_cache_entries(cache)
        entry_count = len(all_entries)
        
        # Get stats
        stats = cache.get_stats()
        
        # Display cache overview
        out.section("Cache Information")
        
        total_entries = stats.get('entry_count', 0) + stats.get('memory_entries', 0)
        total_size_mb = stats.get('cache_size_bytes', 0) / 1024 / 1024
        cache_dir = str(cache.cache_dir) if hasattr(cache, 'cache_dir') else "N/A"
        
        out.key_value({
            "Total entries": total_entries,
            "Memory entries": stats.get('memory_entries', 0),
            "Disk entries": stats.get('entry_count', 0),
            "Total size": f"{total_size_mb:.2f} MB",
            "Cache directory": cache_dir
        })
        
        if entry_count == 0:
            out.newline()
            out.info("Cache is empty")
            return
        
        # Process and display entries
        entries_data = []
        for key, value, cache_type in all_entries:
            try:
                entry_dict = {
                    "key": key,
                    "location": cache_type
                }
                
                if isinstance(value, BagCacheEntry):
                    bag_info = value.bag_info
                    entry_dict.update({
                        "bag_path": str(getattr(bag_info, 'file_path', 'Unknown')),
                        "topics_count": len(getattr(bag_info, 'topics', [])),
                        "duration_sec": getattr(bag_info, 'duration_seconds', 0),
                        "size_mb": value.file_size / 1024 / 1024 if value.file_size else 0,
                    })
                
                entries_data.append(entry_dict)
            except Exception:
                continue
        
        # Display entries
        out.newline()
        out.section(f"Cached Entries ({len(entries_data)})")
        
        if verbose or show_content:
            # Detailed table view
            columns = ["File", "Topics", "Duration", "Size", "Location"]
            rows = []
            for e in entries_data:
                bag_name = Path(e.get('bag_path', e['key'])).name
                rows.append([
                    bag_name,
                    str(e.get('topics_count', '-')),
                    f"{e.get('duration_sec', 0):.1f}s",
                    f"{e.get('size_mb', 0):.1f} MB",
                    e['location']
                ])
            out.table(None, columns, rows)
        else:
            # Simple list view
            for e in entries_data:
                bag_name = Path(e.get('bag_path', e['key'])).name
                size_mb = e.get('size_mb', 0)
                out.print(f"  {bag_name} ({size_mb:.1f} MB)")
        
        out.newline()
        out.success(f"Cache contains {len(entries_data)} entries")
        
    except Exception as e:
        out.error(f"Error getting cache info: {str(e)}")
        raise typer.Exit(1)


def _clear_cache_entries(cache, bag_path, skip_confirm, out):
    """Clear cache entries with optional bag path filtering"""
    stats = cache.get_stats()
    total_entries = stats.get('entry_count', 0) + stats.get('memory_entries', 0)
    
    if total_entries == 0:
        out.info("Cache is already empty")
        return
    
    # Calculate size to free
    size_to_free_mb = stats.get('cache_size_bytes', 0) / 1024 / 1024
    
    if bag_path:
        # Clear specific bag cache
        bag_path_obj = Path(bag_path)
        cache_key = cache.get_bag_cache_key(bag_path_obj)
        
        cached_data = cache.get(cache_key)
        if not cached_data:
            out.warning(f"No cache entry found for: {bag_path}")
            return
        
        # Confirm
        if not skip_confirm:
            out.warning(f"Will clear cache for: {bag_path}")
            out.warning("Use --yes flag to confirm")
            return
        
        out.info(f"Clearing cache for: {bag_path}")
        success = cache.delete(cache_key)
        
        if success:
            out.success(f"Cleared cache for: {bag_path}")
        else:
            out.error(f"Failed to clear cache for: {bag_path}")
    else:
        # Clear all cache
        all_entries = _get_all_cache_entries(cache)
        entries_to_clear = len(all_entries)
        
        # Show what will be cleared
        out.info(f"Will clear {entries_to_clear} cache entries ({size_to_free_mb:.2f} MB)")
        
        # Confirm
        if not skip_confirm:
            out.warning("Use --yes flag to confirm")
            return
        
        # Clear cache with progress
        with out.spinner("Clearing cache..."):
            cache.clear()
        
        out.success(f"Cleared {entries_to_clear} entries, freed {size_to_free_mb:.2f} MB")


def _export_cache_entries(cache, output_file, name, bag_path, format, include_messages, out):
    """Export cache entries to file"""
    try:
        # Validate format
        valid_formats = ["json", "yaml", "pickle"]
        if format not in valid_formats:
            out.error(
                f"Unsupported export format: {format}",
                details=f"Valid formats: {', '.join(valid_formats)}"
            )
            raise typer.Exit(1)
        
        # Get all cache entries
        all_entries = _get_all_cache_entries(cache)
        
        if not all_entries:
            out.info("No cache entries to export")
            return
        
        # Filter entries if criteria provided
        if name or bag_path:
            filtered_entries = []
            for key, value, cache_type in all_entries:
                match = False
                
                if name and name.lower() in key.lower():
                    match = True
                
                if bag_path and not match:
                    try:
                        bag_path_obj = Path(bag_path)
                        expected_key = cache.get_bag_cache_key(bag_path_obj)
                        if key == expected_key:
                            match = True
                    except Exception:
                        if bag_path.lower() in key.lower():
                            match = True
                
                if match:
                    filtered_entries.append((key, value, cache_type))
            
            all_entries = filtered_entries
        
        entry_count = len(all_entries)
        
        if entry_count == 0:
            out.info("No matching cache entries found")
            return
        
        out.info(f"Exporting {entry_count} cache entries to {output_file}...")
        
        # Prepare export data
        with out.spinner("Processing entries..."):
            export_data = _prepare_export_data(all_entries, include_messages)
        
        # Export to file
        output_path = Path(output_file)
        
        with out.spinner(f"Writing {format.upper()} file..."):
            if format == "json":
                with open(output_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
            elif format == "yaml":
                with open(output_path, 'w') as f:
                    yaml.dump(export_data, f, default_flow_style=False)
            elif format == "pickle":
                with open(output_path, 'wb') as f:
                    pickle.dump(export_data, f)
        
        out.success(f"Exported {entry_count} entries to: {output_path}")
        
    except typer.Exit:
        raise
    except Exception as e:
        out.error(f"Error exporting cache: {str(e)}")
        raise typer.Exit(1)


def _process_single_entry(key, value, cache_type, include_messages):
    """Process a single cache entry for export"""
    try:
        entry_data = {
            'key': key,
            'cache_type': cache_type,
            'timestamp': time.time()
        }
        
        if isinstance(value, BagCacheEntry):
            bag_info = value.bag_info
            entry_data.update({
                'bag_path': str(getattr(bag_info, 'file_path', 'Unknown')),
                'topics_count': len(getattr(bag_info, 'topics', [])),
                'messages_count': sum(getattr(bag_info, 'message_counts', {}).values()) if hasattr(bag_info, 'message_counts') and bag_info.message_counts else 0,
                'duration_sec': getattr(bag_info, 'duration_seconds', 0),
                'size_mb': value.file_size / 1024 / 1024 if value.file_size else 0,
                'created': value.cache_timestamp,
                'last_accessed': value.file_mtime
            })
            
            if include_messages and hasattr(bag_info, 'topics'):
                entry_data['topics'] = [
                    {
                        'name': getattr(topic, 'name', str(topic)),
                        'type': getattr(topic, 'message_type', 'unknown'),
                        'message_count': getattr(topic, 'message_count', 0),
                        'frequency': getattr(topic, 'message_frequency', 0)
                    }
                    for topic in bag_info.topics
                ]
        else:
            # Handle other cache entry types
            entry_data['value'] = str(value)
        
        return entry_data
        
    except Exception as e:
        return {
            'key': key,
            'cache_type': cache_type,
            'error': f"Failed to process entry: {str(e)}",
            'timestamp': time.time()
        }


def _get_all_cache_entries(cache) -> List[tuple]:
    """Get all cache entries from memory and disk"""
    all_entries = []
    
    # Get memory cache entries
    if hasattr(cache, '_memory_cache'):
        memory_entries = [(key, entry.value if hasattr(entry, 'value') else entry, 'memory') 
                        for key, entry in cache._memory_cache.items()]
        all_entries.extend(memory_entries)
    
    # Get file cache entries
    seen_keys = set()
    if hasattr(cache, 'cache_dir'):
        for file_path in cache.cache_dir.glob("*.pkl"):
            try:
                with open(file_path, 'rb') as f:
                    value = pickle.load(f)
                key = file_path.stem
                if key not in seen_keys:
                    all_entries.append((key, value, 'disk'))
                    seen_keys.add(key)
            except Exception:
                continue
    
    return all_entries


def _prepare_export_data(all_entries, include_messages):
    """Prepare cache data for export"""
    export_data = {
        'metadata': {
            'export_time': time.time(),
            'total_entries': len(all_entries),
            'include_messages': include_messages
        },
        'entries': []
    }
    
    for key, value, cache_type in all_entries:
        try:
            entry_data = {
                'key': key,
                'type': cache_type,
                'timestamp': time.time()
            }
            
            if isinstance(value, BagCacheEntry):
                entry_data['content'] = _bag_cache_to_dict(value, include_messages)
            else:
                content_str = str(value)
                entry_data['content'] = content_str[:200] + "..." if len(content_str) > 200 else content_str
            
            export_data['entries'].append(entry_data)
            
        except Exception as e:
            export_data['entries'].append({
                'key': key,
                'type': cache_type,
                'error': str(e)
            })
    
    return export_data


def _bag_cache_to_dict(bag_cache_entry, include_messages=False):
    """Convert BagCacheEntry to dictionary for export"""
    try:
        bag_info = bag_cache_entry.bag_info
        result = {
            'file_path': getattr(bag_info, 'file_path', 'Unknown'),
            'topics_count': len(getattr(bag_info, 'topics', [])),
            'duration_seconds': getattr(bag_info, 'duration_seconds', 0),
            'cache_timestamp': bag_cache_entry.cache_timestamp,
            'file_mtime': bag_cache_entry.file_mtime,
            'file_size': bag_cache_entry.file_size
        }
        
        if hasattr(bag_info, 'topics') and bag_info.topics:
            result['topics'] = [
                {
                    'name': getattr(t, 'name', str(t)),
                    'type': getattr(t, 'message_type', 'unknown')
                }
                for t in bag_info.topics
            ]
        
        if hasattr(bag_info, 'message_counts') and bag_info.message_counts:
            result['message_counts'] = bag_info.message_counts
            result['total_messages'] = sum(bag_info.message_counts.values())
        
        if include_messages and hasattr(bag_cache_entry, 'cached_messages') and bag_cache_entry.cached_messages:
            result['cached_messages'] = {
                topic: len(messages) for topic, messages in bag_cache_entry.cached_messages.items()
            }
        
        return result
        
    except Exception as e:
        return {'error': f'Failed to convert bag cache entry: {e}'}


if __name__ == "__main__":
    app()
