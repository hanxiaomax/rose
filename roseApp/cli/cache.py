#!/usr/bin/env python3
"""
Cache command for ROS bag analysis utilities - Headless NDJSON mode

All output goes through EventEmitter for pure NDJSON event emission.
"""

import json
import yaml
import pickle
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer

from ..core.cache import get_cache, BagCacheEntry
from ..core.event_emitter import E, ndjson_command

app = typer.Typer(name="cache", help="Cache management commands")


@app.callback(invoke_without_command=True)
@ndjson_command("cache")
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
            E.error(
                "CACHE_ERROR",
                f"Error showing cache: {str(e)}",
                operation="show"
            )
            raise typer.Exit(1)


@app.command("export")
@ndjson_command("cache-export")
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
        E.error(
            "CACHE_EXPORT_ERROR",
            f"Error exporting cache: {str(e)}",
            output_file=output_file,
            format=format
        )
        raise typer.Exit(1)


@app.command("clear")
@ndjson_command("cache-clear")
def cache_clear(
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Clear cache for specific bag file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation (headless mode)")
):
    """Clear cache data"""
    try:
        cache = get_cache()
        _clear_cache_entries(cache, bag_path, yes)
    except Exception as e:
        E.error(
            "CACHE_CLEAR_ERROR",
            f"Error clearing cache: {str(e)}",
            bag_path=bag_path
        )
        raise typer.Exit(1)


# =============================================================================
# Helper Functions - All use EventEmitter
# =============================================================================

def _show_cache_info(cache, show_content, verbose):
    """Show cache information and entries"""
    try:
        # Get all cache entries first
        all_entries = _get_all_cache_entries(cache)
        entry_count = len(all_entries)
        
        # Adaptive progress: stage mode for few entries, count mode for many
        if entry_count <= 10:
            # Stage mode for few entries (fast enough)
            E.progress(
                message="Processing cache entries",
                mode="stage",
                stage="processing",
                stage_index=1,
                total_stages=2
            )
            
            # Get stats and process entries
            stats = cache.get_stats()
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
                            "messages_count": sum(getattr(bag_info, 'message_counts', {}).values()),
                            "duration_sec": getattr(bag_info, 'duration_seconds', 0),
                            "size_mb": value.file_size / 1024 / 1024 if value.file_size else 0,
                            "created": value.cache_timestamp,
                            "last_accessed": value.file_mtime
                        })
                    
                    entries_data.append(entry_dict)
                except Exception:
                    continue
            
            E.progress(
                message="Preparing output",
                mode="stage",
                stage="output",
                stage_index=2,
                total_stages=2
            )
        else:
            # Count mode for many entries (show progress)
            stats = cache.get_stats()
            entries_data = []
            start_time = time.time()
            
            for i, (key, value, cache_type) in enumerate(all_entries, 1):
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
                            "messages_count": sum(getattr(bag_info, 'message_counts', {}).values()),
                            "duration_sec": getattr(bag_info, 'duration_seconds', 0),
                            "size_mb": value.file_size / 1024 / 1024 if value.file_size else 0,
                            "created": value.cache_timestamp,
                            "last_accessed": value.file_mtime
                        })
                    
                    entries_data.append(entry_dict)
                    
                    # Report progress every 10 entries or on last entry
                    if i % 10 == 0 or i == entry_count:
                        E.progress(
                            message=f"Processed entry {i}",
                            mode="count",
                            current=i,
                            total=entry_count,
                            elapsed=time.time() - start_time
                        )
                        
                except Exception:
                    continue
        
        # Emit cache info as data event
        E.data(
            data={
                "stats": {
                    "total_entries": stats.get('entry_count', 0) + stats.get('memory_entries', 0),
                    "memory_entries": stats.get('memory_entries', 0),
                    "disk_entries": stats.get('entry_count', 0),
                    "total_size_mb": stats.get('cache_size_bytes', 0) / 1024 / 1024,
                    "cache_dir": str(cache.cache_dir) if hasattr(cache, 'cache_dir') else None
                },
                "entries": entries_data
            },
            label="cache_info",
            count=len(entries_data)
        )
        
        # Emit done event
        E.done({
            "entries_count": len(entries_data)
        })
        
    except Exception as e:
        # Using global E emitter
        E.error(
            "CACHE_INFO_ERROR",
            f"Error getting cache info: {str(e)}"
        )
        raise typer.Exit(1)


