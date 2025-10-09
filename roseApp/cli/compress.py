#!/usr/bin/env python3
"""
Compress command for ROS bag file compression.
Headless NDJSON mode - pure event emission.
"""

import os
import asyncio
import concurrent.futures
import glob
import re
import time
from pathlib import Path
from typing import List, Optional
import typer

from ..core.parser import BagParser, ExtractOption
from ..core.logging import get_logger
from ..core.cache import create_bag_cache_manager
from ..core.event_emitter import E, ndjson_command

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(name="compress", help="Compress ROS bag files with different compression algorithms")


def await_sync(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


def find_bag_files(input_patterns: List[str]) -> List[Path]:
    """Find bag files using glob patterns and regex"""
    bag_files = []
    
    for pattern in input_patterns:
        # First try as glob pattern
        if any(char in pattern for char in ['*', '?', '[']):
            expanded = glob.glob(pattern, recursive=True)
            bag_files.extend([Path(f) for f in expanded if f.endswith('.bag')])
        else:
            # Try as direct file path
            path = Path(pattern)
            if path.exists() and path.suffix == '.bag':
                bag_files.append(path)
            else:
                # Try as regex pattern
                try:
                    regex = re.compile(pattern)
                    # Search in current directory and subdirectories
                    for root, dirs, files in os.walk('.'):
                        for file in files:
                            if file.endswith('.bag') and regex.search(file):
                                bag_files.append(Path(root) / file)
                except re.error:
                    pass
    
    # Remove duplicates and sort
    unique_bags = list(set(bag_files))
    unique_bags.sort()
    
    return unique_bags


async def compress_single_bag(
    bag_path: Path, 
    output_pattern: str, 
    compression: str, 
    overwrite: bool, 
    verbose: bool = False, 
    progress_callback=None,
    cache_manager=None
) -> dict:
    """Compress a single bag file"""
    try:
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
        
        # Get all topics from cache if available, otherwise load
        all_topics = []
        if cache_manager:
            cached_entry = cache_manager.get_analysis(bag_path)
            if cached_entry and cached_entry.is_valid(bag_path):
                all_topics = cached_entry.bag_info.get_topic_names()
        
        # If not in cache, load bag info
        if not all_topics:
            parser = BagParser()
            bag_info, _ = await parser.load_bag_async(str(bag_path), build_index=False)
            all_topics = bag_info.get_topic_names()
        
        # Create ExtractOption for compression (include all topics)
        extract_option = ExtractOption(
            topics=all_topics,
            compression=compression,
            overwrite=overwrite,
            memory_limit_mb=256
        )
        
        # Progress callback wrapper
        def progress_wrapper(percent):
            if progress_callback:
                progress_callback(percent)
        
        # Create a new parser instance for each compression
        parser = BagParser()
        
        # Perform the compression using extract functionality
        result_message, elapsed_time = parser.extract(
            str(bag_path), 
            str(output_path), 
            extract_option,
            progress_callback=progress_wrapper
        )
        
        # Get file sizes for compression ratio
        input_size = bag_path.stat().st_size
        output_size = output_path.stat().st_size if output_path.exists() else 0
        compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
        
        return {
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
        
    except Exception as e:
        logger.error(f"Error compressing {bag_path}: {str(e)}")
        return {
            'status': 'error',
            'input_file': str(bag_path),
            'output_file': None,
            'error': str(e),
            'message': str(e)
        }


@app.command()
@ndjson_command("compress")
def compress(
    input_bags: List[str] = typer.Argument(..., help="Bag file patterns (supports glob and regex)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp, {compression} for compression type)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count / 2, max 4)"),
    compression: str = typer.Option("lz4", "--compression", "-c", help="Compression type: bz2, lz4"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be compressed without doing it"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed compression information"),
):
    """
    Compress ROS bag files with different compression algorithms (supports multiple files and patterns).
    
    Bags must be loaded into cache first using 'rose load'.
    
    Examples:
        rose compress "*.bag" --compression lz4                                      # Compress all bag files with LZ4
        rose compress input.bag --compression bz2 -o "{input}_{compression}.bag"    # Single file with pattern
        rose compress bag1.bag bag2.bag --compression lz4 --workers 4               # Multiple files, parallel compression
        rose compress "*.bag" --compression bz2 --dry-run                           # Preview compression without doing it
    """
    start_total_time = time.time()
    
    try:
        # Get event emitter
    # Using global E emitter (context set by @ndjson_command)
        
        # Validate compression option
        valid_compression = ["bz2", "lz4"]
        if compression not in valid_compression:
            E.error(
                "INVALID_ARGUMENT",
                f"Invalid compression: {compression}",
                details={"valid_options": valid_compression}
            )
            raise typer.Exit(1)
        
        # Find bag files using patterns
        E.progress(10, "Finding bag files")
        valid_bags = find_bag_files(input_bags)
        
        if not valid_bags:
            E.error(
                "BAG_NOT_FOUND",
                "No bag files found",
                details={"patterns": input_bags}
            )
            raise typer.Exit(1)
        
        # Emit found bags
        E.data(
            data=[
                {
                    "path": str(bag),
                    "size_mb": bag.stat().st_size / 1024 / 1024
                }
                for bag in valid_bags
            ],
            label="found_bags",
            count=len(valid_bags)
        )
        
        # Check if bags are loaded in cache
        E.progress(20, "Checking cache")
        cache_manager = create_bag_cache_manager()
        uncached_bags = []
        
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            if not cached_entry or not cached_entry.is_valid(bag_path):
                uncached_bags.append(str(bag_path))
        
        if uncached_bags:
            E.error(
                "BAG_NOT_CACHED",
                f"{len(uncached_bags)} bag(s) not in cache",
                details={
                    "uncached_bags": uncached_bags,
                    "suggestions": [
                        "Load bags first: rose load <pattern>",
                        f"Run: rose load {' '.join(input_bags)}"
                    ]
                }
            )
            raise typer.Exit(1)
        
        # Set default output pattern if not specified
        if not output:
            output_pattern = "{input}_{compression}_{timestamp}.bag"
        else:
            output_pattern = output
        
        # Dry run preview
        if dry_run:
            preview_outputs = []
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            for bag_path in valid_bags:
                preview_output = output_pattern
                if '{input}' in preview_output:
                    preview_output = preview_output.replace('{input}', bag_path.stem)
                if '{timestamp}' in preview_output:
                    preview_output = preview_output.replace('{timestamp}', timestamp)
                if '{compression}' in preview_output:
                    preview_output = preview_output.replace('{compression}', compression)
                else:
                    if '{input}' not in output_pattern and '{timestamp}' not in output_pattern:
                        preview_output = f"{bag_path.stem}_{compression}_{timestamp}.bag"
                
                preview_outputs.append({
                    "input": str(bag_path),
                    "output": preview_output,
                    "compression": compression
                })
            
            E.data(
                data=preview_outputs,
                label="compression_plan"
            )
            
            E.done({
                "dry_run": True,
                "would_compress": len(valid_bags),
                "compression": compression
            })
            return
        
        # Determine number of workers - be conservative for compression
        if workers is None:
            # For compression, use fewer workers to avoid memory issues
            workers = max(1, min(4, (os.cpu_count() // 2) if os.cpu_count() else 1))
        else:
            workers = max(1, min(workers, len(valid_bags), 6))  # Cap at 6 workers max
        
        # Emit compression plan
        E.data(
            data={
                "total_bags": len(valid_bags),
                "workers": workers,
                "compression": compression,
                "output_pattern": output_pattern
            },
            label="compression_plan"
        )
        
        # Perform compression
        E.progress(30, "Starting compression")
        results = []
        total_bags = len(valid_bags)
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all compression tasks
            futures = {}
            for bag_path in valid_bags:
                # Silent progress callback in headless mode
                def create_progress_callback(bag_name):
                    def callback(percent):
                        if verbose:
                            logger.debug(f"{bag_name}: {percent:.1f}%")
                    return callback
                
                progress_callback = create_progress_callback(bag_path.name)
                future = executor.submit(
                    await_sync,
                    compress_single_bag(
                        bag_path, 
                        output_pattern, 
                        compression, 
                        overwrite=yes, 
                        verbose=verbose, 
                        progress_callback=progress_callback,
                        cache_manager=cache_manager
                    )
                )
                futures[future] = bag_path
            
            # Collect results as they complete
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                bag_path = futures[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Emit progress
                    percent = 30 + (completed / total_bags) * 60  # 30% to 90%
                    E.progress(
                        percent,
                        f"Compressed {bag_path.name}",
                        step=completed,
                        total_steps=total_bags
                    )
                    
                except Exception as e:
                    logger.error(f"Unexpected error compressing {bag_path}: {str(e)}")
                    results.append({
                        'status': 'error',
                        'input_file': str(bag_path),
                        'output_file': None,
                        'error': str(e),
                        'message': str(e)
                    })
                    completed += 1
        
        # Calculate summary
        success_count = sum(1 for r in results if r['status'] == 'compressed')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_time = time.time() - start_total_time
        
        # Calculate average compression ratio
        successful_results = [r for r in results if r['status'] == 'compressed']
        avg_compression_ratio = (
            sum(r['compression_ratio'] for r in successful_results) / len(successful_results)
            if successful_results else 0
        )
        
        # Emit detailed results
        E.progress(95, "Finalizing")
        E.data(
            data=[
                {
                    "input_file": r['input_file'],
                    "output_file": r.get('output_file'),
                    "status": r['status'],
                    "message": r.get('message', ''),
                    "elapsed": r.get('elapsed_time', 0.0),
                    "input_size_mb": r.get('input_size_mb', 0),
                    "output_size_mb": r.get('output_size_mb', 0),
                    "compression_ratio": r.get('compression_ratio', 0)
                }
                for r in results
            ],
            label="results",
            count=len(results)
        )
        
        # Emit done event
        E.progress(100, "Compression complete")
        E.done({
            "compressed_files": success_count,
            "failed_files": error_count,
            "total_files": len(results),
            "elapsed_time": total_time,
            "compression": compression,
            "workers": workers,
            "avg_compression_ratio": avg_compression_ratio
        })
        
        # Exit with error if any compressions failed
        if error_count > 0:
            raise typer.Exit(1)
        
    except typer.Exit:
        raise
    except Exception as e:
        # Emit error event
        emitter = get_emitter()
        E.error(
            code=type(e).__name__.upper(),
            message=str(e),
            details={'verbose': verbose}
        )
        
        logger.error(f"Compression error: {e}", exc_info=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
