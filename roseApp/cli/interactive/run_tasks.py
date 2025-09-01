#!/usr/bin/env python3
"""
Background task execution for Rose interactive run environment
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from ...core.parser import ExtractOption
from ...core.util import get_logger
from ..util import check_and_load_bag_cache
from .run_output import StreamingRenderer, StreamingProgress, ResultFormatter

logger = get_logger("run_tasks")


class TaskExecutor:
    """Handles execution of background tasks"""
    
    def __init__(self, runner):
        self.runner = runner
        self.console = runner.console
        self.parser = runner.parser
        self.cache_manager = runner.cache_manager
        self.renderer = StreamingRenderer(runner.console)
    
    def _run_async(self, coro):
        """Helper to run async coroutines in sync context"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    
    def execute_task(self, task_id: str, command: str, args: Dict[str, Any], callback):
        """Execute a background task"""
        from .run import TaskResult
        
        try:
            result = TaskResult(
                task_id=task_id,
                command=command,
                status='running',
                start_time=time.time()
            )
            
            self.runner.running_tasks[task_id] = result
            
            # Execute the actual command
            if command == 'load':
                result.result = self._task_load_bag(args)
            elif command == 'extract':
                result.result = self._task_extract_topics(args)
            elif command == 'inspect':
                result.result = self._task_inspect_bag(args)
            elif command == 'compress':
                result.result = self._task_compress_bags(args)
            elif command == 'data':
                result.result = self._task_export_data(args)
            else:
                result.error = f"Unknown command: {command}"
                result.status = 'failed'
            
            if result.error is None:
                result.status = 'completed'
            else:
                result.status = 'failed'
            
            result.end_time = time.time()
            
            # Add to history
            self.runner.state.task_history.append(result)
            
            # Call completion callback if provided
            if callback:
                callback(result)
                
        except Exception as e:
            result.error = str(e)
            result.status = 'failed'
            result.end_time = time.time()
            logger.error(f"Task execution error: {e}")
        finally:
            if task_id in self.runner.running_tasks:
                del self.runner.running_tasks[task_id]
    
    # =============================================================================
    # Task Implementations
    # =============================================================================
    
    def _task_load_bag(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Load bag file task implementation with streaming progress"""
        bag_path = args['bag_path']
        build_index = args.get('build_index', False)
        
        with StreamingProgress(self.console, f"Loading {Path(bag_path).name}") as progress:
            try:
                progress.update(10, "Checking cache...")
                
                # Check if already cached
                cached_entry = self.cache_manager.get_analysis(Path(bag_path))
                if cached_entry and cached_entry.is_valid(Path(bag_path)):
                    progress.log("Found valid cache entry", 'info')
                    progress.update(100, "Using cached data")
                    
                    bag_info = cached_entry.bag_info
                else:
                    progress.update(30, "Loading bag file...")
                    progress.log("Cache miss, loading from file", 'info')
                    
                    # Load bag file with progress tracking
                    def load_progress_callback(phase: str, percent: float):
                        # Map load progress to 30-90% range
                        mapped_percent = 30 + (percent * 0.6)
                        progress.update(mapped_percent, f"Loading: {phase}")
                        progress.log(f"Load phase: {phase} ({percent:.1f}%)", 'info')
                    
                    # Use async loading
                    async def do_load():
                        return await self.parser.load_bag_async(
                            bag_path,
                            build_index=build_index,
                            progress_callback=load_progress_callback
                        )
                    
                    bag_info, elapsed_time = self._run_async(do_load())
                    progress.log(f"Loaded in {elapsed_time:.2f}s", 'success')
                
                progress.update(95, "Processing bag info...")
                
                # Store in session state
                if bag_info and bag_info.topics:
                    topics = [topic.name if hasattr(topic, 'name') else str(topic) for topic in bag_info.topics]
                    
                    bag_data = {
                        'topics': topics,
                        'file_size_mb': bag_info.file_size_mb or 0,
                        'duration_seconds': bag_info.duration_seconds or 0,
                        'total_messages': bag_info.total_messages or 0
                    }
                    
                    self.runner.state.loaded_bags[bag_path] = bag_data
                    
                    # Add to current bags if not already there
                    if bag_path not in self.runner.state.current_bags:
                        self.runner.state.current_bags.append(bag_path)
                    
                    progress.update(100, "Complete")
                    progress.log(f"Successfully processed {len(topics)} topics", 'success')
                    
                    return {
                        'success': True,
                        'bag_path': bag_path,
                        'topics_count': len(topics),
                        'file_size_mb': bag_data['file_size_mb'],
                        'duration_seconds': bag_data['duration_seconds']
                    }
                else:
                    progress.log("No topics found in bag file", 'warning')
                    return {'success': False, 'error': 'No topics found in bag file'}
                
            except Exception as e:
                progress.log(f"Load error: {str(e)}", 'error')
                return {'success': False, 'error': str(e)}
    
    def _task_extract_topics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Extract topics task implementation"""
        try:
            bags = args['bags']
            topics = args['topics']
            output_pattern = args['output_pattern']
            
            results = []
            
            for bag_path in bags:
                # Generate output path
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_str = output_pattern
                
                # Replace placeholders
                if '{input}' in output_str:
                    output_str = output_str.replace('{input}', Path(bag_path).stem)
                if '{timestamp}' in output_str:
                    output_str = output_str.replace('{timestamp}', timestamp)
                
                output_path = output_str
                
                # Create ExtractOption
                extract_option = ExtractOption(
                    topics=topics,
                    compression="none",
                    overwrite=True
                )
                
                try:
                    # Execute extraction
                    result_message, elapsed_time = self.parser.extract(
                        bag_path,
                        output_path,
                        extract_option
                    )
                    
                    results.append({
                        'bag_path': bag_path,
                        'output_path': output_path,
                        'success': True,
                        'elapsed_time': elapsed_time
                    })
                    
                except Exception as e:
                    results.append({
                        'bag_path': bag_path,
                        'output_path': output_path,
                        'success': False,
                        'error': str(e)
                    })
            
            success_count = sum(1 for r in results if r['success'])
            
            return {
                'success': success_count > 0,
                'results': results,
                'success_count': success_count,
                'total_count': len(results),
                'topics_count': len(topics)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _task_inspect_bag(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect bag task implementation"""
        try:
            bag_path = args['bag_path']
            verbose = args.get('verbose', False)
            
            # Get cached analysis
            cached_entry = self.cache_manager.get_analysis(Path(bag_path))
            if cached_entry and cached_entry.is_valid(Path(bag_path)):
                bag_info = cached_entry.bag_info
                
                # Generate inspection report
                report = {
                    'file_path': bag_path,
                    'file_size_mb': bag_info.file_size_mb or 0,
                    'duration_seconds': bag_info.duration_seconds or 0,
                    'topics_count': len(bag_info.topics) if bag_info.topics else 0,
                    'total_messages': bag_info.total_messages or 0,
                    'topics': [topic.name if hasattr(topic, 'name') else str(topic) for topic in bag_info.topics]
                }
                
                return {
                    'success': True,
                    'report': report
                }
            else:
                return {'success': False, 'error': 'Bag not loaded in cache'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _task_compress_bags(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Compress bags task implementation"""
        try:
            bags = args['bags']
            compression = args['compression']
            output_pattern = args['output_pattern']
            
            results = []
            
            for bag_path in bags:
                # Generate output path
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_str = output_pattern
                
                # Replace placeholders
                if '{input}' in output_str:
                    output_str = output_str.replace('{input}', Path(bag_path).stem)
                if '{timestamp}' in output_str:
                    output_str = output_str.replace('{timestamp}', timestamp)
                if '{compression}' in output_str:
                    output_str = output_str.replace('{compression}', compression)
                
                output_path = output_str
                
                try:
                    # Get all topics for compression (include everything)
                    if bag_path in self.runner.state.loaded_bags:
                        all_topics = self.runner.state.loaded_bags[bag_path]['topics']
                    else:
                        # Fallback: load bag info quickly
                        cached_entry = self.cache_manager.get_analysis(Path(bag_path))
                        if cached_entry:
                            all_topics = [topic.name if hasattr(topic, 'name') else str(topic) 
                                        for topic in cached_entry.bag_info.topics]
                        else:
                            all_topics = []
                    
                    if not all_topics:
                        raise ValueError("No topics found for compression")
                    
                    # Create ExtractOption for compression
                    extract_option = ExtractOption(
                        topics=all_topics,
                        compression=compression,
                        overwrite=True
                    )
                    
                    # Execute compression using extract
                    result_message, elapsed_time = self.parser.extract(
                        bag_path,
                        output_path,
                        extract_option
                    )
                    
                    results.append({
                        'bag_path': bag_path,
                        'output_path': output_path,
                        'success': True,
                        'elapsed_time': elapsed_time,
                        'compression': compression
                    })
                    
                except Exception as e:
                    results.append({
                        'bag_path': bag_path,
                        'output_path': output_path,
                        'success': False,
                        'error': str(e)
                    })
            
            success_count = sum(1 for r in results if r['success'])
            
            return {
                'success': success_count > 0,
                'results': results,
                'success_count': success_count,
                'total_count': len(results),
                'compression': compression
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _task_export_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Export data task implementation"""
        try:
            bags = args['bags']
            topics = args['topics']
            output_path = args['output_path']
            
            # For simplicity, export from first bag
            # In full implementation, you'd merge data from all bags
            if not bags:
                return {'success': False, 'error': 'No bags specified'}
            
            bag_path = bags[0]
            
            # Use existing data export functionality
            # This is a simplified implementation
            from ..data import DataProcessor
            
            processor = DataProcessor()
            
            # Load bag with DataFrames
            bag_info = processor.load_bag_sync(bag_path)
            
            # Get DataFrames for selected topics
            dataframes = processor.get_topic_dataframes(bag_info, topics)
            
            if not dataframes:
                return {'success': False, 'error': 'No DataFrames available for selected topics'}
            
            # Export based on number of topics
            if len(dataframes) == 1:
                # Single topic export
                df = list(dataframes.values())[0]
                success = processor.export_to_csv(df, output_path)
                
                return {
                    'success': success,
                    'output_path': output_path,
                    'topics_count': 1,
                    'row_count': len(df) if success else 0
                }
            else:
                # Multiple topics - merge and export
                merged_df = processor.merge_topic_dataframes(dataframes)
                success = processor.export_to_csv(merged_df, output_path)
                
                return {
                    'success': success,
                    'output_path': output_path,
                    'topics_count': len(topics),
                    'row_count': len(merged_df) if success else 0
                }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    pass
