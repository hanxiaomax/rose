#!/usr/bin/env python3
"""
Cache command for ROS bag analysis utilities - Simplified for headless engine

All output goes through Message API for proper NDJSON/Prettify handling.
"""

import json
import yaml
import pickle
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer

from ..core.cache import get_cache, BagCacheEntry
from ..ui.common_ui import Message

app = typer.Typer(name="cache", help="Cache management commands")


@app.callback(invoke_without_command=True)
def cache_default(
    ctx: typer.Context,
    show_content: bool = typer.Option(False, "--content", "-c", help="Show detailed cache content"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """Show cache information (default command when no subcommand is provided)"""
    if ctx.invoked_subcommand is None:
        try:
            cache = get_cache()
            _show_cache_info(cache, show_content, verbose)
        except Exception as e:
            Message.error(f"Error showing cache: {e}")


@app.command("export")
def cache_export(
    output_file: str = typer.Argument(..., help="Output file path"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Cache key or bag file name to export"),
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Original bag file path to find cache for"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, yaml, pickle"),
    include_messages: bool = typer.Option(False, "--messages", "-m", help="Include cached message data")
):
    """Export cache entries to file"""
    try:
        cache = get_cache()
        _export_cache_entries(cache, output_file, name, bag_path, format, include_messages)
    except Exception as e:
        Message.error(f"Error exporting cache: {e}")


@app.command("clear")
def cache_clear(
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Clear cache for specific bag file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """Clear cache data"""
    try:
        cache = get_cache()
        _clear_cache_entries(cache, bag_path, yes)
    except Exception as e:
        Message.error(f"Error clearing cache: {e}")


# =============================================================================
# Helper Functions - All use Message API
# =============================================================================

def _show_cache_info(cache, show_content, verbose):
    """Show cache information and entries"""
    try:
        stats = cache.get_stats()
        
        # Display cache statistics via Message API
        Message.info("Cache Statistics:")
        Message.info(f"  Total Entries: {stats.get('entry_count', 0) + stats.get('memory_entries', 0)}")
        Message.info(f"  Memory Cache: {stats.get('memory_entries', 0)}")
        Message.info(f"  Disk Cache: {stats.get('entry_count', 0)}")
        Message.info(f"  Cache Size: {_format_size(stats.get('cache_size_bytes', 0))}")
        
        # Show cache entries
        _show_cache_entries(cache, show_content, verbose)
        
    except Exception as e:
        Message.error(f"Error getting cache info: {e}")


def _show_cache_entries(cache, show_content, verbose):
    """Show all cache entries"""
    try:
        # Get memory cache entries
        memory_entries = cache._memory_cache.items() if hasattr(cache, '_memory_cache') else []
        
        # Get file cache entries
        file_entries = []
        seen_keys = set()
        if hasattr(cache, 'cache_dir'):
            for file_path in cache.cache_dir.glob("*.pkl"):
                try:
                    with open(file_path, 'rb') as f:
                        value = pickle.load(f)
                    key = file_path.stem
                    if key not in seen_keys:
                        file_entries.append((key, value))
                        seen_keys.add(key)
                except Exception:
                    continue
        
        total_entries = len(memory_entries) + len(file_entries)
        
        if total_entries == 0:
            Message.warning("Cache is empty")
            return
        
        Message.info(f"Cache Entries ({total_entries}):")
        
        # Process memory cache entries
        for key, entry in memory_entries:
            try:
                value = entry.value if hasattr(entry, 'value') else entry
                if isinstance(value, BagCacheEntry):
                    bag_info = value.bag_info
                    file_path = getattr(bag_info, 'file_path', 'Unknown')
                    topics_count = len(getattr(bag_info, 'topics', []))
                    duration = getattr(bag_info, 'duration_seconds', 0)
                    Message.info(f"  • {file_path}")
                    Message.muted(f"    Topics: {topics_count}, Duration: {duration:.1f}s")
            except Exception:
                continue
        
        # Process file cache entries
        for key, value in file_entries:
            try:
                if isinstance(value, BagCacheEntry):
                    bag_info = value.bag_info
                    file_path = getattr(bag_info, 'file_path', 'Unknown')
                    topics_count = len(getattr(bag_info, 'topics', []))
                    duration = getattr(bag_info, 'duration_seconds', 0)
                    Message.info(f"  • {file_path}")
                    Message.muted(f"    Topics: {topics_count}, Duration: {duration:.1f}s")
            except Exception:
                continue
        
    except Exception as e:
        Message.error(f"Error showing cache entries: {e}")


def _clear_cache_entries(cache, bag_path, skip_confirm):
    """Clear cache entries with optional bag path filtering"""
    try:
        stats = cache.get_stats()
        total_entries = stats.get('entry_count', 0) + stats.get('memory_entries', 0)
        
        if total_entries == 0:
            Message.warning("No cache data to clear")
            return
        
        if bag_path:
            # Clear specific bag cache
            bag_path_obj = Path(bag_path)
            cache_key = cache.get_bag_cache_key(bag_path_obj)
            
            cached_data = cache.get(cache_key)
            if not cached_data:
                Message.warning(f"No cache found for bag: {bag_path}")
                return
            
            Message.info(f"Found cache for bag: {bag_path}")
            
            if not skip_confirm:
                confirm = typer.confirm("Clear this cache entry?")
                if not confirm:
                    Message.info("Operation cancelled")
                    return
            
            success = cache.delete(cache_key)
            if success:
                Message.success(f"Successfully cleared cache for {bag_path}")
            else:
                Message.error(f"Failed to clear cache for {bag_path}")
        else:
            # Clear all cache
            Message.info(f"Found {total_entries:,} cache entries")
            
            if not skip_confirm:
                confirm = typer.confirm(f"Clear all {total_entries} cache entries?")
                if not confirm:
                    Message.info("Operation cancelled")
                    return
            
            cache.clear()
            Message.success(f"Successfully cleared {total_entries} cache entries")
            
    except Exception as e:
        Message.error(f"Error clearing cache: {e}")


def _export_cache_entries(cache, output_file, name, bag_path, format, include_messages):
    """Export cache entries to file"""
    try:
        # Get all cache entries
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
                        all_entries.append((key, value, 'file'))
                        seen_keys.add(key)
                except Exception:
                    continue
        
        if not all_entries:
            Message.warning("No cache entries to export")
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
                    except:
                        if bag_path.lower() in key.lower():
                            match = True
                
                if match:
                    filtered_entries.append((key, value, cache_type))
            
            if not filtered_entries:
                Message.warning("No matching cache entries found")
                return
            all_entries = filtered_entries
        
        # Prepare export data
        export_data = _prepare_export_data(all_entries, include_messages)
        
        # Export to file
        output_path = Path(output_file)
        if format == "json":
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
        elif format == "yaml":
            with open(output_path, 'w') as f:
                yaml.dump(export_data, f, default_flow_style=False)
        elif format == "pickle":
            with open(output_path, 'wb') as f:
                pickle.dump(export_data, f)
        else:
            Message.error(f"Unsupported export format: {format}")
            return
        
        Message.success(f"Successfully exported {len(all_entries)} cache entries to {output_path}")
        Message.muted(f"Format: {format}, Messages included: {include_messages}")
        
    except Exception as e:
        Message.error(f"Error exporting cache: {e}")


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
            result['topics'] = bag_info.topics
        
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


def _format_size(size_bytes):
    """Format size in bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"


if __name__ == "__main__":
    app()