def _clear_cache_entries(cache, bag_path, skip_confirm):
    """Clear cache entries with optional bag path filtering"""
    try:
        # Using global E emitter
        stats = cache.get_stats()
        total_entries = stats.get('entry_count', 0) + stats.get('memory_entries', 0)
        
        if total_entries == 0:
            E.data(
                data={
                    "entries_to_clear": 0,
                    "size_to_free_mb": 0
                },
                label="clear_plan"
            )
            E.done({
                "cleared_entries": 0,
                "freed_mb": 0
            })
            return
        
        # Calculate size to free
        size_to_free_mb = stats.get('cache_size_bytes', 0) / 1024 / 1024
        
        if bag_path:
            # Clear specific bag cache
            bag_path_obj = Path(bag_path)
            cache_key = cache.get_bag_cache_key(bag_path_obj)
            
            cached_data = cache.get(cache_key)
            if not cached_data:
                E.data(
                    data={
                        "entries_to_clear": 0,
                        "bag_path": str(bag_path),
                        "found": False
                    },
                    label="clear_plan"
                )
                E.done({
                    "cleared_entries": 0,
                    "freed_mb": 0
                })
                return
            
            # Emit clear plan
            E.data(
                data={
                    "entries_to_clear": 1,
                    "size_to_free_mb": size_to_free_mb,
                    "bag_path": str(bag_path),
                    "skip_confirm": skip_confirm
                },
                label="clear_plan"
            )
            
            # In headless mode, skip_confirm should be True
            if not skip_confirm:
                E.error(
                    "CONFIRMATION_REQUIRED",
                    "Interactive confirmation not supported in headless mode. Use --yes flag.",
                    details={"bag_path": str(bag_path)}
                )
                raise typer.Exit(1)
            
            success = cache.delete(cache_key)
            
            E.done({
                "cleared_entries": 1 if success else 0,
                "freed_mb": size_to_free_mb if success else 0,
                "bag_path": str(bag_path)
            })
        else:
            # Clear all cache
            # Get all entries to clear with progress
            all_entries = _get_all_cache_entries(cache)
            entries_to_clear = len(all_entries)
            
            E.data(
                data={
                    "entries_to_clear": entries_to_clear,
                    "size_to_free_mb": size_to_free_mb,
                    "skip_confirm": skip_confirm
                },
                label="clear_plan"
            )
            
            # In headless mode, skip_confirm should be True
            if not skip_confirm:
                E.error(
                    "CONFIRMATION_REQUIRED",
                    "Interactive confirmation not supported in headless mode. Use --yes flag.",
                    details={"total_entries": entries_to_clear}
                )
                raise typer.Exit(1)
            
            # Adaptive progress for clearing
            if entries_to_clear <= 20:
                # Stage mode for few entries (fast clear)
                E.progress(
                    message="Clearing cache",
                    mode="stage",
                    stage="clearing",
                    stage_index=1,
                    total_stages=1
                )
                cache.clear()
            else:
                # Count mode for many entries - clear one by one with progress
                start_time = time.time()
                cleared_count = 0
                
                for i, (key, value, cache_type) in enumerate(all_entries, 1):
                    try:
                        if cache_type == "memory":
                            # Clear from memory cache
                            if hasattr(cache, '_memory_cache') and key in cache._memory_cache:
                                del cache._memory_cache[key]
                                cleared_count += 1
                        else:
                            # Clear from disk cache
                            success = cache.delete(key)
                            if success:
                                cleared_count += 1
                        
                        # Report progress every 10 entries or on last entry
                        if i % 10 == 0 or i == entries_to_clear:
                            E.progress(
                                message=f"Cleared {cleared_count} entries",
                                mode="count",
                                current=i,
                                total=entries_to_clear,
                                elapsed=time.time() - start_time
                            )
                    except Exception:
                        # Continue clearing other entries even if one fails
                        continue
            
            E.done({
                "cleared_entries": entries_to_clear,
                "freed_mb": size_to_free_mb
            })
            
    except typer.Exit:
        raise
    except Exception as e:
        # Using global E emitter
        E.error(
            "CACHE_CLEAR_ERROR",
            f"Error clearing cache: {str(e)}",
            details={"bag_path": bag_path}
        )
        raise typer.Exit(1)


