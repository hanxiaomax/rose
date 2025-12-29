import asyncio
import glob
import os
import re
import time
from pathlib import Path
from typing import Any, Generator, List, Optional, Tuple, Dict

from roseApp.core.events import LogEvent, ProgressEvent, ResultEvent
from roseApp.core.parser import BagParser, ExtractOption
from roseApp.core.cache import create_bag_cache_manager
from roseApp.core.errors import BagFileError, validate_bag_file, RoseError

def await_sync(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

def step_find_bags(patterns: List[str]) -> Generator[Any, None, List[Path]]:
    """
    Generator step to find bag files based on patterns.
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

def step_load_bag(bag_path: Path, build_index: bool = False, force: bool = False, parser: Optional[BagParser] = None) -> Generator[Any, None, Dict[str, Any]]:
    """
    Generator step to load a single bag file.
    """
    yield LogEvent(f"Processing {bag_path.name}...", level="INFO")
    
    try:
        if not parser:
            parser = BagParser()

        # Check cache
        if not force:
            cache_manager = create_bag_cache_manager()
            cached_entry = cache_manager.get_analysis(bag_path)
            
            if cached_entry and cached_entry.is_valid(bag_path):
                yield LogEvent(f"Bag {bag_path.name} already cached", level="INFO")
                yield ResultEvent(success=True, data={
                    'path': str(bag_path),
                    'status': 'already_cached',
                    'message': 'Already in cache'
                })
                return {
                    'path': str(bag_path),
                    'status': 'already_cached',
                    'message': 'Already in cache'
                }

        yield ProgressEvent(0, 100, f"Loading {bag_path.name}")
        yield LogEvent("Starting analysis...", level="DEBUG")

        # Define a callback to bridge async progress to our generator (if we could blocking yield)
        # Since we use await_sync, we can't yield from within the callback effectively without a queue.
        # For simplicity, we trust the async call to finish and yield events around it.
        # But we can try to improve this later.

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
        return result_data

    except Exception as e:
        yield LogEvent(f"Failed to load {bag_path.name}: {e}", level="ERROR")
        yield ResultEvent(success=False, data={
            'path': str(bag_path),
            'status': 'error',
            'message': str(e)
        })
        # We handle exception here by yielding error result, but maybe re-raise if orchestrator expects it?
        # User said "Ensure all exception handling ... in main orchestrator ... capture and translate to LogEvent".
        # So I should probably re-raise or let orchestrator handle it.
        # But `step_load_bag` is a step. If it fails, does the whole pipeline fail?
        # Typically no for batch processing.
        # I'll return the error dict as data, and success=False.
        return {
            'path': str(bag_path),
            'status': 'error',
            'message': str(e)
        }

def load_orchestrator(patterns: List[str], build_index: bool = False, force: bool = False) -> Generator[Any, None, List[Dict[str, Any]]]:
    """
    Main orchestrator for loading bags.
    """
    # 1. Find bags
    try:
        # yield from returns the return value of the generator
        bag_files = yield from step_find_bags(patterns)
    except Exception as e:
        yield LogEvent(f"Discovery failed: {e}", level="ERROR")
        yield ResultEvent(success=False, data=[])
        return []

    if not bag_files:
        return []

    results = []
    parser = BagParser()

    # 2. Process bags sequentially
    total = len(bag_files)
    for i, bag_path in enumerate(bag_files):
        yield ProgressEvent(i, total, f"Processing {i+1}/{total}")
        
        try:
            result = yield from step_load_bag(bag_path, build_index, force, parser)
            results.append(result)
        except Exception as e:
            # Catch unexpected errors in the step
            yield LogEvent(f"Error in step for {bag_path.name}: {e}", level="ERROR")
            results.append({
                'path': str(bag_path),
                'status': 'error',
                'message': str(e)
            })

    yield ProgressEvent(total, total, "All done")
    yield ResultEvent(success=True, data=results)
    return results


def step_extract_bag(
    bag_path: Path, 
    topics: List[str], 
    output_pattern: str, 
    compression: str, 
    overwrite: bool, 
    parser: Optional[BagParser] = None
) -> Generator[Any, None, Dict[str, Any]]:
    """
    Generator step to extract topics from a single bag file.
    """
    yield LogEvent(f"Extracting from {bag_path.name}...", level="INFO")
    
    try:
        if not parser:
            parser = BagParser()

        # Generate output path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_str = output_pattern
        
        # Replace placeholders
        if '{input}' in output_str:
            output_str = output_str.replace('{input}', bag_path.stem)
        if '{timestamp}' in output_str:
            output_str = output_str.replace('{timestamp}', timestamp)
        
        # If no placeholders were found, create a default pattern
        if '{input}' not in output_pattern and '{timestamp}' not in output_pattern:
            output_str = f"{bag_path.stem}_{output_pattern}_{timestamp}.bag"
        
        output_path = Path(output_str)
        
        # Create ExtractOption
        extract_option = ExtractOption(
            topics=topics,
            compression=compression,
            overwrite=overwrite
        )
        
        yield ProgressEvent(0, 100, f"Extracting {bag_path.name}")
        
        # We need a way to capture progress from parser.extract which accepts a callback
        # Since parser.extract is synchronous (based on previous view), we can pass a callback that yields?
        # But we can't yield from a callback called by a sync function easily.
        # However, parser.extract takes a callback.
        # We can unfortunately not yield events *during* the sync call easily unless we change parser to be a generator or use a queue.
        # For now, we'll accept that we get start/end events, or we rely on the parser being fast enough or logging.
        # Wait, if `parser.extract` calls the callback, we can't `yield` from the callback to this generator's consumer.
        # We can strictly only log from the callback if we pass a logger, but we want events.
        # A workaround is to not rely on granular internal progress for now, OR refactor parser.
        # Given constraints, I will emit start event, run extract, emit end event.
        
        start_time = time.time()
        
        # Run extraction
        # Note: parser.extract is blocking.
        result_message, extraction_time = parser.extract(
            str(bag_path),
            str(output_path),
            extract_option
        )
        
        yield ProgressEvent(100, 100, "Extraction complete")
        yield LogEvent(f"Extracted to {output_path.name} in {extraction_time:.3f}s", level="INFO")
        
        result_data = {
            'path': str(bag_path),
            'output_path': str(output_path),
            'status': 'extracted',
            'message': result_message,
            'topics_count': len(topics),
            'elapsed_time': extraction_time
        }
        
        yield ResultEvent(success=True, data=result_data)
        return result_data

    except Exception as e:
        yield LogEvent(f"Failed to extract {bag_path.name}: {e}", level="ERROR")
        return {
            'path': str(bag_path),
            'output_path': None,
            'status': 'error',
            'message': str(e),
            'elapsed_time': 0.0
        }


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
    bag_files = yield from step_find_bags(patterns)
    if not bag_files:
        return []
    
    # 2. Check cache/topics (optional logic from original CLI, simplified here or moved to steps)
    # The original CLI did complex topic filtering based on cache.
    # We should reproduce that logic as a step or inside the orchestrator.
    
    yield LogEvent("Analyzing topics...", level="INFO")
    cache_manager = create_bag_cache_manager()
    parser = BagParser()
    
    # Identify topics per bag or global union? The CLI did global union.
    all_topics_set = set()
    uncached_bags = []
    
    for bag_path in bag_files:
        cached_entry = cache_manager.get_analysis(bag_path)
        if not cached_entry or not cached_entry.is_valid(bag_path):
            uncached_bags.append(bag_path)
        else:
            bag_info = cached_entry.bag_info
            if bag_info and hasattr(bag_info, 'topics') and bag_info.topics:
                 # bag_info.topics can be list of TopicInfo objects or strings depending on version/mock
                 # Based on parser.py: `self._current_bag_info.add_topic(topic_info)` -> TopicInfo objects
                 # But in list comprehension `t.name for t in ...`
                 for t in bag_info.topics:
                     all_topics_set.add(t.name if hasattr(t, 'name') else str(t))

    if uncached_bags:
        if load_if_missing:
            yield LogEvent(f"Loading {len(uncached_bags)} uncached bags...", level="INFO")
            for bag_path in uncached_bags:
                yield from step_load_bag(bag_path, force=True, parser=parser)
                # Re-check cache
                cached_entry = cache_manager.get_analysis(bag_path)
                if cached_entry and cached_entry.bag_info:
                    for t in cached_entry.bag_info.topics:
                        all_topics_set.add(t.name if hasattr(t, 'name') else str(t))
        else:
            # Auto-load metadata only (lightweight) to allow topic resolution
            yield LogEvent(f"Reading metadata for {len(uncached_bags)} uncached bags...", level="INFO")
            for bag_path in uncached_bags:
                # Use load_bag_async directly or step_load_bag with build_index=False
                # step_load_bag yields events which is good for UI
                # We interpret this as a temporary load or implicit load
                yield from step_load_bag(bag_path, build_index=False, force=False, parser=parser)
                
                cached_entry = cache_manager.get_analysis(bag_path)
                if cached_entry and cached_entry.bag_info:
                    for t in cached_entry.bag_info.topics:
                        all_topics_set.add(t.name if hasattr(t, 'name') else str(t))

    all_topics = list(all_topics_set)
    if not all_topics and not uncached_bags:
         yield LogEvent("No topics found in cached bags.", level="ERROR")
         return []

    # Filter topics
    # Logic from CLI filter_topics
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
        result = yield from step_extract_bag(bag_path, final_topics, output_pattern or "{input}_filtered_{timestamp}.bag", compression, overwrite, parser)
        results.append(result)

    yield ProgressEvent(total, total, "All done")
    yield ResultEvent(success=True, data=results)
    return results


def step_compress_bag(
    bag_path: Path, 
    output_pattern: str, 
    compression: str, 
    overwrite: bool, 
    parser: Optional[BagParser] = None
) -> Generator[Any, None, Dict[str, Any]]:
    """
    Generator step to compress a single bag file.
    """
    yield LogEvent(f"Compressing {bag_path.name}...", level="INFO")
    
    try:
        if not parser:
            parser = BagParser()

        # Generate output path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_str = output_pattern
        
        # Replace placeholders
        if '{input}' in output_str:
            output_str = output_str.replace('{input}', bag_path.stem)
        if '{timestamp}' in output_str:
            output_str = output_str.replace('{timestamp}', timestamp)
        if '{compression}' in output_str:
            output_str = output_str.replace('{compression}', compression)
            
        # If no placeholders were found, create a default pattern
        if '{input}' not in output_pattern and '{timestamp}' not in output_pattern and '{compression}' not in output_pattern:
            output_str = f"{bag_path.stem}_{compression}_{timestamp}.bag"
        
        output_path = Path(output_str)
        
        # Get topics (all topics)
        # We need to peek into the bag to get all topics to create ExtractOption
        # We can do a quick load if not cached, or just use parser to get info?
        # Re-using parser.extract requires topics list.
        # parser.load_bag_async can get us topics.
        
        # Check cache first (lightweight)
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(bag_path)
        all_topics = []
        
        if cached_entry and cached_entry.is_valid(bag_path):
             all_topics = [t.name for t in cached_entry.bag_info.topics]
        else:
             # Load just enough to get topics
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
        
        # Calculate stats
        input_size = bag_path.stat().st_size
        output_size = output_path.stat().st_size if output_path.exists() else 0
        compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
        
        yield ProgressEvent(100, 100, "Compression complete")
        yield LogEvent(f"Compressed to {output_path.name} (ratio: {compression_ratio:.1f}%)", level="INFO")
        
        result_data = {
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
        
        yield ResultEvent(success=True, data=result_data)
        return result_data

    except Exception as e:
        yield LogEvent(f"Failed to compress {bag_path.name}: {e}", level="ERROR")
        return {
            'status': 'error',
            'input_file': str(bag_path),
            'error': str(e),
            'message': str(e)
        }


def compress_orchestrator(
    patterns: List[str], 
    output_pattern: str, 
    compression: str = 'lz4', 
    overwrite: bool = False
) -> Generator[Any, None, List[Dict[str, Any]]]:
    """
    Orchestrator for compression.
    """
    bag_files = yield from step_find_bags(patterns)
    if not bag_files:
        return []

    results = []
    parser = BagParser()
    total = len(bag_files)
    
    for i, bag_path in enumerate(bag_files):
        yield ProgressEvent(i, total, f"Compressing {i+1}/{total}")
        result = yield from step_compress_bag(bag_path, output_pattern or "{input}_{compression}_{timestamp}.bag", compression, overwrite, parser)
        results.append(result)

    yield ProgressEvent(total, total, "All done")
    yield ResultEvent(success=True, data=results)
    return results


def step_inspect_bag(
    bag_path: Path, 
    load_if_missing: bool = False, 
    build_index: bool = False,
    force: bool = False,
    parser: Optional[BagParser] = None
) -> Generator[Any, None, Dict[str, Any]]:
    """
    Generator step to inspect a single bag file.
    
    This step ensures the bag is loaded (or loads it if requested) and checks valid cache analysis.
    It does NOT perform the full formatting/printing which is done by the CLI.
    """
    yield LogEvent(f"Inspecting {bag_path.name}...", level="INFO")
    
    try:
        if not parser:
            parser = BagParser()
            
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(bag_path)
        
        # Logic to handle loading if not cached or if upgrade needed
        is_cached = cached_entry is not None and cached_entry.is_valid(bag_path)
        needs_upgrade = False
        
        if is_cached and build_index and not force:
            # Check if we have index
            # Accessing value directly to avoid importing AnalysisLevel Enum
            current_level = getattr(cached_entry.bag_info.analysis_level, 'value', str(cached_entry.bag_info.analysis_level))
            if current_level != 'index':
                needs_upgrade = True
                yield LogEvent("Cache exists but missing message index. Reloading...", level="INFO")
        
        if force or not is_cached or needs_upgrade:
            if force or load_if_missing or needs_upgrade:
                load_mode = "with index" if build_index else "quick"
                msg = f"Loading bag ({load_mode})"
                if force:
                    msg += " (forced)"
                elif needs_upgrade:
                    msg += " (upgrade needed)"
                msg += "..."
                
                yield LogEvent(msg, level="INFO")
                # Reuse step_load_bag to load
                # If needs_upgrade is True, we must force reload
                yield from step_load_bag(bag_path, build_index=build_index, force=(force or needs_upgrade or not is_cached), parser=parser)
                
                # Re-fetch from cache
                cached_entry = cache_manager.get_analysis(bag_path)
                if cached_entry is None:
                    yield LogEvent(f"Failed to load bag into cache", level="ERROR")
                    return {
                        'path': str(bag_path),
                        'status': 'error',
                        'message': 'Failed to load bag into cache'
                    }
            else:
                yield LogEvent(f"Bag not in cache: {bag_path.name}", level="WARN")
                result = {
                    'path': str(bag_path),
                    'status': 'not_cached',
                    'message': 'Bag not in cache'
                }
                yield ResultEvent(success=False, data=result)
                return result
        
        # Retrieve info
        bag_info = cached_entry.bag_info
        
        yield LogEvent(f"Retrieved analysis for {bag_path.name}", level="DEBUG")
        yield ResultEvent(success=True, data={
            'path': str(bag_path),
            'status': 'success',
            'bag_info': bag_info
        })
        
        return {
            'path': str(bag_path),
            'status': 'success',
            'bag_info': bag_info
        }

    except Exception as e:
        yield LogEvent(f"Failed to inspect {bag_path.name}: {e}", level="ERROR")
        result = {
            'path': str(bag_path),
            'status': 'error',
            'message': str(e)
        }
        yield ResultEvent(success=False, data=result)
        return result


def inspect_orchestrator(
    bag_path: Path, 
    load_if_missing: bool = False,
    build_index: bool = False,
    force: bool = False
) -> Generator[Any, None, Dict[str, Any]]:
    """
    Orchestrator for inspection. Single file focused.
    """
    # Validation
    if not bag_path.exists():
        yield LogEvent(f"Bag file not found: {bag_path}", level="ERROR")
        return {'status': 'error', 'message': f"Bag file not found: {bag_path}"}
        
    yield LogEvent(f"Validating {bag_path.name}", level="DEBUG")
    
    # Run inspection step
    result = yield from step_inspect_bag(bag_path, load_if_missing, build_index, force)
    
    # The result event is already yielded by step_inspect_bag
    return result


