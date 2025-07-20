"""
Unified Bag Manager - High-level interface for all bag operations
Provides a single entry point for CLI commands to interact with ROS bags
"""
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum
import logging

from .analyzer import BagAnalyzer, AnalysisResult, AnalysisType
from .cache import get_cache
from .result_handler import ResultHandler, OutputFormat, RenderOptions, ExportOptions


@dataclass
class InspectOptions:
    """Options for bag inspection"""
    topics: Optional[List[str]] = None
    topic_filter: Optional[str] = None
    show_fields: bool = False
    sort_by: str = "name"
    reverse_sort: bool = False
    limit: Optional[int] = None
    output_format: OutputFormat = OutputFormat.TABLE
    output_file: Optional[Path] = None
    verbose: bool = False


@dataclass
class FilterOptions:
    """Options for bag filtering"""
    topics: Optional[List[str]] = None
    topic_filter: Optional[str] = None
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    message_types: Optional[List[str]] = None
    output_path: Optional[Path] = None
    compression: Optional[str] = None
    dry_run: bool = False


@dataclass
class ProfileOptions:
    """Options for bag profiling"""
    topics: Optional[List[str]] = None
    time_window: float = 1.0
    show_statistics: bool = True
    show_timeline: bool = False
    output_format: OutputFormat = OutputFormat.TABLE
    output_file: Optional[Path] = None


@dataclass
class DiagnoseOptions:
    """Options for bag diagnosis"""
    check_integrity: bool = True
    check_timestamps: bool = True
    check_message_counts: bool = True
    check_duplicates: bool = False
    detailed: bool = False
    output_format: OutputFormat = OutputFormat.TABLE


