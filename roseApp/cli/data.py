"""
Data manipulation command for ROS bag files.

Provides functionality to:
- Export bag data to CSV format
- Merge multiple topics into a single DataFrame
- Apply basic filtering and search operations
- Support interactive and non-interactive modes
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from ..core.parser import create_parser
from ..core.cache import create_bag_cache_manager
from ..core.model import ComprehensiveBagInfo, TopicInfo
from ..core.util import get_logger
from ..ui.common_ui import Message
from .util import LoadingAnimation, filter_topics, check_and_load_bag_cache

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

logger = get_logger("data")
console = Console()
app = typer.Typer(help="Data manipulation commands for ROS bag files")


@app.command()
def data(
    bag_path: Path = typer.Argument(..., help="Path to the ROS bag file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Filter specific topics"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output CSV file path"),
    show_columns: bool = typer.Option(False, "--columns", "-c", help="Show DataFrame column information"),
    show_sample: bool = typer.Option(False, "--sample", "-s", help="Show sample data"),
    sample_size: int = typer.Option(5, "--sample-size", help="Number of sample rows to show"),
    start_time: Optional[str] = typer.Option(None, "--start-time", help="Start time filter (ISO format or seconds)"),
    end_time: Optional[str] = typer.Option(None, "--end-time", help="End time filter (ISO format or seconds)"),
    search: Optional[str] = typer.Option(None, "--search", help="Search text in string columns"),
    include_index: bool = typer.Option(True, "--include-index/--no-index", help="Include timestamp index in CSV"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (auto-load cache, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Show debug logs"),
):
    """
    Data manipulation and analysis for ROS bag files
    
    This command provides comprehensive data operations including:
    - Display DataFrame information for topics
    - Export data to CSV format with filtering
    - Show sample data and column information
    
    If the bag file is not in cache, you will be prompted to load it automatically.
    This command requires DataFrame indexing for full functionality.
    """
    if not PANDAS_AVAILABLE:
        Message.error("Pandas is required for data operations. Please install pandas: pip install pandas", console)
        raise typer.Exit(1)
    
    # Validate bag file exists
    if not bag_path.exists():
        Message.error(f"Bag file not found: {bag_path}", console)
        raise typer.Exit(1)
    
    # Configure logging based on debug flag
    if not debug:
        # Suppress logs in standard output unless debug mode
        import logging
        logging.getLogger().setLevel(logging.CRITICAL)
        logging.getLogger('cache').setLevel(logging.CRITICAL)
        logging.getLogger('root').setLevel(logging.CRITICAL)
    
    # Get cache manager and check current status
    cache_manager = create_bag_cache_manager()
    cached_entry = cache_manager.get_analysis(bag_path)
    
    # Check if bag needs loading or re-loading for DataFrame index
    needs_loading = False
    needs_index = False
    
    if cached_entry is None:
        needs_loading = True
        needs_index = True  # Data command always needs DataFrame index
    elif not cached_entry.bag_info.has_any_dataframes():
        # Data command requires DataFrame index, but current cache doesn't have DataFrames
        needs_index = True
        
    if needs_loading:
        # Bag not in cache at all
        if not yes:
            Message.warning(f"⚠ Bag file {bag_path} is not loaded in cache.", console)
            Message.info("Data operations require DataFrame indexing for full functionality.", console)
            should_load = typer.confirm("Would you like to load it with DataFrame indexing now?", default=True)
            if not should_load:
                Message.warning(f"Operation cancelled. Please load the bag first using: rose load {bag_path}", console)
                raise typer.Exit(1)
        
        if not check_and_load_bag_cache(bag_path, auto_load=True, verbose=verbose, build_index=True, force_load=yes):
            Message.error(f"Bag file '{bag_path}' is not available in cache and loading failed.", console)
            raise typer.Exit(1)
        cached_entry = cache_manager.get_analysis(bag_path)
    elif needs_index:
        # Bag in cache but needs DataFrame index for data operations
        should_rebuild = yes  # Default to yes if --yes flag is used
        
        if not yes:
            Message.warning("⚠ Data operations require DataFrame index, but cached data doesn't have it.", console)
            should_rebuild = typer.confirm("Would you like to rebuild the cache with DataFrame indexing?", default=True)
            if not should_rebuild:
                Message.warning("Continuing with cached data (data operations may be limited).", console)
                # Continue with limited functionality
        
        if should_rebuild:
            Message.info("Rebuilding cache with DataFrame indexing...", console)
            # Clear current cache entry and reload with index
            cache_manager.clear(bag_path)
            if not check_and_load_bag_cache(bag_path, auto_load=True, verbose=verbose, build_index=True, force_load=True):
                Message.error(f"Failed to rebuild cache with DataFrame indexing.", console)
                raise typer.Exit(1)
            cached_entry = cache_manager.get_analysis(bag_path)
    
    # Now we have cached data, proceed with data operations
    bag_info = cached_entry.bag_info
    
    # Get available topics
    available_topics = []
    for topic in bag_info.topics:
        if isinstance(topic, TopicInfo):
            available_topics.append(topic)
        else:
            # Handle legacy string format
            available_topics.append(TopicInfo(name=str(topic), message_type="unknown"))
    
    # Filter topics if specified
    if topics:
        topic_names = [t.name for t in available_topics]
        filtered_topic_names = filter_topics(topic_names, topics, None)
        if not filtered_topic_names:
            Message.error(f"No topics match the patterns: {', '.join(topics)}", console)
            Message.info(f"Available topics: {', '.join(topic_names[:10])}{'...' if len(topic_names) > 10 else ''}", console)
            raise typer.Exit(1)
        
        available_topics = [t for t in available_topics if t.name in filtered_topic_names]
        Message.info(f"Filtered to {len(available_topics)} topics: {', '.join(filtered_topic_names[:5])}{'...' if len(filtered_topic_names) > 5 else ''}", console)
    
    # Display topic information
    _display_data_info(bag_info, available_topics, show_columns, show_sample, sample_size)
    
    # Export to CSV if output path is specified
    if output:
        _export_data_to_csv(bag_info, available_topics, output, start_time, end_time, search, include_index)


def _display_data_info(bag_info: ComprehensiveBagInfo, topics: List[TopicInfo], show_columns: bool, show_sample: bool, sample_size: int):
    """Display data information for the specified topics"""
    from rich.table import Table
    
    # Display topic information
    table = Table(title=f"Data Information for {Path(bag_info.file_path).name}")
    table.add_column("Topic", style="cyan")
    table.add_column("Message Type", style="magenta")
    table.add_column("Messages", justify="right")
    table.add_column("DataFrame", style="green")
    table.add_column("Memory (MB)", justify="right")
    
    total_dataframes = 0
    total_memory = 0
    
    for topic_info in topics:
        if isinstance(topic_info, TopicInfo):
            has_df = "✓" if topic_info.has_dataframe() else "✗"
            memory_mb = f"{topic_info.df_memory_mb:.2f}" if topic_info.df_memory_mb else "N/A"
            
            if topic_info.has_dataframe():
                total_dataframes += 1
                if topic_info.df_memory_mb:
                    total_memory += topic_info.df_memory_mb
            
            table.add_row(
                topic_info.name,
                topic_info.message_type,
                topic_info.count_str,
                has_df,
                memory_mb
            )
        else:
            table.add_row(
                topic_info.name,
                topic_info.message_type,
                "N/A",
                "✗",
                "N/A"
            )
    
    console.print(table)
    console.print(f"\nSummary: {total_dataframes} topics with DataFrames, {total_memory:.2f} MB total memory")
    
    # Show column information if requested
    if show_columns:
        for topic_info in topics:
            if isinstance(topic_info, TopicInfo) and topic_info.has_dataframe():
                df = topic_info.get_dataframe()
                if df is not None:
                    console.print(f"\n[bold cyan]Columns for {topic_info.name}:[/bold cyan]")
                    col_table = Table()
                    col_table.add_column("Column", style="cyan")
                    col_table.add_column("Type", style="magenta")
                    col_table.add_column("Non-Null Count", justify="right")
                    
                    for col in df.columns:
                        dtype = str(df[col].dtype)
                        non_null = df[col].count()
                        col_table.add_row(col, dtype, str(non_null))
                    
                    console.print(col_table)
    
    # Show sample data if requested
    if show_sample:
        for topic_info in topics:
            if isinstance(topic_info, TopicInfo) and topic_info.has_dataframe():
                df = topic_info.get_dataframe()
                if df is not None and len(df) > 0:
                    console.print(f"\n[bold cyan]Sample data for {topic_info.name}:[/bold cyan]")
                    sample_df = df.head(sample_size)
                    
                    # Create a simple table for sample data
                    sample_table = Table()
                    sample_table.add_column("Index", style="dim")
                    for col in sample_df.columns:
                        sample_table.add_column(col, style="white")
                    
                    for idx, row in sample_df.iterrows():
                        row_data = [str(idx)]
                        for col in sample_df.columns:
                            value = str(row[col])
                            if len(value) > 30:
                                value = value[:27] + "..."
                            row_data.append(value)
                        sample_table.add_row(*row_data)
                    
                    console.print(sample_table)


def _export_data_to_csv(
    bag_info: ComprehensiveBagInfo, 
    topics: List[TopicInfo], 
    output_path: Path, 
    start_time: Optional[str], 
    end_time: Optional[str], 
    search: Optional[str], 
    include_index: bool
):
    """Export data to CSV with filtering"""
    processor = DataProcessor()
    
    # Get topic names
    topic_names = [t.name for t in topics]
    
    # Get DataFrames for selected topics
    Message.info(f"Retrieving DataFrames for {len(topic_names)} topics...", console)
    dataframes = processor.get_topic_dataframes(bag_info, topic_names)
    
    if not dataframes:
        Message.error("No DataFrames available for selected topics", console)
        raise typer.Exit(1)
    
    Message.success(f"Found DataFrames for {len(dataframes)} topics", console)
    
    # Set up filters
    filters = {}
    if start_time:
        filters['start_time'] = start_time
    if end_time:
        filters['end_time'] = end_time
    if search:
        filters['search_text'] = search
    
    # Process data - automatically stack multiple topics
    if len(dataframes) > 1:
        Message.info(f"Stacking {len(dataframes)} topic DataFrames by timestamp...", console)
        stacked_df = processor.merge_topic_dataframes(dataframes)
        
        # Apply filters
        if filters:
            Message.info("Applying filters...", console)
            stacked_df = processor.filter_dataframe(stacked_df, filters)
        
        # Export stacked DataFrame
        success = processor.export_to_csv(stacked_df, str(output_path), include_index)
        
        if success:
            Message.success(f"Successfully exported stacked data to: {output_path}", console)
            console.print(f"Total rows: {len(stacked_df)}, Columns: {len(stacked_df.columns)}")
        else:
            Message.error("Failed to export stacked data", console)
            raise typer.Exit(1)
    
    elif len(dataframes) == 1:
        # Single topic export
        topic_name = list(dataframes.keys())[0]
        df = list(dataframes.values())[0]
        
        # Apply filters
        if filters:
            Message.info("Applying filters...", console)
            df = processor.filter_dataframe(df, filters)
        
        success = processor.export_to_csv(df, str(output_path), include_index)
        
        if success:
            Message.success(f"Successfully exported {topic_name} data to: {output_path}", console)
            console.print(f"Total rows: {len(df)}, Columns: {len(df.columns)}")
        else:
            Message.error(f"Failed to export {topic_name} data", console)
            raise typer.Exit(1)
    
    else:
        Message.error("No valid DataFrames to export", console)
        raise typer.Exit(1)


class DataProcessor:
    """Main data processing class for bag file operations"""
    
    def __init__(self):
        self.console = Console()
        self.parser = create_parser()
        self.cache_manager = create_bag_cache_manager()
        self.current_bag_info: Optional[ComprehensiveBagInfo] = None
        self.current_bag_path: Optional[str] = None
    
    def _run_async(self, coro):
        """Helper to run async coroutines in sync context"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    
    async def _load_bag_with_dataframes(self, bag_path: str) -> ComprehensiveBagInfo:
        """Load bag file with DataFrame generation for all topics"""
        if not PANDAS_AVAILABLE:
            raise RuntimeError("Pandas is required for data operations. Please install pandas: pip install pandas")
        
        # Try to get from cache first
        cached_entry = self.cache_manager.get_analysis(Path(bag_path))
        if cached_entry and cached_entry.is_valid(Path(bag_path)):
            logger.debug(f"Using cached bag info for {bag_path}")
            bag_info = cached_entry.bag_info
        else:
            # Load using parser with DataFrame generation
            def progress_callback(phase: str, percent: float):
                logger.debug(f"Loading {bag_path}: {phase} ({percent:.1f}%)")
            
            bag_info, _ = await self.parser.load_bag_async(
                bag_path, 
                build_index=True,  # Enable DataFrame generation
                progress_callback=progress_callback
            )
        
        # Cache the current bag info
        self.current_bag_info = bag_info
        self.current_bag_path = bag_path
        
        return bag_info
    
    def load_bag_sync(self, bag_path: str) -> ComprehensiveBagInfo:
        """Synchronous wrapper for bag loading with DataFrames"""
        return self._run_async(self._load_bag_with_dataframes(bag_path))
    
    def get_topic_dataframes(self, bag_info: ComprehensiveBagInfo, topic_names: List[str]) -> Dict[str, Any]:
        """Get DataFrames for specified topics"""
        dataframes = {}
        
        for topic_name in topic_names:
            # Find topic info
            topic_info = None
            for topic in bag_info.topics:
                if isinstance(topic, TopicInfo) and topic.name == topic_name:
                    topic_info = topic
                    break
                elif isinstance(topic, str) and topic == topic_name:
                    # Handle legacy string format
                    logger.warning(f"Topic {topic_name} found as string, DataFrame may not be available")
                    continue
            
            if topic_info and topic_info.has_dataframe():
                dataframes[topic_name] = topic_info.get_dataframe()
                logger.debug(f"Retrieved DataFrame for topic {topic_name}: {len(dataframes[topic_name])} messages")
            else:
                logger.warning(f"No DataFrame available for topic {topic_name}")
        
        return dataframes
    
    def merge_topic_dataframes(self, dataframes: Dict[str, Any]) -> Any:
        """Stack multiple topic DataFrames by timestamp"""
        if not PANDAS_AVAILABLE:
            raise RuntimeError("Pandas is required for DataFrame merging")
        
        if not dataframes:
            raise ValueError("No DataFrames to merge")
        
        if len(dataframes) == 1:
            return list(dataframes.values())[0]
        
        # Prepare DataFrames for stacking
        prepared_dfs = []
        
        for topic_name, df in dataframes.items():
            if df is None or len(df) == 0:
                logger.warning(f"Skipping empty DataFrame for topic {topic_name}")
                continue
            
            # Add topic name column to identify source
            df_copy = df.copy()
            df_copy['topic'] = topic_name
            
            prepared_dfs.append(df_copy)
        
        if not prepared_dfs:
            raise ValueError("No valid DataFrames to merge")
        
        # Stack all DataFrames and sort by timestamp
        stacked_df = pd.concat(prepared_dfs, ignore_index=False, sort=False)
        
        # Sort by timestamp index
        stacked_df = stacked_df.sort_index()
        
        return stacked_df
    
    def filter_dataframe(self, df: Any, filters: Dict[str, Any]) -> Any:
        """Apply filters to DataFrame"""
        if not PANDAS_AVAILABLE or df is None:
            return df
        
        filtered_df = df.copy()
        
        # Time range filter
        if 'start_time' in filters and filters['start_time'] is not None:
            start_time = pd.to_datetime(filters['start_time'])
            filtered_df = filtered_df[filtered_df.index >= start_time]
        
        if 'end_time' in filters and filters['end_time'] is not None:
            end_time = pd.to_datetime(filters['end_time'])
            filtered_df = filtered_df[filtered_df.index <= end_time]
        
        # Column value filters
        if 'column_filters' in filters:
            for col, condition in filters['column_filters'].items():
                if col in filtered_df.columns:
                    if isinstance(condition, dict):
                        # Handle range conditions
                        if 'min' in condition:
                            filtered_df = filtered_df[filtered_df[col] >= condition['min']]
                        if 'max' in condition:
                            filtered_df = filtered_df[filtered_df[col] <= condition['max']]
                    else:
                        # Handle equality condition
                        filtered_df = filtered_df[filtered_df[col] == condition]
        
        # Text search in string columns
        if 'search_text' in filters and filters['search_text']:
            search_text = filters['search_text'].lower()
            string_columns = filtered_df.select_dtypes(include=['object', 'string']).columns
            
            if len(string_columns) > 0:
                # Create a mask for rows containing the search text in any string column
                search_mask = pd.Series(False, index=filtered_df.index)
                for col in string_columns:
                    search_mask |= filtered_df[col].astype(str).str.lower().str.contains(search_text, na=False)
                
                filtered_df = filtered_df[search_mask]
        
        return filtered_df
    
    def _process_timestamp_columns(self, df: Any) -> Any:
        """Process timestamp columns and index into a single timestamp column in seconds"""
        if not PANDAS_AVAILABLE or df is None:
            return df
        
        df_copy = df.copy()
        
        # Check if timestamp columns exist in columns
        has_sec_col = 'timestamp_sec' in df_copy.columns
        has_ns_col = 'timestamp_ns' in df_copy.columns
        
        # Check if timestamp is in index
        has_timestamp_index = df_copy.index.name == 'timestamp_sec' or 'timestamp' in str(type(df_copy.index)).lower()
        
        # Priority 1: Handle index timestamp (most common case)
        if has_timestamp_index and not has_sec_col:
            # Convert index to timestamp column in seconds
            if df_copy.index.name == 'timestamp_sec':
                df_copy['timestamp'] = df_copy.index
            else:
                # Index might be in nanoseconds or other format
                try:
                    # Try to convert index to seconds
                    index_values = df_copy.index.values
                    if hasattr(index_values[0], 'timestamp'):
                        # Pandas datetime index
                        df_copy['timestamp'] = df_copy.index.values.astype('datetime64[ns]').astype('float64') / 1_000_000_000
                    else:
                        # Numeric index, assume seconds
                        df_copy['timestamp'] = df_copy.index
                except:
                    # Fallback: use index as-is
                    df_copy['timestamp'] = df_copy.index
            
            logger.debug("Converted timestamp index to timestamp column")
        
        # Priority 2: Handle column timestamps
        elif has_sec_col and has_ns_col:
            # Merge timestamp_sec and timestamp_ns columns
            df_copy['timestamp'] = df_copy['timestamp_sec'] + (df_copy['timestamp_ns'] / 1_000_000_000)
            
            # Remove the original timestamp columns
            df_copy = df_copy.drop(columns=['timestamp_sec', 'timestamp_ns'])
            
            logger.debug("Merged timestamp_sec and timestamp_ns columns into single timestamp column")
        
        elif has_sec_col:
            # Only timestamp_sec column exists
            df_copy['timestamp'] = df_copy['timestamp_sec']
            df_copy = df_copy.drop(columns=['timestamp_sec'])
            logger.debug("Converted timestamp_sec column to timestamp")
        
        elif has_ns_col:
            # Only timestamp_ns column exists, convert to seconds
            df_copy['timestamp'] = df_copy['timestamp_ns'] / 1_000_000_000
            df_copy = df_copy.drop(columns=['timestamp_ns'])
            logger.debug("Converted timestamp_ns column to timestamp in seconds")
        
        # Always remove any remaining timestamp columns that might be duplicates
        columns_to_remove = [col for col in df_copy.columns 
                           if col in ['timestamp_sec', 'timestamp_ns'] and col != 'timestamp']
        if columns_to_remove:
            df_copy = df_copy.drop(columns=columns_to_remove)
            logger.debug(f"Removed duplicate timestamp columns: {columns_to_remove}")
        
        # Move timestamp column to the front if it exists
        if 'timestamp' in df_copy.columns:
            cols = ['timestamp'] + [col for col in df_copy.columns if col != 'timestamp']
            df_copy = df_copy[cols]
        
        return df_copy
    
    def export_to_csv(self, df: Any, output_path: str, include_index: bool = True) -> bool:
        """Export DataFrame to CSV file with timestamp processing"""
        if not PANDAS_AVAILABLE or df is None:
            logger.error("Pandas is not available or DataFrame is None")
            return False
        
        try:
            # Process timestamp columns before export
            processed_df = self._process_timestamp_columns(df)
            
            # If we created a timestamp column, don't include the index to avoid duplication
            should_include_index = include_index
            if 'timestamp' in processed_df.columns:
                should_include_index = False
                logger.debug("Excluding index since timestamp column was created")
            
            # Export with processed timestamps
            processed_df.to_csv(output_path, index=should_include_index)
            logger.info(f"Successfully exported {len(processed_df)} rows to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export CSV: {str(e)}")
            return False


