#!/usr/bin/env python3
"""
Extract command for ROS bag topic extraction.
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

app = typer.Typer(name="extract", help="Extract specific topics from ROS bag files")


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
        logger.error(f"Failed to extract from {bag_path}: {e}")
        return {
            'path': str(bag_path),
            'output_path': None,
            'status': 'error',
            'message': str(e),
            'elapsed_time': 0.0
        }


@app.command()
@ndjson_command("extract")
def extract(
    input_bags: Optional[List[str]] = typer.Argument(None, help="Bag file patterns (supports glob and regex)"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", help="Topics to keep (supports fuzzy matching, can be used multiple times)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count - 2)"),
    reverse: bool = typer.Option(False, "--reverse", help="Reverse selection - exclude specified topics instead of including them"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be extracted without doing it"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed extraction information")
):
    """
    Extract specific topics from ROS bag files (supports multiple files and patterns).
    
    Bags must be loaded into cache first using 'rose load'.
    
    Examples:
        rose extract "*.bag" --topics gps imu                                    # Extract from all bag files
        rose extract input.bag --topics /gps/fix -o "{input}_filtered.bag"      # Single file with pattern
        rose extract bag1.bag bag2.bag --topics tf --reverse                    # Multiple files, exclude tf
        rose extract "*.bag" --topics gps --compression lz4 --workers 4         # Parallel extraction with compression
        rose extract "*.bag" --topics gps --dry-run                             # Preview without extraction
    """
    start_total_time = time.time()
    
    try:
        # Get event emitter
    # Using global E emitter (context set by @ndjson_command)
        
        # Validate input arguments
        if not input_bags:
            E.error(
                "INVALID_ARGUMENT",
                "No bag files specified",
                details={"suggestions": ["Provide bag file patterns: rose extract '*.bag' --topics gps"]}
            )
            raise typer.Exit(1)
        
        if not topics:
            E.error(
                "INVALID_ARGUMENT",
                "No topics specified",
                details={"suggestions": ["Use --topics to specify topics: rose extract demo.bag --topics gps imu"]}
            )
            raise typer.Exit(1)
        
        # Validate compression option
        valid_compression = ["none", "bz2", "lz4"]
        if compression not in valid_compression:
            E.error(
                "INVALID_ARGUMENT",
                f"Invalid compression: {compression}",
                details={"valid_options": valid_compression}
            )
            raise typer.Exit(1)
        
        # Stages 1-3: Preparation (fast)
        # Stage 1: Discovery
        E.progress(
            message="Finding bag files",
            mode="stage", 
            stage="discovery",
            stage_index=1,
            total_stages=4
        )
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
            data=[{"path": str(bag), "size_mb": bag.stat().st_size / 1024 / 1024} for bag in valid_bags],
            label="found_bags",
            count=len(valid_bags)
        )
        
        # Stage 2: Cache check
        E.progress(
            message="Checking cache",
            mode="stage",
            stage="cache_check", 
            stage_index=2,
            total_stages=4
        )
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
            output_pattern = "{input}_filtered_{timestamp}.bag"
        else:
            output_pattern = output
        
        # Stage 3: Topic analysis
        E.progress(
            message="Analyzing topics",
            mode="stage",
            stage="topic_analysis",
            stage_index=3,
            total_stages=4
        )
        all_topics_set = set()
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            bag_info = cached_entry.bag_info
            if bag_info and hasattr(bag_info, 'topics') and bag_info.topics:
                bag_topics = bag_info.topics if isinstance(bag_info.topics[0], str) else [topic.name for topic in bag_info.topics]
                all_topics_set.update(bag_topics)
        
        all_topics = list(all_topics_set)
        if not all_topics:
            E.error(
                "NO_TOPICS",
                "No topics found in cached bag analysis",
                details={"bags": [str(b) for b in valid_bags]}
            )
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
            E.error(
                "NO_MATCHING_TOPICS",
                f"No topics match the patterns: {', '.join(topics)}",
                details={
                    "patterns": topics,
                    "available_topics": all_topics[:20],
                    "total_available": len(all_topics)
                }
            )
            raise typer.Exit(1)
        
        # Emit topics data
        E.data(
            data={
                "all_topics": all_topics,
                "topics_to_extract": topics_to_extract,
                "operation": operation,
                "patterns": topics
            },
            label="topics",
            count=len(topics_to_extract)
        )
        
        # If dry run, show preview and return
        if dry_run:
            preview_outputs = []
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            for bag_path in valid_bags:
                if '{input}' in output_pattern:
                    preview_output = output_pattern.replace('{input}', bag_path.stem)
                elif '{timestamp}' in output_pattern:
                    preview_output = output_pattern.replace('{timestamp}', timestamp)
                else:
                    preview_output = f"{bag_path.stem}_{output_pattern}_{timestamp}.bag"
                
                preview_outputs.append({
                    "input": str(bag_path),
                    "output": preview_output
                })
            
            E.data(
                data=preview_outputs,
                label="extraction_plan"
            )
            
            E.done({
                "dry_run": True,
                "would_extract": len(valid_bags),
                "topics_count": len(topics_to_extract)
            })
            return
        
        # Determine number of workers
        if workers is None:
            workers = max(1, os.cpu_count() - 2)
        workers = min(workers, len(valid_bags))
        
        # Emit extraction plan
        E.data(
            data={
                "total_bags": len(valid_bags),
                "workers": workers,
                "compression": compression,
                "topics_count": len(topics_to_extract),
                "output_pattern": output_pattern
            },
            label="extraction_plan"
        )
        
        # Stage 4: Extraction (count mode, 2-phase concurrent)
        results = []
        total_bags = len(valid_bags)
        start_time = time.time()
        total_items = total_bags * 2
        
        # Use ThreadPoolExecutor for parallel extraction
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # Phase 1: Submit all tasks (fast)
            future_to_bag = {}
            for i, bag_path in enumerate(valid_bags, 1):
                # Silent progress callback in headless mode
                def create_progress_callback(bag_name):
                    def progress_callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                        if phase and verbose:
                            logger.debug(f"{bag_name}: {phase}")
                    return progress_callback
                
                progress_callback = create_progress_callback(bag_path.name)
                future = executor.submit(
                    await_sync, 
                    extract_single_bag(bag_path, topics_to_extract, output_pattern, compression, yes, verbose, progress_callback)
                )
                future_to_bag[future] = bag_path
                
                # Report submission progress (first half of items)
                E.progress(
                    message=f"Queued {bag_path.name}",
                    mode="count",
                    current=i,
                    total=total_items,
                    elapsed=time.time() - start_time
                )
            
            # Phase 2: Collect results as they complete (second half of items)
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_bag):
                bag_path = future_to_bag[future]
                completed_count += 1
                current_item = total_bags + completed_count  # Second half
                
                try:
                    result = future.result()
                    results.append(result)
                    E.progress(
                        message=f"Extracted {bag_path.name}",
                        mode="count",
                        current=current_item,
                        total=total_items,
                        elapsed=time.time() - start_time
                    )
                    
                except Exception as e:
                    logger.error(f"Unexpected error extracting {bag_path}: {e}")
                    results.append({
                        'path': str(bag_path),
                        'output_path': None,
                        'status': 'error',
                        'message': f"Unexpected error: {e}",
                        'elapsed_time': 0.0
                    })
                    E.progress(
                        message=f"Failed {bag_path.name}",
                        mode="count",
                        current=current_item,
                        total=total_items,
                        elapsed=time.time() - start_time
                    )
        
        # Calculate summary
        success_count = sum(1 for r in results if r['status'] == 'extracted')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_time = time.time() - start_total_time
        
        # Emit detailed results
        E.data(
            data=[
                {
                    "path": r['path'],
                    "output_path": r.get('output_path'),
                    "status": r['status'],
                    "message": r.get('message', ''),
                    "elapsed": r.get('elapsed_time', 0.0)
                }
                for r in results
            ],
            label="results",
            count=len(results)
        )
        
        # Emit done event
        E.done({
            "extracted_files": success_count,
            "failed_files": error_count,
            "total_files": len(results),
            "topics_count": len(topics_to_extract),
            "elapsed_time": total_time,
            "compression": compression,
            "workers": workers
        })
        
        # Exit with error if any extractions failed
        if error_count > 0:
            raise typer.Exit(1)
        
    except typer.Exit:
        raise
    except Exception as e:
        # Emit error event
        E.error(
            code=type(e).__name__.upper(),
            message=str(e),
            details={'verbose': verbose}
        )
        
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)


# Register extract as the default command with empty name
app.command(name="")(extract)

if __name__ == "__main__":
    app()
