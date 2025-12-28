#!/usr/bin/env python3
"""
Extract command for ROS bag topic extraction.
"""

import os
import asyncio
import concurrent.futures
import glob
import re
import sys
import time
from pathlib import Path
from typing import List, Optional
import typer

from ..core.parser import BagParser, ExtractOption
from ..core.logging import get_logger
from ..core.cache import create_bag_cache_manager
from ..core.output import get_output

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(name="extract", help="Extract specific topics from ROS bag files")


def await_sync(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


def _load_bag_into_cache(bag_path: Path, out, build_index: bool = False, verbose: bool = False):
    """Load a bag file into cache"""
    try:
        parser = BagParser()
        
        load_msg = f"Loading {bag_path.name}" + (" (building index)" if build_index else "")
        with out.spinner(load_msg):
            bag_info, elapsed_time = await_sync(
                parser.load_bag_async(str(bag_path), build_index=build_index)
            )
        
        if verbose:
            out.success(f"Loaded in {elapsed_time:.2f}s")
        else:
            out.success("Loaded successfully")
        
        return True
    except Exception as e:
        out.error(f"Failed to load: {str(e)}")
        logger.error(f"Error loading bag {bag_path}: {e}")
        return False


def find_bag_files(input_patterns: List[str]) -> List[Path]:
    """Find bag files using glob patterns and regex"""
    bag_files = []
    
    for pattern in input_patterns:
        # First try as glob pattern
        glob_matches = glob.glob(pattern)
        if glob_matches:
            for match in glob_matches:
                path = Path(match)
                if path.exists() and path.suffix == '.bag':
                    bag_files.append(path)
        else:
            # Try as regex pattern in current directory
            try:
                regex = re.compile(pattern)
                current_dir = Path('.')
                for bag_file in current_dir.glob('*.bag'):
                    if regex.search(bag_file.name):
                        bag_files.append(bag_file)
            except re.error:
                # If regex is invalid, treat as literal filename
                path = Path(pattern)
                if path.exists() and path.suffix == '.bag':
                    bag_files.append(path)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_bags = []
    for bag in bag_files:
        if bag not in seen:
            seen.add(bag)
            unique_bags.append(bag)
    
    return unique_bags


def filter_topics(all_topics: List[str], topic_patterns: List[str], exclude_pattern=None):
    """Filter topics using regex patterns"""
    matched_topics = set()
    
    for pattern in topic_patterns:
        try:
            regex = re.compile(pattern)
            for topic in all_topics:
                if regex.search(topic):
                    matched_topics.add(topic)
        except re.error:
            # If not valid regex, try exact match
            if pattern in all_topics:
                matched_topics.add(pattern)
    
    result = list(matched_topics)
    
    if exclude_pattern:
        exclude_regex = re.compile(exclude_pattern)
        result = [t for t in result if not exclude_regex.search(t)]
    
    return result


async def extract_single_bag(
    bag_path: Path, 
    topics_to_extract: List[str], 
    output_pattern: str, 
    compression: str, 
    overwrite: bool, 
    verbose: bool = False, 
    progress_callback=None
) -> dict:
    """Extract topics from a single bag file"""
    try:
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
            topics=topics_to_extract,
            compression=compression,
            overwrite=overwrite
        )
        
        # Initialize parser
        parser = BagParser()
        
        # Execute extraction
        if progress_callback:
            progress_callback("Extracting topics...", 50.0)
        
        result_message, extraction_time = parser.extract(
            str(bag_path),
            str(output_path),
            extract_option
        )
        
        if progress_callback:
            progress_callback("Complete", 100.0)
        
        if verbose:
            logger.info(f"Successfully extracted {len(topics_to_extract)} topics from {bag_path} in {extraction_time:.3f}s")
        
        return {
            'path': str(bag_path),
            'output_path': str(output_path),
            'status': 'extracted',
            'message': 'Successfully extracted topics',
            'topics_count': len(topics_to_extract),
            'elapsed_time': extraction_time
        }
        
    except Exception as e:
        logger.error(f"Failed to extract from {bag_path}: {e}", exc_info=True)
        return {
            'path': str(bag_path),
            'output_path': None,
            'status': 'error',
            'message': str(e),
            'elapsed_time': 0.0
        }


