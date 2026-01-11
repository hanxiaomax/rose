#!/usr/bin/env python3
"""
List and manage cached ROS bag files.
"""

import json
import yaml
import pickle
import sys
import time
from pathlib import Path
from typing import Optional, List
import typer

from ..core.cache import get_cache
from ..core.model import BagInfo
from ..core.output import get_output
from ..tui.dialogs import ask_multi_selection
from ..tui.widgets.question import Answer

app = typer.Typer(name="list", help="List and manage cached bag files")


@app.callback(invoke_without_command=True)
def list_default(
    ctx: typer.Context,
    show_content: bool = typer.Option(False, "--content", "-c", help="Show detailed cache content (CLI mode)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information (CLI mode)")
):
    """List all cached bag files (default command)"""
    if ctx.invoked_subcommand is None:
        out = get_output()
        try:
            # If no flags passed, launch TUI
            if not show_content and not verbose:
                from ..tui.list_app import run_list_app
                run_list_app()
                raise typer.Exit(0)
            
            # Otherwise, show CLI output
            cache = get_cache()
            _show_cache_info(cache, show_content, verbose, out)
        except Exception as e:
            if isinstance(e, typer.Exit):
                raise
            out.error(f"Error showing cache: {str(e)}")
            raise typer.Exit(1)