def _export_cache_entries(cache, output_file, name, bag_path, format, include_messages):
    """Export cache entries to file"""
    try:
        # Get all cache entries
        all_entries = _get_all_cache_entries(cache)
        
        if not all_entries:
            E.data(
                data={
                    "output_file": output_file,
                    "format": format,
                    "entries_count": 0
                },
                label="export_plan"
            )
            E.done({
                "exported_file": output_file,
                "format": format,
                "entries_exported": 0
            })
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
            
            all_entries = filtered_entries
        
        entry_count = len(all_entries)
        
        # Emit export plan
        E.data(
            data={
                "output_file": output_file,
                "format": format,
                "entries_count": entry_count,
                "include_messages": include_messages
            },
            label="export_plan"
        )
        
        # Adaptive progress for export preparation
        if entry_count <= 10:
            # Stage mode for few entries
            E.progress(
                message="Processing entries",
                mode="stage",
                stage="processing",
                stage_index=1,
                total_stages=2
            )
            export_data = _prepare_export_data(all_entries, include_messages)
            
            E.progress(
                message="Writing file",
                mode="stage",
                stage="writing",
                stage_index=2,
                total_stages=2
            )
        else:
            # Count mode for many entries
            start_time = time.time()
            export_data = {
                'metadata': {
                    'export_timestamp': time.time(),
                    'format': format,
                    'include_messages': include_messages,
                    'total_entries': entry_count
                },
                'entries': []
            }
            
            for i, (key, value, cache_type) in enumerate(all_entries, 1):
                # Process each entry with progress
                entry_data = _process_single_entry(key, value, cache_type, include_messages)
                export_data['entries'].append(entry_data)
                
                # Report progress every 5 entries or on last entry
                if i % 5 == 0 or i == entry_count:
                    E.progress(
                        message=f"Processed entry {i}",
                        mode="count",
                        current=i,
                        total=entry_count,
                        elapsed=time.time() - start_time
                    )
        
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
            E.error(
                "INVALID_FORMAT",
                f"Unsupported export format: {format}",
                details={"format": format, "supported": ["json", "yaml", "pickle"]}
            )
            raise typer.Exit(1)
        
        E.done({
            "exported_file": str(output_path),
            "format": format,
            "entries_exported": len(all_entries),
            "include_messages": include_messages
        })
        
    except typer.Exit:
        raise
    except Exception as e:
        # Using global E emitter
        E.error(
            "CACHE_EXPORT_ERROR",
            f"Error exporting cache: {str(e)}",
            details={"output_file": output_file, "format": format}
        )
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
                'messages_count': sum(getattr(bag_info, 'message_counts', {}).values()),
                'duration_sec': getattr(bag_info, 'duration_seconds', 0),
                'size_mb': value.file_size / 1024 / 1024 if value.file_size else 0,
                'created': value.cache_timestamp,
                'last_accessed': value.file_mtime
            })
            
            if include_messages and hasattr(bag_info, 'topics'):
                entry_data['topics'] = [
                    {
                        'name': topic.name,
                        'type': topic.type,
                        'message_count': topic.message_count,
                        'frequency': getattr(topic, 'frequency', 0)
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


if __name__ == "__main__":
    app()
