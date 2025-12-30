
import asyncio
import glob
import os
import re
import time
from pathlib import Path
from typing import Any, Generator, List, Optional, Tuple, Dict, Set

from roseApp.core.events import LogEvent, ProgressEvent, ResultEvent
from roseApp.core.parser import BagParser, ExtractOption
from roseApp.core.cache import create_bag_cache_manager
from roseApp.core.errors import BagFileError, validate_bag_file

def await_sync(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

def find_bags(patterns: List[str]) -> Generator[Any, None, List[Path]]:
    """
    Find bag files based on patterns.
    """
    yield LogEvent("Scanning directories...", level="INFO")
    yield ProgressEvent(0, 0, "Scanning directories")
    
    bag_files = []
    
    for pattern in patterns:
        try:
            # First try as glob pattern
            glob_matches = glob.glob(pattern)
            if glob_matches:
                for match in glob_matches:
                    path = Path(match)
                    try:
                        validate_bag_file(path)
                        bag_files.append(path)
                    except BagFileError as e:
                        yield LogEvent(f"Skipping invalid file {path}: {e.message}", level="DEBUG")
            else:
                # Try as regex pattern in current directory
                try:
                    regex = re.compile(pattern)
                    current_dir = Path('.')
                    for bag_file in current_dir.glob('*.bag'):
                        if regex.search(bag_file.name):
                            try:
                                validate_bag_file(bag_file)
                                bag_files.append(bag_file)
                            except BagFileError:
                                continue
                except re.error:
                    # If regex is invalid, treat as literal filename
                    path = Path(pattern)
                    try:
                        validate_bag_file(path)
                        bag_files.append(path)
                    except BagFileError:
                        pass
        except Exception as e:
            yield LogEvent(f"Error processing pattern {pattern}: {e}", level="WARN")

    # Remove duplicates while preserving order
    seen = set()
    unique_bags = []
    for bag in bag_files:
        if bag not in seen:
            seen.add(bag)
            unique_bags.append(bag)
            
    if not unique_bags:
        yield LogEvent("No valid bag files found", level="WARN")
    else:
        yield LogEvent(f"Found {len(unique_bags)} bag file(s)", level="INFO")
    
    yield ResultEvent(success=True, data=unique_bags)
    return unique_bags

def load_orchestrator(patterns: List[str], build_index: bool = False, force: bool = False) -> Generator[Any, None, List[Dict[str, Any]]]:
    """
    Main orchestrator for loading bags.
    """
    # 1. Find bags
    try:
        bag_files = yield from find_bags(patterns)
    except Exception as e:
        yield LogEvent(f"Discovery failed: {e}", level="ERROR")
        yield ResultEvent(success=False, data=[])
        return []

    if not bag_files:
        return []

    results = []
    parser = BagParser()
    cache_manager = create_bag_cache_manager()

    # 2. Process bags sequentially
    total = len(bag_files)
    for i, bag_path in enumerate(bag_files):
        yield ProgressEvent(i, total, f"Processing {i+1}/{total}")
        yield LogEvent(f"Processing {bag_path.name}...", level="INFO")
        
        try:
            # Check cache
            if not force:
                cached_entry = cache_manager.get_analysis(bag_path)
                
                if cached_entry and cached_entry.is_valid(bag_path):
                    if build_index and not cached_entry.bag_info.has_message_index():
                        # Needs upgrade
                        pass
                    else:
                        yield LogEvent(f"Bag {bag_path.name} already cached", level="INFO")
                        res = {
                            'path': str(bag_path),
                            'status': 'already_cached',
                            'message': 'Already in cache'
                        }
                        yield ResultEvent(success=True, data=res)
                        results.append(res)
                        continue

            yield ProgressEvent(0, 100, f"Loading {bag_path.name}")
            yield LogEvent("Starting analysis...", level="DEBUG")

            start_time = time.time()
            
            # Run async load
            bag_info, elapsed_time = await_sync(parser.load_bag_async(
                str(bag_path), 
                build_index=build_index
            ))
            
            yield ProgressEvent(100, 100, "Load complete")
            yield LogEvent(f"Successfully loaded {bag_path.name} in {elapsed_time:.3f}s", level="INFO")
            
            result_data = {
                'path': str(bag_path),
                'status': 'loaded',
                'message': 'Successfully loaded into cache',
                'topics_count': len(bag_info.topics) if bag_info.topics else 0,
                'duration': bag_info.duration_seconds if bag_info.duration_seconds else 0,
                'elapsed': elapsed_time
            }
            
            yield ResultEvent(success=True, data=result_data)
            results.append(result_data)

        except Exception as e:
            yield LogEvent(f"Error loading {bag_path.name}: {e}", level="ERROR")
            err_res = {
                'path': str(bag_path),
                'status': 'error',
                'message': str(e)
            }
            results.append(err_res)
            yield ResultEvent(success=False, data=err_res)

    yield ProgressEvent(total, total, "All done")
    yield ResultEvent(success=True, data=results)
    return results

def extract_orchestrator(
    patterns: List[str], 
    topics: List[str], 
    output_pattern: str, 
    compression: str = 'none', 
    overwrite: bool = False,
    reverse: bool = False,
    load_if_missing: bool = False
) -> Generator[Any, None, List[Dict[str, Any]]]:
    """
    Orchestrator for extraction.
    """
    # 1. Find bags
    bag_files = yield from find_bags(patterns)
    if not bag_files:
        return []
    
    if output_pattern is None:
        output_pattern = "{input}_extracted_{timestamp}.bag"
    
    yield LogEvent("Analyzing topics...", level="INFO")
    cache_manager = create_bag_cache_manager()
    parser = BagParser()
    
    # Identify topics and uncached bags
    all_topics_set = set()
    uncached_bags = []
    
    for bag_path in bag_files:
        cached_entry = cache_manager.get_analysis(bag_path)
        if not cached_entry or not cached_entry.is_valid(bag_path):
            uncached_bags.append(bag_path)
        else:
            bag_info = cached_entry.bag_info
            if bag_info and hasattr(bag_info, 'topics') and bag_info.topics:
                 for t in bag_info.topics:
                     all_topics_set.add(t.name if hasattr(t, 'name') else str(t))

    if uncached_bags:
        action_msg = "Loading" if load_if_missing else "Reading metadata for"
        yield LogEvent(f"{action_msg} {len(uncached_bags)} uncached bags...", level="INFO")
        
        for bag_path in uncached_bags:
            try:
                # Decide load type
                build_idx = False # Extraction doesn't strictly need index, just connection info
                yield LogEvent(f"Loading {bag_path.name}...", level="DEBUG")
                # Load synchronously
                await_sync(parser.load_bag_async(str(bag_path), build_index=build_idx))
                
                # Retrieve fresh info
                # Note: load_bag_async caches it, so we can check cache or use return value
                # But to be safe and consistent, we can just use the parser's current state implied ??
                # Actually load_bag_async returns bag_info.
                # But to fit the previous loop structure, let's just re-get from cache.
                cached_entry = cache_manager.get_analysis(bag_path)
                if cached_entry and cached_entry.bag_info:
                    for t in cached_entry.bag_info.topics:
                        all_topics_set.add(t.name if hasattr(t, 'name') else str(t))
            except Exception as e:
                yield LogEvent(f"Failed to load {bag_path.name}: {e}", level="WARN")

    all_topics = list(all_topics_set)
    if not all_topics and not uncached_bags:
         yield LogEvent("No topics found in cached bags.", level="ERROR")
         return []

    # Filter topics
    matched_topics = set()
    for pattern in topics:
        try:
            regex = re.compile(pattern)
            for topic in all_topics:
                if regex.search(topic):
                    matched_topics.add(topic)
        except re.error:
             if pattern in all_topics:
                matched_topics.add(pattern)
    
    final_topics = list(matched_topics)
    if reverse:
        final_topics = [t for t in all_topics if t not in matched_topics]
    
    if not final_topics:
        yield LogEvent("No matching topics found.", level="ERROR")
        return []
        
    yield LogEvent(f"Selected {len(final_topics)} topics for extraction", level="INFO")

    # 3. Extract
    results = []
    total = len(bag_files)
    for i, bag_path in enumerate(bag_files):
        yield ProgressEvent(i, total, f"Extracting {i+1}/{total}")
        yield LogEvent(f"Extracting from {bag_path.name}...", level="INFO")
        
        try:
            # Generate output path
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_str = output_pattern
            if '{input}' in output_str:
                output_str = output_str.replace('{input}', bag_path.stem)
            if '{timestamp}' in output_str:
                output_str = output_str.replace('{timestamp}', timestamp)
            if '{input}' not in output_pattern and '{timestamp}' not in output_pattern:
                output_str = f"{bag_path.stem}_{output_pattern}_{timestamp}.bag"
            
            output_path = Path(output_str)
            
            extract_option = ExtractOption(
                topics=final_topics,
                compression=compression,
                overwrite=overwrite
            )
            
            yield ProgressEvent(0, 100, f"Extracting {bag_path.name}")
            start_time = time.time()
            
            result_message, extraction_time = parser.extract(
                str(bag_path),
                str(output_path),
                extract_option
            )
            
            yield ProgressEvent(100, 100, "Extraction complete")
            yield LogEvent(f"Extracted to {output_path.name} in {extraction_time:.3f}s", level="INFO")
            
            res = {
                'path': str(bag_path),
                'output_path': str(output_path),
                'status': 'extracted',
                'message': result_message,
                'topics_count': len(final_topics),
                'elapsed_time': extraction_time
            }
            yield ResultEvent(success=True, data=res)
            results.append(res)
            
        except Exception as e:
            yield LogEvent(f"Failed to extract {bag_path.name}: {e}", level="ERROR")
            err_res = {
                'path': str(bag_path),
                'output_path': None,
                'status': 'error',
                'message': str(e),
                'elapsed_time': 0.0
            }
            results.append(err_res)

    yield ProgressEvent(total, total, "All done")
    yield ResultEvent(success=True, data=results)
    return results

def compress_orchestrator(
    patterns: List[str], 
    output_pattern: str, 
    compression: str = 'lz4', 
    overwrite: bool = False
) -> Generator[Any, None, List[Dict[str, Any]]]:
    """
    Orchestrator for compression.
    """
    bag_files = yield from find_bags(patterns)
    if not bag_files:
        return []

    if output_pattern is None:
        output_pattern = "{input}_{compression}_{timestamp}.bag"

    results = []
    parser = BagParser()
    cache_manager = create_bag_cache_manager()
    total = len(bag_files)
    
    for i, bag_path in enumerate(bag_files):
        yield ProgressEvent(i, total, f"Compressing {i+1}/{total}")
        yield LogEvent(f"Compressing {bag_path.name}...", level="INFO")
        
        try:
            # Generate output path
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_str = output_pattern
            if '{input}' in output_str:
                output_str = output_str.replace('{input}', bag_path.stem)
            if '{timestamp}' in output_str:
                output_str = output_str.replace('{timestamp}', timestamp)
            if '{compression}' in output_str:
                output_str = output_str.replace('{compression}', compression)
            if '{input}' not in output_pattern and '{timestamp}' not in output_pattern and '{compression}' not in output_pattern:
                output_str = f"{bag_path.stem}_{compression}_{timestamp}.bag"
            
            output_path = Path(output_str)
            
            # Get topics
            cached_entry = cache_manager.get_analysis(bag_path)
            all_topics = []
            
            if cached_entry and cached_entry.is_valid(bag_path):
                 all_topics = [t.name for t in cached_entry.bag_info.topics]
            else:
                 yield LogEvent("Reading bag info...", level="DEBUG")
                 bag_info, _ = await_sync(parser.load_bag_async(str(bag_path), build_index=False))
                 all_topics = [t.name for t in bag_info.topics]

            extract_option = ExtractOption(
                topics=all_topics,
                compression=compression,
                overwrite=overwrite,
                memory_limit_mb=256
            )
            
            yield ProgressEvent(0, 100, f"Compressing {bag_path.name}")
            start_time = time.time()
            
            result_message, elapsed_time = parser.extract(
                str(bag_path),
                str(output_path),
                extract_option
            )
            
            # Stats
            input_size = bag_path.stat().st_size
            output_size = output_path.stat().st_size if output_path.exists() else 0
            compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
            
            yield ProgressEvent(100, 100, "Compression complete")
            yield LogEvent(f"Compressed to {output_path.name} (ratio: {compression_ratio:.1f}%)", level="INFO")
            
            res = {
                'status': 'compressed',
                'input_file': str(bag_path),
                'output_file': str(output_path),
                'compression': compression,
                'elapsed_time': elapsed_time,
                'message': result_message,
                'topics_count': len(all_topics),
                'input_size_mb': input_size / 1024 / 1024,
                'output_size_mb': output_size / 1024 / 1024,
                'compression_ratio': compression_ratio
            }
            yield ResultEvent(success=True, data=res)
            results.append(res)

        except Exception as e:
            yield LogEvent(f"Failed to compress {bag_path.name}: {e}", level="ERROR")
            err_res = {
                'status': 'error',
                'input_file': str(bag_path),
                'error': str(e),
                'message': str(e)
            }
            results.append(err_res)

    yield ProgressEvent(total, total, "All done")
    yield ResultEvent(success=True, data=results)
    return results

def inspect_orchestrator(
    bag_path: Path, 
    load_if_missing: bool = False,
    build_index: bool = False,
    force: bool = False
) -> Generator[Any, None, Dict[str, Any]]:
    """
    Orchestrator for inspection. Single file focused.
    """
    if not bag_path.exists():
        yield LogEvent(f"Bag file not found: {bag_path}", level="ERROR")
        return {'status': 'error', 'message': f"Bag file not found: {bag_path}"}
        
    yield LogEvent(f"Inspecting {bag_path.name}...", level="INFO")
    
    try:
        parser = BagParser()
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(bag_path)
        
        is_cached = cached_entry is not None and cached_entry.is_valid(bag_path)
        needs_upgrade = False
        
        if is_cached and build_index and not force:
            current_level = getattr(cached_entry.bag_info.analysis_level, 'value', str(cached_entry.bag_info.analysis_level))
            if current_level != 'index':
                needs_upgrade = True
                yield LogEvent("Cache exists but missing message index. Reloading...", level="INFO")
        
        if force or not is_cached or needs_upgrade:
            if force or load_if_missing or needs_upgrade:
                load_mode = "with index" if build_index else "quick"
                msg = f"Loading bag ({load_mode})"
                if force: msg += " (forced)"
                elif needs_upgrade: msg += " (upgrade needed)"
                msg += "..."
                
                yield LogEvent(msg, level="INFO")
                
                # Load
                try:
                    await_sync(parser.load_bag_async(str(bag_path), build_index=build_index))
                    # Reload cache
                    cached_entry = cache_manager.get_analysis(bag_path)
                    if cached_entry is None:
                        raise Exception("Failed to retrieve analysis after load")
                except Exception as e:
                    yield LogEvent(f"Failed to load bag: {e}", level="ERROR")
                    res = {'path': str(bag_path), 'status': 'error', 'message': str(e)}
                    yield ResultEvent(success=False, data=res)
                    return res
            else:
                yield LogEvent(f"Bag not in cache: {bag_path.name}", level="WARN")
                res = {'path': str(bag_path), 'status': 'not_cached', 'message': 'Bag not in cache'}
                yield ResultEvent(success=False, data=res)
                return res
        
        bag_info = cached_entry.bag_info
        yield LogEvent(f"Retrieved analysis for {bag_path.name}", level="DEBUG")
        
        res = {
            'path': str(bag_path),
            'status': 'success',
            'bag_info': bag_info
        }
        yield ResultEvent(success=True, data=res)
        return res

    except Exception as e:
        yield LogEvent(f"Failed to inspect {bag_path.name}: {e}", level="ERROR")
        res = {'path': str(bag_path), 'status': 'error', 'message': str(e)}
        yield ResultEvent(success=False, data=res)
        return res