@app.command("remove")
def list_remove(
    bag_path: Optional[str] = typer.Argument(None, help="Bag file path or ID to remove from cache"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Remove a specific bag file from cache"""
    out = get_output()
    try:
        cache = get_cache()
        
        if bag_path is None:
            # Interactive mode
            all_entries = _get_all_cache_entries(cache)
            if not all_entries:
                out.info("Cache is empty")
                raise typer.Exit(0)
                
            selection_items = []
            for idx, (key, value, _) in enumerate(all_entries, 1):
                name = key
                if isinstance(value, BagInfo):
                    # Match the display format of 'rose list' somewhat
                    bag_name = Path(getattr(value, 'file_path', key)).name
                    name = f"[{idx}] {bag_name}"
                else:
                    name = f"[{idx}] {key}"
                    
                selection_items.append(Answer(text=name, id=str(idx)))
            
            selected = ask_multi_selection("Select caches to remove (Space to toggle, Enter to confirm):", selection_items)
            
            if not selected:
                out.info("No cache entries selected")
                raise typer.Exit(0)
            
            # Map selected numeric IDs back to Cache Keys to ensure safe deletion 
            # (indices shift after deletion, so we can't use IDs sequentially)
            id_to_key_map = {str(idx): key for idx, (key, _, _) in enumerate(all_entries, 1)}
            
            keys_to_remove = []
            for answer in selected:
                key = id_to_key_map.get(answer.id)
                if key:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                 # We skip individual confirmation since user selected them in TUI
                _remove_cache_entry(cache, key, True, out)
        else:
            _remove_cache_entry(cache, bag_path, yes, out)
    except Exception as e:
        out.error(f"Error removing cache entry: {str(e)}")
        raise typer.Exit(1)


@app.command("clear")
def list_clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Clear all cache data"""
    out = get_output()
    try:
        cache = get_cache()
        _clear_all_cache(cache, yes, out)
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
        total_size_mb = stats.get('total_size_bytes', 0) / 1024 / 1024
        cache_dir = str(cache.cache_dir) if hasattr(cache, 'cache_dir') else "N/A"
        
        out.key_value({
            "Total entries": total_entries,
            "Memory entries": stats.get('memory_entries', 0),
            "Disk entries": stats.get('entry_count', 0),
            "Total size": f"{total_size_mb:.2f} MB",
            "Cache directory": out.format_path(cache_dir)
        })
        
        if entry_count == 0:
            out.newline()
            out.info("Cache is empty")
            return
        
        # Process and display entries with ID
        entries_data = []
        for idx, (key, value, cache_type) in enumerate(all_entries, 1):
            try:
                entry_dict = {
                    "id": idx,
                    "key": key,
                    "location": cache_type
                }
                
                if isinstance(value, BagInfo):
                    bag_info = value
                    entry_dict.update({
                        "bag_path": str(getattr(bag_info, 'file_path', 'Unknown')),
                        "topics_count": len(getattr(bag_info, 'topics', [])),
                        "duration_sec": getattr(bag_info, 'duration_seconds', 0),
                        "size_mb": bag_info.file_size / 1024 / 1024 if bag_info.file_size else 0,
                        "has_index": getattr(bag_info, 'has_message_index', lambda: False)()
                    })
                
                entries_data.append(entry_dict)
            except Exception:
                continue
        
        # Display entries
        out.newline()
        out.section(f"Cached Bags ({len(entries_data)})")
        
        if verbose or show_content:
            # Detailed table view
            columns = ["ID", "File", "Topics", "Duration", "Size", "Index", "Location"]
            rows = []
            for e in entries_data:
                bag_name = Path(e.get('bag_path', e['key'])).name
                rows.append([
                    f"[{out.theme.highlight}]{e['id']}[/{out.theme.highlight}]",
                    f"[{out.theme.path}]{bag_name}[/{out.theme.path}]",
                    str(e.get('topics_count', '-')),
                    f"{e.get('duration_sec', 0):.1f}s",
                    f"[{out.theme.muted}]{e.get('size_mb', 0):.1f} MB[/{out.theme.muted}]",
                    f"[{out.theme.success}]Yes[/{out.theme.success}]" if e.get('has_index') else f"[{out.theme.muted}]No[/{out.theme.muted}]",
                    e['location']
                ])
            out.table(None, columns, rows)
        else:
            # Simple list view with ID
            for e in entries_data:
                bag_name = Path(e.get('bag_path', e['key'])).name
                size_mb = e.get('size_mb', 0)
                idx_str = f" [{out.theme.success}][Indexed][/{out.theme.success}]" if e.get('has_index') else ""
                
                out.print(f"  [{out.theme.highlight}][{e['id']}][/{out.theme.highlight}] "
                         f"[{out.theme.path}]{bag_name}[/{out.theme.path}] "
                         f"([{out.theme.muted}]{size_mb:.1f} MB[/{out.theme.muted}]){idx_str}")
        
        out.newline()
        out.info(f"Use 'rose list remove <id|path>' to remove a specific entry")
        out.info(f"Use 'rose list clear --yes' to clear all cache")
        
    except Exception as e:
        out.error(f"Error getting cache info: {str(e)}")
        raise typer.Exit(1)


def _remove_cache_entry(cache, identifier, skip_confirm, out):
    """Remove a specific cache entry by ID or path"""
    all_entries = _get_all_cache_entries(cache)
    
    if not all_entries:
        out.info("Cache is empty")
        return
    
    # Try to parse as ID first
    target_entry = None
    target_key = None
    target_id = None
    try:
        entry_id = int(identifier)
        if 1 <= entry_id <= len(all_entries):
            target_key, target_value, target_type = all_entries[entry_id - 1]
            target_entry = (target_key, target_value, target_type)
            target_id = entry_id
    except ValueError:
        # Not a number, treat as path - need to find the ID
        identifier_path = Path(identifier)
        for idx, (key, value, cache_type) in enumerate(all_entries, 1):
            if isinstance(value, BagInfo):
                bag_info = value
                bag_path = Path(getattr(bag_info, 'file_path', ''))
                if bag_path.name == identifier_path.name or str(bag_path) == str(identifier_path) or key == identifier:
                    target_entry = (key, value, cache_type)
                    target_key = key
                    target_id = idx
                    break
    
    if not target_entry:
        out.error(f"No cache entry found for: {identifier}")
        out.info(f"Use 'rose list' to see all cached bags")
        raise typer.Exit(1)
    
    key, value, cache_type = target_entry
    
    # Collect detailed information about the entry
    bag_name = key
    bag_path_str = "Unknown"
    entry_details = {}
    cache_size_bytes = 0
    
    if isinstance(value, BagInfo):
        bag_info = value
        bag_name = Path(getattr(bag_info, 'file_path', key)).name
        bag_path_str = getattr(bag_info, 'file_path', 'Unknown')
        
        # Collect detailed information
        entry_details = {
            "File": bag_name,
            "Path": bag_path_str,
            "Topics": len(getattr(bag_info, 'topics', [])),
            "Duration": f"{getattr(bag_info, 'duration_seconds', 0):.1f}s",
            "Original size": f"{bag_info.file_size / 1024 / 1024:.1f} MB" if bag_info.file_size else "Unknown",
            "Cache location": cache_type
        }
        
        # Get message counts if available - check deprecated message_counts too just in case
        if hasattr(bag_info, 'total_messages') and bag_info.total_messages:
            entry_details["Total messages"] = f"{bag_info.total_messages:,}"
        
        # Calculate cache file size
        if cache_type == "disk":
            cache_file = cache.cache_dir / f"{key}.pkl"
            if cache_file.exists():
                cache_size_bytes = cache_file.stat().st_size
                entry_details["Cache size"] = f"{cache_size_bytes / 1024:.1f} KB"
    
    # Show what will be removed with details
    out.newline()
    out.section("Cache Entry to Remove")
    if entry_details:
        out.key_value(entry_details)
    else:
        out.info(f"Entry: {bag_name}")
    
    # Confirm
    if not skip_confirm:
        try:
            out.newline()
            sys.stdout.write(f"Remove '{bag_name}' from cache? (y/N): ")
            sys.stdout.flush()
            response = input().strip().lower()
            if response not in ['y', 'yes']:
                out.info("Cancelled")
                return
        except (EOFError, KeyboardInterrupt):
            out.newline()
            out.info("Cancelled")
            return
    
    # Remove the entry - handle both memory and disk cache
    success = False
    cache_file_path = None
    
    if False: # Removed memory cache support
        # Remove from memory cache
        pass
    else:
        # Remove from disk cache - the key is already the hashed filename
        cache_file = cache.cache_dir / f"{key}.pkl"
        cache_file_path = str(cache_file)
        if cache_file.exists():
            cache_file.unlink()
            success = True
    
    if success:
        out.newline()
        freed_size = f"{cache_size_bytes / 1024:.1f} KB" if cache_size_bytes > 0 else "N/A"
        out.success(f"Removed cache entry")
        
        removal_details = {
            "ID": target_id if target_id else "N/A",
            "File": bag_name,
            "Bag path": bag_path_str,
            "Freed": freed_size
        }
        
        # Add cache file path if available
        if cache_file_path:
            removal_details["Cache file"] = cache_file_path
        
        out.key_value(removal_details)
    else:
        out.error(f"Failed to remove: {bag_name}")
        raise typer.Exit(1)


def _clear_all_cache(cache, skip_confirm, out):
    """Clear all cache entries"""
    stats = cache.get_stats()
    total_entries = stats.get('entry_count', 0) + stats.get('memory_entries', 0)
    
    if total_entries == 0:
        out.info("Cache is already empty")
        return
    
    # Calculate size to free
    size_to_free_mb = stats.get('total_size_bytes', 0) / 1024 / 1024
    
    # Get all entries
    all_entries = _get_all_cache_entries(cache)
    entries_to_clear = len(all_entries)
    
    # Collect detailed information for each entry before deletion
    entries_info = []
    total_bags_size = 0
    bag_names = []
    
    for key, value, cache_type in all_entries:
        entry_info = {
            'key': key,
            'cache_type': cache_type,
            'bag_name': key,
            'bag_path': 'Unknown',
            'cache_size': 0,
            'cache_file_path': None
        }
        
        if isinstance(value, BagInfo):
            bag_info = value
            entry_info['bag_name'] = Path(getattr(bag_info, 'file_path', key)).name
            entry_info['bag_path'] = getattr(bag_info, 'file_path', 'Unknown')
            bag_names.append(entry_info['bag_name'])
            
            if bag_info.file_size:
                total_bags_size += bag_info.file_size
            
            # Get cache file size
            if cache_type == "disk":
                cache_file = cache.cache_dir / f"{key}.pkl"
                if cache_file.exists():
                    entry_info['cache_size'] = cache_file.stat().st_size
                    entry_info['cache_file_path'] = str(cache_file)
        
        entries_info.append(entry_info)
    
    # Show what will be cleared with details
    out.newline()
    out.section("Cache Clear Summary")
    out.key_value({
        "Total entries": entries_to_clear,
        "Memory entries": stats.get('memory_entries', 0),
        "Disk entries": stats.get('entry_count', 0),
        "Cache size": f"{size_to_free_mb:.2f} MB",
        "Original bags size": f"{total_bags_size / 1024 / 1024:.1f} MB" if total_bags_size > 0 else "N/A"
    })
    
    if bag_names and entries_to_clear <= 10:
        out.newline()
        out.info("Bags to clear:")
        for name in bag_names:
            out.print(f"  - {name}")
    elif bag_names:
        out.newline()
        out.info(f"Bags to clear: {', '.join(bag_names[:5])}{'...' if len(bag_names) > 5 else ''}")
    
    # Confirm
    if not skip_confirm:
        try:
            out.newline()
            sys.stdout.write(f"Clear all {entries_to_clear} cache entries? (y/N): ")
            sys.stdout.flush()
            response = input().strip().lower()
            if response not in ['y', 'yes']:
                out.info("Cancelled")
                return
        except (EOFError, KeyboardInterrupt):
            out.newline()
            out.info("Cancelled")
            return
    
    # Clear cache with progress
    with out.spinner("Clearing cache..."):
        cache.clear()
    
    # Show detailed information for each deleted entry
    out.newline()
    out.success(f"Cleared {entries_to_clear} entries, freed {size_to_free_mb:.2f} MB")
    out.newline()
    out.section("Deleted Cache Entries")
    
    for idx, entry_info in enumerate(entries_info, 1):
        freed_size = f"{entry_info['cache_size'] / 1024:.1f} KB" if entry_info['cache_size'] > 0 else "N/A"
        
        entry_display = {
            "ID": idx,
            "File": out.format_path(entry_info['bag_name']),
            "Bag path": out.format_path(entry_info['bag_path']),
            "Cache size": freed_size
        }
        
        # Add cache file path if available
        if entry_info['cache_file_path']:
            entry_display["Cache file"] = out.format_path(entry_info['cache_file_path'])
        
        out.key_value(entry_display)
        if idx < len(entries_info):  # Add separator between entries
            out.print("")


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


def _get_all_cache_entries(cache) -> List[tuple]:
    """Get all cache entries from memory and disk"""
    all_entries = []
    
    # Get memory cache entries - Removed
    # if hasattr(cache, '_memory_cache'):
    #    ...
    
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
            
            if isinstance(value, BagInfo):
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


def _bag_cache_to_dict(bag_info, include_messages=False):
    """Convert ComprehensiveBagInfo to dictionary for export"""
    try:
        result = {
            'file_path': getattr(bag_info, 'file_path', 'Unknown'),
            'topics_count': len(getattr(bag_info, 'topics', [])),
            'duration_seconds': getattr(bag_info, 'duration_seconds', 0),
            'last_updated': getattr(bag_info, 'last_updated', 0),
            'file_mtime': getattr(bag_info, 'file_mtime', 0),
            'file_size': getattr(bag_info, 'file_size', 0)
        }
        
        if hasattr(bag_info, 'topics') and bag_info.topics:
            result['topics'] = [
                {
                    'name': getattr(t, 'name', str(t)),
                    'type': getattr(t, 'message_type', 'unknown')
                }
                for t in bag_info.topics
            ]
        
        if hasattr(bag_info, 'total_messages') and bag_info.total_messages:
            result['total_messages'] = bag_info.total_messages
        
        if include_messages and hasattr(bag_info, 'cached_message_topics') and bag_info.cached_message_topics:
            result['cached_message_topics'] = bag_info.cached_message_topics
        
        return result
        
    except Exception as e:
        return {'error': f'Failed to convert bag cache entry: {e}'}


if __name__ == "__main__":
    app()