@app.command()
def extract(
    input_bags: Optional[List[str]] = typer.Argument(None, help="Bag file patterns (supports glob and regex)"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", help="Topics to keep (supports fuzzy matching, can be used multiple times)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count - 2)"),
    reverse: bool = typer.Option(False, "--reverse", help="Reverse selection - exclude specified topics instead of including them"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed extraction information"),
    load: bool = typer.Option(False, "--load", help="Load bags if not cached"),
    build_index: bool = typer.Option(False, "--build-index", help="Build index when loading (requires --load)"),
):
    """
    Extract specific topics from ROS bag files (supports multiple files and patterns).
    
    Bags must be loaded into cache first using 'rose load' or use --load option.
    
    Examples:
        rose extract "*.bag" --topics gps imu                                    # Extract from all bag files
        rose extract input.bag --topics /gps/fix -o "{input}_filtered.bag"      # Single file with pattern
        rose extract bag1.bag bag2.bag --topics tf --reverse                    # Multiple files, exclude tf
        rose extract "*.bag" --topics gps --compression lz4 --workers 4         # Parallel extraction with compression
        rose extract "*.bag" --topics gps --load                                 # Auto load if not cached
    """
    start_total_time = time.time()
    out = get_output()
    
    try:
        # Validate input arguments
        if not input_bags:
            out.error(
                "No bag files specified",
                details="Provide bag file patterns: rose extract '*.bag' --topics gps"
            )
            raise typer.Exit(1)
        
        if not topics:
            out.error(
                "No topics specified",
                details="Use --topics to specify topics: rose extract demo.bag --topics gps imu"
            )
            raise typer.Exit(1)
        
        # Validate compression option
        valid_compression = ["none", "bz2", "lz4"]
        if compression not in valid_compression:
            out.error(
                f"Invalid compression: {compression}",
                details=f"Valid options: {', '.join(valid_compression)}"
            )
            raise typer.Exit(1)
        
        # Stage 1: Discovery
        out.info("Finding bag files...")
        valid_bags = find_bag_files(input_bags)
        
        if not valid_bags:
            out.error("No bag files found")
            raise typer.Exit(1)
        
        # Display found bags
        out.info(f"Found {len(valid_bags)} bag file(s):")
        for bag in valid_bags:
            size_mb = bag.stat().st_size / 1024 / 1024
            out.file_info(bag, size_mb)
        
        # Stage 2: Cache check and auto-load if needed
        out.info("Checking cache...")
        cache_manager = create_bag_cache_manager()
        uncached_bags = []
        
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            if not cached_entry or not cached_entry.is_valid(bag_path):
                uncached_bags.append(bag_path)
        
        if uncached_bags:
            if load:
                # Auto-load uncached bags
                out.info(f"Loading {len(uncached_bags)} uncached bag(s)...")
                for bag_path in uncached_bags:
                    _load_bag_into_cache(bag_path, out, build_index=build_index, verbose=verbose)
            else:
                # Ask user if they want to load
                out.warning(f"{len(uncached_bags)} bag(s) not in cache")
                for bag in uncached_bags:
                    out.print(f"  - {bag.name}")
                
                try:
                    out.newline()
                    sys.stdout.write(f"Load {len(uncached_bags)} bag(s) now? (y/N): ")
                    sys.stdout.flush()
                    response = input().strip().lower()
                    if response in ['y', 'yes']:
                        out.info(f"Loading {len(uncached_bags)} uncached bag(s)...")
                        for bag_path in uncached_bags:
                            _load_bag_into_cache(bag_path, out, build_index=False, verbose=verbose)
                    else:
                        out.info("Cancelled")
                        raise typer.Exit(0)
                except (EOFError, KeyboardInterrupt):
                    out.newline()
                    out.info("Cancelled")
                    raise typer.Exit(0)
        
        # Set default output pattern if not specified
        if not output:
            output_pattern = "{input}_filtered_{timestamp}.bag"
        else:
            output_pattern = output
        
        # Stage 3: Topic analysis
        out.info("Analyzing topics...")
        all_topics_set = set()
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            bag_info = cached_entry.bag_info
            if bag_info and hasattr(bag_info, 'topics') and bag_info.topics:
                bag_topics = bag_info.topics if isinstance(bag_info.topics[0], str) else [topic.name for topic in bag_info.topics]
                all_topics_set.update(bag_topics)
        
        all_topics = list(all_topics_set)
        if not all_topics:
            out.error("No topics found in cached bag analysis")
            raise typer.Exit(1)
        
        # Apply topic filtering
        if reverse:
            # Reverse selection: exclude topics that match the patterns
            topics_to_exclude = filter_topics(all_topics, topics, None)
            topics_to_extract = [t for t in all_topics if t not in topics_to_exclude]
            operation = "excluding"
        else:
            # Normal selection: include topics that match the patterns
            topics_to_extract = filter_topics(all_topics, topics, None)
            operation = "including"
        
        if not topics_to_extract:
            out.error(
                f"No topics match the patterns: {', '.join(topics)}",
                details=f"Available topics: {', '.join(all_topics[:10])}{'...' if len(all_topics) > 10 else ''}"
            )
            raise typer.Exit(1)
        
        # Show extraction plan (like dry-run)
        out.newline()
        out.section("Extraction Plan")
        out.info(f"Operation: {operation} {len(topics_to_extract)} of {len(all_topics)} topics")
        out.info("Topics to extract:")
        for topic in sorted(topics_to_extract)[:20]:
            out.print(f"  {topic}")
        if len(topics_to_extract) > 20:
            out.debug(f"  ... and {len(topics_to_extract) - 20} more")
        
        out.newline()
        out.info("Output files:")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        for bag_path in valid_bags:
            preview_output = output_pattern
            if '{input}' in preview_output:
                preview_output = preview_output.replace('{input}', bag_path.stem)
            if '{timestamp}' in preview_output:
                preview_output = preview_output.replace('{timestamp}', timestamp)
            else:
                if '{input}' not in output_pattern and '{timestamp}' not in output_pattern:
                    preview_output = f"{bag_path.stem}_{output_pattern}_{timestamp}.bag"
            out.print(f"  {bag_path.name} -> {preview_output}")
        
        # Ask for confirmation
        if not yes:
            out.newline()
            try:
                sys.stdout.write(f"Extract {len(topics_to_extract)} topics from {len(valid_bags)} bag(s)? (y/N): ")
                sys.stdout.flush()
                response = input().strip().lower()
                if response not in ['y', 'yes']:
                    out.info("Cancelled")
                    return
            except (EOFError, KeyboardInterrupt):
                out.newline()
                out.info("Cancelled")
                return
        
        # Determine number of workers
        if workers is None:
            workers = max(1, (os.cpu_count() or 2) - 2)
        workers = min(workers, len(valid_bags))
        
        if verbose:
            out.newline()
            out.key_value({
                "Total bags": len(valid_bags),
                "Workers": workers,
                "Compression": compression,
                "Topics": len(topics_to_extract),
                "Output pattern": output_pattern
            }, title="Extraction Details")
        
        # Stage 4: Extraction
        results = []
        total_bags = len(valid_bags)
        
        out.newline()
        
        # Format compression display text
        if compression == "none":
            compression_display = "NO COMPRESSION"
        else:
            compression_display = compression.upper()
        
        # Use progress bar for extraction
        with out.progress_bar(total_bags, f"Extracting ({compression_display})") as progress:
            # Use ThreadPoolExecutor for parallel extraction
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                # Submit all tasks
                future_to_bag = {}
                for bag_path in valid_bags:
                    def create_progress_callback(bag_name):
                        def callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                            if phase and verbose:
                                logger.debug(f"{bag_name}: {phase}")
                        return callback
                    
                    cb = create_progress_callback(bag_path.name)
                    future = executor.submit(
                        await_sync, 
                        extract_single_bag(bag_path, topics_to_extract, output_pattern, compression, yes, verbose, cb)
                    )
                    future_to_bag[future] = bag_path
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_bag):
                    bag_path = future_to_bag[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        if verbose:
                            status = result['status']
                            if status == 'extracted':
                                out.debug(f"  Extracted: {bag_path.name} -> {Path(result['output_path']).name}")
                            else:
                                out.debug(f"  Error: {bag_path.name}")
                        
                    except Exception as e:
                        logger.error(f"Unexpected error extracting {bag_path}: {e}")
                        results.append({
                            'path': str(bag_path),
                            'output_path': None,
                            'status': 'error',
                            'message': f"Unexpected error: {e}",
                            'elapsed_time': 0.0
                        })
                    
                    progress.update(progress.task_id, advance=1)
        
        # Calculate summary
        success_count = sum(1 for r in results if r['status'] == 'extracted')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_time = time.time() - start_total_time
        
        # Show results
        out.newline()
        
        if verbose:
            # Show detailed results
            out.section("Results")
            columns = ["Input", "Output", "Status", "Time"]
            rows = [
                [
                    Path(r['path']).name,
                    Path(r['output_path']).name if r.get('output_path') else "-",
                    r['status'],
                    f"{r.get('elapsed_time', 0):.2f}s"
                ]
                for r in results
            ]
            out.table(None, columns, rows)
        
        # Show summary
        out.summary(
            "Extraction Complete" if error_count == 0 else "Extraction Complete (with errors)",
            {
                "Extracted": success_count,
                "Failed": error_count,
                "Topics": len(topics_to_extract),
                "Compression": compression,
                "Time": f"{total_time:.2f}s"
            },
            success=(error_count == 0)
        )
        
        # Exit with error if any extractions failed
        if error_count > 0:
            raise typer.Exit(1)
        
    except typer.Exit:
        raise
    except Exception as e:
        out.error(str(e))
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)


# Register extract as the default command with empty name
app.command(name="")(extract)

if __name__ == "__main__":
    app()
