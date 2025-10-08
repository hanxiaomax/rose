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
from ..core.event_emitter import get_emitter

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
            emitter = get_emitter()
            emitter.set_context("cache")
            
            cache = get_cache()
            _show_cache_info(cache, show_content, verbose)
        except Exception as e:
            emitter = get_emitter()
            emitter.emit_error(
                "CACHE_ERROR",
                f"Error showing cache: {str(e)}",
                details={"operation": "show"}
            )
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
    try:
        emitter = get_emitter()
        emitter.set_context("cache")
        
        cache = get_cache()
        _export_cache_entries(cache, output_file, name, bag_path, format, include_messages)
    except Exception as e:
        emitter = get_emitter()
        emitter.emit_error(
            "CACHE_EXPORT_ERROR",
            f"Error exporting cache: {str(e)}",
            details={"output_file": output_file, "format": format}
        )
        raise typer.Exit(1)


@app.command("clear")
def cache_clear(
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Clear cache for specific bag file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation (headless mode)")
):
    """Clear cache data"""
    try:
        emitter = get_emitter()
        emitter.set_context("cache")
        
        cache = get_cache()
        _clear_cache_entries(cache, bag_path, yes)
    except Exception as e:
        emitter = get_emitter()
        emitter.emit_error(
            "CACHE_CLEAR_ERROR",
            f"Error clearing cache: {str(e)}",
            details={"bag_path": bag_path}
        )
        raise typer.Exit(1)


# =============================================================================
# Helper Functions - All use EventEmitter
# =============================================================================

def _show_cache_info(cache, show_content, verbose):
    """Show cache information and entries"""
    try:
        emitter = get_emitter()
        stats = cache.get_stats()
        
        # Get all cache entries
        all_entries = _get_all_cache_entries(cache)
        
        # Prepare entries data
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
        
        # Emit cache info as data event
        emitter.emit_data(
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
        emitter.emit_done({
            "entries_count": len(entries_data)
        })
        
    except Exception as e:
        emitter = get_emitter()
        emitter.emit_error(
            "CACHE_INFO_ERROR",
            f"Error getting cache info: {str(e)}"
        )
        raise typer.Exit(1)


def _clear_cache_entries(cache, bag_path, skip_confirm):
    """Clear cache entries with optional bag path filtering"""
    try:
        emitter = get_emitter()
        stats = cache.get_stats()
        total_entries = stats.get('entry_count', 0) + stats.get('memory_entries', 0)
        
        if total_entries == 0:
            emitter.emit_data(
                data={
                    "entries_to_clear": 0,
                    "size_to_free_mb": 0
                },
                label="clear_plan"
            )
            emitter.emit_done({
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
                emitter.emit_data(
                    data={
                        "entries_to_clear": 0,
                        "bag_path": str(bag_path),
                        "found": False
                    },
                    label="clear_plan"
                )
                emitter.emit_done({
                    "cleared_entries": 0,
                    "freed_mb": 0
                })
                return
            
            # Emit clear plan
            emitter.emit_data(
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
                emitter.emit_error(
                    "CONFIRMATION_REQUIRED",
                    "Interactive confirmation not supported in headless mode. Use --yes flag.",
                    details={"bag_path": str(bag_path)}
                )
                raise typer.Exit(1)
            
            success = cache.delete(cache_key)
            
            emitter.emit_done({
                "cleared_entries": 1 if success else 0,
                "freed_mb": size_to_free_mb if success else 0,
                "bag_path": str(bag_path)
            })
        else:
            # Clear all cache
            emitter.emit_data(
                data={
                    "entries_to_clear": total_entries,
                    "size_to_free_mb": size_to_free_mb,
                    "skip_confirm": skip_confirm
                },
                label="clear_plan"
            )
            
            # In headless mode, skip_confirm should be True
            if not skip_confirm:
                emitter.emit_error(
                    "CONFIRMATION_REQUIRED",
                    "Interactive confirmation not supported in headless mode. Use --yes flag.",
                    details={"total_entries": total_entries}
                )
                raise typer.Exit(1)
            
            cache.clear()
            
            emitter.emit_done({
                "cleared_entries": total_entries,
                "freed_mb": size_to_free_mb
            })
            
    except typer.Exit:
        raise
    except Exception as e:
        emitter = get_emitter()
        emitter.emit_error(
            "CACHE_CLEAR_ERROR",
            f"Error clearing cache: {str(e)}",
            details={"bag_path": bag_path}
        )
        raise typer.Exit(1)


def _export_cache_entries(cache, output_file, name, bag_path, format, include_messages):
    """Export cache entries to file"""
    try:
        emitter = get_emitter()
        
        # Get all cache entries
        all_entries = _get_all_cache_entries(cache)
        
        if not all_entries:
            emitter.emit_data(
                data={
                    "output_file": output_file,
                    "format": format,
                    "entries_count": 0
                },
                label="export_plan"
            )
            emitter.emit_done({
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
        
        # Emit export plan
        emitter.emit_data(
            data={
                "output_file": output_file,
                "format": format,
                "entries_count": len(all_entries),
                "include_messages": include_messages
            },
            label="export_plan"
        )
        
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
            emitter.emit_error(
                "INVALID_FORMAT",
                f"Unsupported export format: {format}",
                details={"format": format, "supported": ["json", "yaml", "pickle"]}
            )
            raise typer.Exit(1)
        
        emitter.emit_done({
            "exported_file": str(output_path),
            "format": format,
            "entries_exported": len(all_entries),
            "include_messages": include_messages
        })
        
    except typer.Exit:
        raise
    except Exception as e:
        emitter = get_emitter()
        emitter.emit_error(
            "CACHE_EXPORT_ERROR",
            f"Error exporting cache: {str(e)}",
            details={"output_file": output_file, "format": format}
        )
        raise typer.Exit(1)


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