class BagManager:
    """
    Unified high-level interface for all ROS bag operations
    
    This class provides a simple, consistent API for CLI commands to interact
    with ROS bags without needing to understand the underlying complexity.
    
    Example usage:
        manager = BagManager()
        result = await manager.inspect_bag("demo.bag", options)
        
        # Render results
        handler = manager.get_result_handler()
        handler.render(result, RenderOptions(format=OutputFormat.TABLE))
        
        # Export results
        handler.export(result, ExportOptions(format=OutputFormat.JSON, output_file=Path("report.json")))
    """
    
    def __init__(self, max_workers: int = 4):
        """Initialize the bag manager"""
        self.analyzer = BagAnalyzer(max_workers=max_workers)
        self.cache = get_cache()
        self.logger = logging.getLogger(__name__)
        self._result_handler = None
        
    def get_result_handler(self) -> ResultHandler:
        """Get the result handler instance for rendering and exporting"""
        if self._result_handler is None:
            self._result_handler = ResultHandler()
        return self._result_handler
        
    async def inspect_bag(
        self, 
        bag_path: Union[str, Path], 
        options: Optional[InspectOptions] = None
    ) -> Dict[str, Any]:
        """
        Inspect a ROS bag file and return analysis results
        
        Args:
            bag_path: Path to the bag file
            options: Inspection options
            
        Returns:
            Dictionary containing inspection results
        """
        if options is None:
            options = InspectOptions()
            
        bag_path = Path(bag_path)
        
        # Determine analysis type based on options
        analysis_type = AnalysisType.FULL_ANALYSIS if options.show_fields else AnalysisType.METADATA
        
        # Perform bag analysis
        result = await self.analyzer.analyze_bag_async(bag_path, analysis_type)
        
        # Apply topic filtering if specified
        filtered_topics = self._filter_topics(
            list(result.bag_info.topics), 
            options.topics, 
            options.topic_filter
        )
        
        # Prepare inspection results
        inspection_result = {
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'file_size': bag_path.stat().st_size if bag_path.exists() else 0,
                'topics_count': len(filtered_topics),
                'total_messages': sum(result.bag_info.message_counts.get(topic, 0) for topic in filtered_topics),
                'duration_seconds': result.bag_info.duration_seconds,
                'time_range': result.bag_info.time_range,
                'analysis_time': result.analysis_time,
                'cached': result.cached
            },
            'topics': [],
            'field_analysis': {},
            'cache_stats': self._get_cache_stats()
        }
        
        # Build topic information
        for topic in self._sort_topics(filtered_topics, options.sort_by, options.reverse_sort):
            if options.limit and len(inspection_result['topics']) >= options.limit:
                break
                
            message_type = result.bag_info.connections.get(topic, 'Unknown')
            message_count = result.bag_info.message_counts.get(topic, 0)
            frequency = message_count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            
            topic_info = {
                'name': topic,
                'message_type': message_type,
                'message_count': message_count,
                'frequency': frequency
            }
            
            # Add field analysis if requested
            if options.show_fields and result.message_types:
                field_paths = result.get_topic_field_paths(topic)
                if field_paths:
                    topic_info['field_paths'] = field_paths
                    inspection_result['field_analysis'][topic] = {
                        'message_type': message_type,
                        'field_paths': field_paths,
                        'samples_analyzed': len([t for t in filtered_topics if result.bag_info.connections.get(t) == message_type])
                    }
            
            inspection_result['topics'].append(topic_info)
        
        return inspection_result
    
    async def profile_bag(
        self,
        bag_path: Union[str, Path],
        options: Optional[ProfileOptions] = None
    ) -> Dict[str, Any]:
        """
        Profile a ROS bag file to analyze performance characteristics
        
        Args:
            bag_path: Path to the bag file
            options: Profiling options
            
        Returns:
            Dictionary containing profiling results
        """
        if options is None:
            options = ProfileOptions()
            
        # Analyze the bag for profiling
        result = await self.analyzer.analyze_bag_async(Path(bag_path), AnalysisType.METADATA)
        
        # Apply topic filtering
        topics_to_profile = self._filter_topics(
            list(result.bag_info.topics),
            options.topics,
            None
        )
        
        # Build profiling results
        profile_result = {
            'bag_info': {
                'file_name': Path(bag_path).name,
                'total_topics': len(topics_to_profile),
                'total_messages': sum(result.bag_info.message_counts.get(topic, 0) for topic in topics_to_profile),
                'duration_seconds': result.bag_info.duration_seconds,
                'average_rate': sum(result.bag_info.message_counts.values()) / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            },
            'topic_statistics': [],
            'performance_metrics': {
                'analysis_time': result.analysis_time,
                'cached': result.cached,
                'cache_hit_rate': self._get_cache_hit_rate()
            }
        }
        
        # Calculate topic statistics
        for topic in topics_to_profile:
            message_count = result.bag_info.message_counts.get(topic, 0)
            frequency = message_count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            
            topic_stats = {
                'topic': topic,
                'message_type': result.bag_info.connections.get(topic, 'Unknown'),
                'message_count': message_count,
                'frequency': frequency,
                'percentage': (message_count / sum(result.bag_info.message_counts.values())) * 100 if sum(result.bag_info.message_counts.values()) > 0 else 0
            }
            
            profile_result['topic_statistics'].append(topic_stats)
        
        return profile_result
    
    async def diagnose_bag(
        self,
        bag_path: Union[str, Path],
        options: Optional[DiagnoseOptions] = None
    ) -> Dict[str, Any]:
        """
        Diagnose a ROS bag file for potential issues
        
        Args:
            bag_path: Path to the bag file
            options: Diagnosis options
            
        Returns:
            Dictionary containing diagnosis results
        """
        if options is None:
            options = DiagnoseOptions()
            
        bag_path = Path(bag_path)
        
        # Perform bag analysis for diagnosis
        result = await self.analyzer.analyze_bag_async(bag_path, AnalysisType.METADATA)
        
        diagnosis_result = {
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'file_exists': bag_path.exists(),
                'file_size': bag_path.stat().st_size if bag_path.exists() else 0
            },
            'checks': [],
            'issues': [],
            'warnings': [],
            'summary': {
                'total_checks': 0,
                'passed_checks': 0,
                'failed_checks': 0,
                'warnings_count': 0
            }
        }
        
        # File integrity check
        if options.check_integrity:
            integrity_check = self._check_file_integrity(bag_path, result)
            diagnosis_result['checks'].append(integrity_check)
            if not integrity_check['passed']:
                diagnosis_result['issues'].append(integrity_check['message'])
        
        # Timestamp consistency check  
        if options.check_timestamps:
            timestamp_check = self._check_timestamps(result)
            diagnosis_result['checks'].append(timestamp_check)
            if not timestamp_check['passed']:
                diagnosis_result['issues'].append(timestamp_check['message'])
        
        # Message count validation
        if options.check_message_counts:
            count_check = self._check_message_counts(result)
            diagnosis_result['checks'].append(count_check)
            if not count_check['passed']:
                diagnosis_result['warnings'].append(count_check['message'])
        
        # Update summary
        diagnosis_result['summary']['total_checks'] = len(diagnosis_result['checks'])
        diagnosis_result['summary']['passed_checks'] = sum(1 for check in diagnosis_result['checks'] if check['passed'])
        diagnosis_result['summary']['failed_checks'] = sum(1 for check in diagnosis_result['checks'] if not check['passed'])
        diagnosis_result['summary']['warnings_count'] = len(diagnosis_result['warnings'])
        
        return diagnosis_result
    
    def _filter_topics(
        self, 
        all_topics: List[str], 
        selected_topics: Optional[List[str]], 
        topic_filter: Optional[str]
    ) -> List[str]:
        """Filter topics based on selection criteria with smart matching"""
        if selected_topics:
            # Smart matching: try exact match first, then fuzzy match
            filtered = []
            for pattern in selected_topics:
                # First try exact match
                exact_matches = [topic for topic in all_topics if topic == pattern]
                if exact_matches:
                    filtered.extend(exact_matches)
                else:
                    # If no exact match, try fuzzy matching (contains)
                    fuzzy_matches = [topic for topic in all_topics if pattern.lower() in topic.lower()]
                    filtered.extend(fuzzy_matches)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_filtered = []
            for topic in filtered:
                if topic not in seen:
                    seen.add(topic)
                    unique_filtered.append(topic)
            
            return unique_filtered
        elif topic_filter:
            # Use fuzzy matching
            return [topic for topic in all_topics if topic_filter.lower() in topic.lower()]
        else:
            # Return all topics
            return all_topics
    
    def _sort_topics(self, topics: List[str], sort_by: str, reverse: bool) -> List[str]:
        """Sort topics based on specified criteria"""
        if sort_by == "name":
            return sorted(topics, reverse=reverse)
        else:
            # Default to name sorting
            return sorted(topics, reverse=reverse)
    
    def _get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        try:
            stats = self.cache.get_stats() if hasattr(self.cache, 'get_stats') else {}
            return {
                'hit_rate': stats.get('hit_rate', 0.0),
                'total_requests': stats.get('total_requests', 0),
                'cache_hits': stats.get('cache_hits', 0),
                'cache_misses': stats.get('cache_misses', 0)
            }
        except Exception:
            return {'hit_rate': 0.0, 'total_requests': 0, 'cache_hits': 0, 'cache_misses': 0}
    
    def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate percentage"""
        stats = self._get_cache_stats()
        return stats['hit_rate']
    
    def _check_file_integrity(self, bag_path: Path, result: AnalysisResult) -> Dict[str, Any]:
        """Check bag file integrity"""
        check_result = {
            'name': 'File Integrity',
            'description': 'Verify bag file can be read and parsed correctly',
            'passed': True,
            'message': 'Bag file integrity is good'
        }
        
        if not bag_path.exists():
            check_result.update({
                'passed': False,
                'message': f'Bag file does not exist: {bag_path}'
            })
        elif len(result.errors) > 0:
            check_result.update({
                'passed': False,
                'message': f'Bag file has parsing errors: {", ".join(result.errors)}'
            })
        
        return check_result
    
    def _check_timestamps(self, result: AnalysisResult) -> Dict[str, Any]:
        """Check timestamp consistency"""
        check_result = {
            'name': 'Timestamp Consistency',
            'description': 'Verify timestamps are in chronological order',
            'passed': True,
            'message': 'Timestamps appear consistent'
        }
        
        if result.bag_info.time_range:
            start_time, end_time = result.bag_info.time_range
            if start_time >= end_time:
                check_result.update({
                    'passed': False,
                    'message': f'Invalid time range: start ({start_time}) >= end ({end_time})'
                })
        
        return check_result
    
    def _check_message_counts(self, result: AnalysisResult) -> Dict[str, Any]:
        """Check message count consistency"""
        check_result = {
            'name': 'Message Counts',
            'description': 'Verify message counts are reasonable',
            'passed': True,
            'message': 'Message counts appear normal'
        }
        
        total_messages = sum(result.bag_info.message_counts.values())
        if total_messages == 0:
            check_result.update({
                'passed': False,
                'message': 'Bag file contains no messages'
            })
        elif total_messages > 1000000:  # Arbitrary large number threshold
            check_result.update({
                'passed': True,  # Warning, not error
                'message': f'Large number of messages detected: {total_messages:,}'
            })
        
        return check_result
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self.analyzer, 'cleanup'):
            self.analyzer.cleanup() 