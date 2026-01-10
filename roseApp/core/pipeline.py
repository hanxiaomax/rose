
import asyncio
import glob
import os
import re
import time
from pathlib import Path
from typing import Any, Generator, List, Optional, Tuple, Dict, Set

from roseApp.core.events import LogEvent, ProgressEvent, ResultEvent
from roseApp.core.parser import BagReader
from roseApp.core.writer import BagWriter, WriterOption
from roseApp.core.model import AnalysisLevel

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
    # Map boolean build_index to AnalysisLevel
    # If build_index is True, we use INDEX level
    # If False, we default to QUICK (Metadata) level
    target_level = AnalysisLevel.INDEX if build_index else AnalysisLevel.QUICK
    
    # 1. Find bags
    try:
        # yield from returns the return value of the generator
        bag_files = yield from find_bags(patterns)
    except Exception as e:
        yield LogEvent(f"Discovery failed: {e}", level="ERROR")
        yield ResultEvent(success=False, data=[])
        return []

    if not bag_files:
        return []

    results = []
    reader = BagReader()
    cache_manager = create_bag_cache_manager()

    # 2. Process bags sequentially
    total = len(bag_files)
    for i, bag_path in enumerate(bag_files):
        yield ProgressEvent(i, total, f"Processing {i+1}/{total}")
        yield LogEvent(f"Processing {bag_path.name}...", level="INFO")
        
        try:
            # Load logic embedded here
            cache_manager = create_bag_cache_manager()
            
            # Check cache with level awareness
            # For simplicity in this refactor step, we just check existence for now
            # But ideally we should check if cached level >= target_level
            cached_info = cache_manager.get_analysis(bag_path)
            
            # Determine if we need to load
            start_load = force
            if not start_load:
                if not cached_info:
                    start_load = True
                else:
                    # Check if upgrade needed
                     if target_level == AnalysisLevel.INDEX and not cached_info.has_message_index():
                         start_load = True
                         yield LogEvent(f"Upgrading analysis to INDEX level for {bag_path.name}...", level="INFO")
            
            if start_load:
                yield LogEvent(f"Loading {bag_path.name} (Level: {target_level.value})...", level="INFO")
                
                # Setup callback for progress
                current_phase = "Initializing"
                
                def progress_cb(phase, pct):
                    nonlocal current_phase
                    current_phase = phase
                    # We can't yield from a callback easily without extensive refactoring
                    # So we rely on the orchestrator to yield updates or simple prints?
                    # Since this is async running in sync context, we can't yield.
                    # We'll trust the parser logs or add specific event hooks if needed.
                    pass

                # Run async load
                bag_info, elapsed = await_sync(reader.load_bag_async(str(bag_path), level=target_level, progress_callback=progress_cb))
                
                result = {
                    'path': str(bag_path),
                    'status': 'success',
                    'loaded': True,
                    'level': target_level.value,
                    'time': elapsed,
                    'bag_info': bag_info
                }
                yield ResultEvent(success=True, data=result)
                yield LogEvent(f"Loaded {bag_path.name} in {elapsed:.2f}s", level="SUCCESS")
            else:
                yield LogEvent(f"Using cached analysis for {bag_path.name}", level="INFO")
                result = {
                    'path': str(bag_path),
                    'status': 'success',
                    'loaded': False, 
                    'cached': True,
                    'bag_info': cached_info
                }
                yield ResultEvent(success=True, data=result)
            
            results.append(result)

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
    reader = BagReader()
    
    # Identify topics and uncached bags
    all_topics_set = set()
    uncached_bags = []
    
    for bag_path in bag_files:
        bag_info = cache_manager.get_analysis(bag_path)
        if not bag_info:
            uncached_bags.append(bag_path)
        else:
            if hasattr(bag_info, 'topics') and bag_info.topics:
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
                await_sync(reader.load_bag_async(str(bag_path), level=AnalysisLevel.QUICK))
                
                # Retrieve fresh info
                # Note: load_bag_async caches it, so we can check cache or use return value
                # But to be safe and consistent, we can just use the parser's current state implied ??
                # Actually load_bag_async returns bag_info.
                # But to fit the previous loop structure, let's just re-get from cache.
                cached_info = cache_manager.get_analysis(bag_path)
                if cached_info:
                    for t in cached_info.topics:
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
            
            writer_option = WriterOption(
                topics=final_topics,
                compression=compression,
                overwrite=overwrite
            )
            
            yield ProgressEvent(0, 100, f"Extracting {bag_path.name}")
            start_time = time.time()
            
            # Fetch bag_info for correct bag
            bag_info = cache_manager.get_analysis(bag_path)
            if not bag_info:
                # Should have been loaded by previous step, but just in case
                yield LogEvent(f"Reloading info for {bag_path.name}...", level="DEBUG")
                bag_info, _ = await_sync(reader.load_bag_async(str(bag_path), level=AnalysisLevel.QUICK))
            
            # Perform extraction
            writer = BagWriter()
            result_message, extraction_time = writer.write(
                bag_info,
                str(output_path),
                writer_option
            )
            
            yield ProgressEvent(100, 100, "Extraction complete")
            yield LogEvent(f"Extracted to {output_path.name} in {extraction_time:.3f}s", level="INFO")
            
            res = {
                'path': str(bag_path),
                'output_path': str(output_path),
                'status': 'extracted',
                'message': result_message,
                'topics_count': len(final_topics),
                'elapsed_time': extraction_time,
                'topics_list': final_topics,
                'output_size': output_path.stat().st_size if output_path.exists() else 0
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
    reader = BagReader()
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
            bag_info = cache_manager.get_analysis(bag_path)
            all_topics = []
            
            if bag_info:
                 all_topics = [t.name for t in bag_info.topics]
            else:
                  yield LogEvent("Reading bag info...", level="DEBUG")
                  bag_info, _ = await_sync(reader.load_bag_async(str(bag_path), level=AnalysisLevel.QUICK))
                  all_topics = [t.name for t in bag_info.topics]

            writer_option = WriterOption(
                topics=all_topics,
                compression=compression,
                overwrite=overwrite,
                memory_limit_mb=256
            )
            
            yield ProgressEvent(0, 100, f"Compressing {bag_path.name}")
            start_time = time.time()
            
            # Perform compression (using writer)
            writer = BagWriter()
            result_message, elapsed_time = writer.write(
                bag_info,
                str(output_path),
                writer_option
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

def inspect_orchestrator(bag_path: Path, load_if_missing: bool = False, build_index: bool = False, force: bool = False) -> Generator[Any, None, Dict[str, Any]]:
    """
    Orchestrator for inspecting a bag file.
    """
    target_level = AnalysisLevel.INDEX if build_index else AnalysisLevel.QUICK
    
    yield LogEvent(f"Inspecting {bag_path.name}...", level="INFO")
    
    # Check cache first
    cache_manager = create_bag_cache_manager()
    cached_info = cache_manager.get_analysis(bag_path)
    
    needs_load = force
    reason = "Forced reload" if force else "Unknown reason"
    
    if not cached_info:
        needs_load = True
        reason = "Bag not in cache"
    elif target_level == AnalysisLevel.INDEX and not cached_info.has_message_index():
        needs_load = True
        reason = "Index upgrade required"
    
    if needs_load:
        if not load_if_missing:
             yield LogEvent(f"Bag not in cache: {bag_path}", level="WARN")
             yield ResultEvent(success=False, data={'status': 'not_cached'})
             return {'status': 'not_cached'}
        
        yield LogEvent(f"Loading bag ({reason})...", level="INFO")
        
        reader = BagReader()
        
        try:
             # Run async load
             bag_info, elapsed = await_sync(reader.load_bag_async(str(bag_path), level=target_level))
             yield LogEvent(f"Loaded bag in {elapsed:.2f}s", level="INFO")
             yield ResultEvent(success=True, data={'status': 'success', 'bag_info': bag_info})
             return {'status': 'success', 'bag_info': bag_info}
             
        except Exception as e:
            yield LogEvent(f"Failed to load bag: {e}", level="ERROR")
            yield ResultEvent(success=False, data={'status': 'error', 'message': str(e)})
            return {'status': 'error', 'message': str(e)}

    # Cached available and sufficient
    yield LogEvent(f"Using cached analysis (Level: {cached_info.analysis_level.value})", level="INFO")
    yield ResultEvent(success=True, data={'status': 'success', 'bag_info': cached_info})
    return {'status': 'success', 'bag_info': cached_info}