@app.command()
def export(
    input_bag: str = typer.Argument(..., help="Input bag file path"),
    output_csv: Optional[str] = typer.Option(None, "--output", "-o", help="Output CSV file path"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Topics to export (supports fuzzy matching, can specify multiple)"),
    start_time: Optional[str] = typer.Option(None, "--start-time", help="Start time filter (ISO format or seconds)"),
    end_time: Optional[str] = typer.Option(None, "--end-time", help="End time filter (ISO format or seconds)"),
    search: Optional[str] = typer.Option(None, "--search", help="Search text in string columns"),
    include_index: bool = typer.Option(True, "--include-index/--no-index", help="Include timestamp index in CSV"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (auto-load cache, etc.)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode")
):
    """Export bag data to CSV format with filtering and merging options
    
    If the bag file is not in cache, you will be prompted to load it automatically.
    This command requires DataFrame indexing for full functionality.
    """
    
    if not PANDAS_AVAILABLE:
        Message.error("Pandas is required for data operations. Please install pandas: pip install pandas", console)
        raise typer.Exit(1)
    
    # Validate input file as Path
    bag_path = Path(input_bag)
    if not bag_path.exists():
        Message.error(f"Bag file not found: {bag_path}", console)
        raise typer.Exit(1)
    
    # Get cache manager and check current status
    cache_manager = create_bag_cache_manager()
    cached_entry = cache_manager.get_analysis(bag_path)
    
    # Check if bag needs loading or re-loading for DataFrame index
    needs_loading = False
    needs_index = False
    
    if cached_entry is None:
        needs_loading = True
        needs_index = True  # Export command always needs DataFrame index
    elif not cached_entry.bag_info.has_any_dataframes():
        # Export command requires DataFrame index, but current cache doesn't have DataFrames
        needs_index = True
        
    if needs_loading:
        # Bag not in cache at all
        if not yes:
            Message.warning(f"⚠ Bag file {bag_path} is not loaded in cache.", console)
            Message.info("Export operations require DataFrame indexing for full functionality.", console)
            should_load = typer.confirm("Would you like to load it with DataFrame indexing now?", default=True)
            if not should_load:
                Message.warning(f"Operation cancelled. Please load the bag first using: rose load {bag_path}", console)
                raise typer.Exit(1)
        
        if not check_and_load_bag_cache(bag_path, auto_load=False, verbose=True, build_index=True, force_load=True):
            Message.error(f"Bag file '{bag_path}' is not available in cache and loading failed.", console)
            raise typer.Exit(1)
        cached_entry = cache_manager.get_analysis(bag_path)
    elif needs_index:
        # Bag in cache but needs DataFrame index for export operations
        should_rebuild = yes  # Default to yes if --yes flag is used
        
        if not yes:
            Message.warning("⚠ Export operations require DataFrame index, but cached data doesn't have it.", console)
            should_rebuild = typer.confirm("Would you like to rebuild the cache with DataFrame indexing?", default=True)
            if not should_rebuild:
                Message.warning("Continuing with cached data (export operations may be limited).", console)
                # Continue with limited functionality
        
        if should_rebuild:
            Message.info("Rebuilding cache with DataFrame indexing...", console)
            # Clear current cache entry and reload with index
            cache_manager.clear(bag_path)
            if not check_and_load_bag_cache(bag_path, auto_load=False, verbose=True, build_index=True, force_load=True):
                Message.error(f"Failed to rebuild cache with DataFrame indexing.", console)
                raise typer.Exit(1)
            cached_entry = cache_manager.get_analysis(bag_path)
    
    # Now we have cached data, get bag_info from cache
    bag_info = cached_entry.bag_info
    
    processor = DataProcessor()
    
    try:
        # Get all available topics
        available_topics = [t.name if isinstance(t, TopicInfo) else str(t) for t in bag_info.topics]
        
        # Interactive mode
        if interactive:
            topics, output_csv, filters = _interactive_export_config(
                bag_info, output_csv, topics, start_time, end_time, search
            )
            
            if not topics:
                console.print("[yellow]No topics selected. Exiting.[/yellow]")
                return
        else:
            # Non-interactive mode
            if not topics:
                # Export all topics
                topics = available_topics
                console.print(f"No topics specified, exporting all {len(topics)} topics")
            else:
                # Apply fuzzy matching to topic patterns
                matched_topics = filter_topics(available_topics, topics)
                if not matched_topics:
                    console.print(f"[red]Error: No topics match the patterns: {', '.join(topics)}[/red]")
                    console.print(f"Available topics: {', '.join(available_topics[:10])}{'...' if len(available_topics) > 10 else ''}")
                    raise typer.Exit(1)
                
                topics = matched_topics
                console.print(f"Matched {len(topics)} topics: {', '.join(topics[:5])}{'...' if len(topics) > 5 else ''}")
            
            # Set up filters
            filters = {}
            if start_time:
                filters['start_time'] = start_time
            if end_time:
                filters['end_time'] = end_time
            if search:
                filters['search_text'] = search
        
        # Generate default output path if not provided
        if not output_csv:
            bag_name = os.path.splitext(os.path.basename(input_bag))[0]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            if len(topics) > 1:
                output_csv = f"{bag_name}_data_{timestamp}.csv"
            else:
                # Single topic - include topic name in filename
                topic_name = topics[0].replace('/', '_')
                output_csv = f"{bag_name}{topic_name}_{timestamp}.csv"
        
        # Get DataFrames for selected topics
        console.print(f"Retrieving DataFrames for {len(topics)} topics...")
        dataframes = processor.get_topic_dataframes(bag_info, topics)
        
        if not dataframes:
            console.print("[red]Error: No DataFrames available for selected topics[/red]")
            raise typer.Exit(1)
        
        console.print(f"Found DataFrames for {len(dataframes)} topics")
        
        # Process data - automatically stack multiple topics
        if len(dataframes) > 1:
            console.print(f"Stacking {len(dataframes)} topic DataFrames by timestamp...")
            stacked_df = processor.merge_topic_dataframes(dataframes)
            
            # Apply filters
            if filters:
                console.print("Applying filters...")
                stacked_df = processor.filter_dataframe(stacked_df, filters)
            
            # Export stacked DataFrame
            success = processor.export_to_csv(stacked_df, output_csv, include_index)
            
            if success:
                console.print(f"[green]Successfully exported stacked data to: {output_csv}[/green]")
                console.print(f"Total rows: {len(stacked_df)}, Columns: {len(stacked_df.columns)}")
            else:
                console.print("[red]Failed to export stacked data[/red]")
                raise typer.Exit(1)
        
        elif len(dataframes) == 1:
            # Single topic export
            topic_name = list(dataframes.keys())[0]
            df = list(dataframes.values())[0]
            
            # Apply filters
            if filters:
                console.print("Applying filters...")
                df = processor.filter_dataframe(df, filters)
            
            success = processor.export_to_csv(df, output_csv, include_index)
            
            if success:
                console.print(f"[green]Successfully exported {topic_name} data to: {output_csv}[/green]")
                console.print(f"Total rows: {len(df)}, Columns: {len(df.columns)}")
            else:
                console.print(f"[red]Failed to export {topic_name} data[/red]")
                raise typer.Exit(1)
        
        else:
            console.print("[red]Error: No valid DataFrames to export[/red]")
            raise typer.Exit(1)
    
    except Exception as e:
        logger.error(f"Export failed: {str(e)}", exc_info=True)
        console.print(f"[red]Error during export: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def info(
    input_bag: str = typer.Argument(..., help="Input bag file path"),
    topics: Optional[List[str]] = typer.Option(None, "--topic", "-t", help="Topics to show info for"),
    show_columns: bool = typer.Option(False, "--columns", "-c", help="Show DataFrame column information"),
    show_sample: bool = typer.Option(False, "--sample", "-s", help="Show sample data"),
    sample_size: int = typer.Option(5, "--sample-size", help="Number of sample rows to show")
):
    """Show information about bag data and available DataFrames"""
    
    if not PANDAS_AVAILABLE:
        console.print("[red]Error: Pandas is required for data operations. Please install pandas: pip install pandas[/red]")
        raise typer.Exit(1)
    
    # Validate input file
    if not os.path.exists(input_bag):
        console.print(f"[red]Error: Input bag file '{input_bag}' does not exist[/red]")
        raise typer.Exit(1)
    
    processor = DataProcessor()
    
    try:
        # Load bag file
        console.print(f"Loading bag file: {input_bag}")
        with LoadingAnimation("Loading bag file and generating DataFrames...") as progress:
            task = progress.add_task("Loading...", total=100)
            bag_info = processor.load_bag_sync(input_bag)
            progress.update(task, completed=100)
        
        # Get available topics
        available_topics = []
        for topic in bag_info.topics:
            if isinstance(topic, TopicInfo):
                available_topics.append(topic)
            else:
                # Handle legacy string format
                available_topics.append(TopicInfo(name=str(topic), message_type="unknown"))
        
        # Filter topics if specified
        if topics:
            filtered_topics = [t for t in available_topics if t.name in topics]
            if not filtered_topics:
                console.print(f"[red]Error: None of the specified topics found in bag file[/red]")
                raise typer.Exit(1)
            available_topics = filtered_topics
        
        # Display topic information
        table = Table(title=f"Data Information for {os.path.basename(input_bag)}")
        table.add_column("Topic", style="cyan")
        table.add_column("Message Type", style="magenta")
        table.add_column("Messages", justify="right")
        table.add_column("DataFrame", style="green")
        table.add_column("Memory (MB)", justify="right")
        
        total_dataframes = 0
        total_memory = 0
        
        for topic_info in available_topics:
            if isinstance(topic_info, TopicInfo):
                has_df = "✓" if topic_info.has_dataframe() else "✗"
                memory_mb = f"{topic_info.df_memory_mb:.2f}" if topic_info.df_memory_mb else "N/A"
                
                if topic_info.has_dataframe():
                    total_dataframes += 1
                    if topic_info.df_memory_mb:
                        total_memory += topic_info.df_memory_mb
                
                table.add_row(
                    topic_info.name,
                    topic_info.message_type,
                    topic_info.count_str,
                    has_df,
                    memory_mb
                )
            else:
                table.add_row(
                    topic_info.name,
                    topic_info.message_type,
                    "N/A",
                    "✗",
                    "N/A"
                )
        
        console.print(table)
        console.print(f"\nSummary: {total_dataframes} topics with DataFrames, {total_memory:.2f} MB total memory")
        
        # Show column information if requested
        if show_columns:
            for topic_info in available_topics:
                if isinstance(topic_info, TopicInfo) and topic_info.has_dataframe():
                    df = topic_info.get_dataframe()
                    if df is not None:
                        console.print(f"\n[bold cyan]Columns for {topic_info.name}:[/bold cyan]")
                        col_table = Table()
                        col_table.add_column("Column", style="cyan")
                        col_table.add_column("Type", style="magenta")
                        col_table.add_column("Non-Null Count", justify="right")
                        
                        for col in df.columns:
                            dtype = str(df[col].dtype)
                            non_null = df[col].count()
                            col_table.add_row(col, dtype, str(non_null))
                        
                        console.print(col_table)
        
        # Show sample data if requested
        if show_sample:
            for topic_info in available_topics:
                if isinstance(topic_info, TopicInfo) and topic_info.has_dataframe():
                    df = topic_info.get_dataframe()
                    if df is not None and len(df) > 0:
                        console.print(f"\n[bold cyan]Sample data for {topic_info.name}:[/bold cyan]")
                        sample_df = df.head(sample_size)
                        
                        # Create a simple table for sample data
                        sample_table = Table()
                        sample_table.add_column("Index", style="dim")
                        for col in sample_df.columns:
                            sample_table.add_column(col, style="white")
                        
                        for idx, row in sample_df.iterrows():
                            row_data = [str(idx)]
                            for col in sample_df.columns:
                                value = str(row[col])
                                if len(value) > 30:
                                    value = value[:27] + "..."
                                row_data.append(value)
                            sample_table.add_row(*row_data)
                        
                        console.print(sample_table)
    
    except Exception as e:
        logger.error(f"Info command failed: {str(e)}", exc_info=True)
        console.print(f"[red]Error getting bag info: {str(e)}[/red]")
        raise typer.Exit(1)


def _interactive_export_config(bag_info, output_csv, topics, start_time, end_time, search):
    """Interactive configuration for export command"""
    
    # Get available topics
    available_topics = []
    for topic in bag_info.topics:
        if isinstance(topic, TopicInfo):
            available_topics.append(topic.name)
        else:
            available_topics.append(str(topic))
    
    console.print(f"\n[bold cyan]Available topics ({len(available_topics)}):[/bold cyan]")
    for i, topic in enumerate(available_topics, 1):
        console.print(f"  {i}. {topic}")
    
    # Topic selection
    if not topics:
        topic_choices = [Choice(value=topic, name=topic) for topic in available_topics]
        topics = inquirer.checkbox(
            message="Select topics to export:",
            choices=topic_choices,
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one topic"
        ).execute()
        
        if not topics:
            return None, None, None, None, None
    
    # Output file
    if not output_csv:
        bag_name = os.path.splitext(os.path.basename(bag_info.file_path if hasattr(bag_info, 'file_path') else 'bag'))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_output = f"{bag_name}_data_{timestamp}.csv"
        
        output_csv = inquirer.text(
            message="Output CSV file path:",
            default=default_output
        ).execute()
        
        if not output_csv:
            return None, None, None, None
    
    # Show info about automatic stacking
    if len(topics) > 1:
        console.print(f"[cyan]Multiple topics selected - will automatically stack by timestamp[/cyan]")
    
    # Filters
    filters = {}
    
    # Time range filter
    use_time_filter = inquirer.confirm(
        message="Apply time range filter?",
        default=bool(start_time or end_time)
    ).execute()
    
    if use_time_filter:
        if not start_time:
            start_time = inquirer.text(
                message="Start time (ISO format or seconds since epoch):",
                default=""
            ).execute()
        
        if not end_time:
            end_time = inquirer.text(
                message="End time (ISO format or seconds since epoch):",
                default=""
            ).execute()
        
        if start_time:
            filters['start_time'] = start_time
        if end_time:
            filters['end_time'] = end_time
    
    # Text search filter
    use_search = inquirer.confirm(
        message="Apply text search filter?",
        default=bool(search)
    ).execute()
    
    if use_search:
        if not search:
            search = inquirer.text(
                message="Search text:",
                default=""
            ).execute()
        
        if search:
            filters['search_text'] = search
    
    return topics, output_csv, filters


if __name__ == "__main__":
    app()
