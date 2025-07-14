#!/usr/bin/env python3
"""
Benchmark test for comparing async vs sync bag analysis performance.
Tests performance differences across different bag sizes and analysis levels.
"""

import asyncio
import time
import psutil
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from statistics import mean, median, stdev
import json

# Import the modules we want to benchmark
from roseApp.core.async_analyzer import AsyncBagAnalyzer, CacheLevel, analyze_bag_async, get_async_analyzer
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import get_logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

logger = get_logger()


@dataclass
class BenchmarkResult:
    """Single benchmark test result"""
    test_name: str
    analysis_type: str  # 'async' or 'sync'
    file_size_mb: float
    topic_count: int
    message_count: int
    duration_seconds: float
    memory_peak_mb: float
    memory_avg_mb: float
    cache_hit: bool
    analysis_level: str
    error: Optional[str] = None


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results"""
    async_results: List[BenchmarkResult]
    sync_results: List[BenchmarkResult]
    performance_comparison: Dict[str, Any]
    recommendations: List[str]


class PerformanceMonitor:
    """Monitor system performance during tests"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.memory_samples = []
        self.monitoring = False
    
    def start_monitoring(self):
        """Start monitoring system resources"""
        self.monitoring = True
        self.memory_samples = []
        # Sample initial memory
        self.sample_memory()
        
    def stop_monitoring(self) -> Tuple[float, float]:
        """Stop monitoring and return peak and average memory usage in MB"""
        # Sample final memory
        self.sample_memory()
        self.monitoring = False
        
        if not self.memory_samples:
            return 0.0, 0.0
        
        peak_memory = max(self.memory_samples)
        avg_memory = mean(self.memory_samples)
        
        return peak_memory / 1024 / 1024, avg_memory / 1024 / 1024
    
    def sample_memory(self):
        """Sample current memory usage"""
        if self.monitoring:
            memory_info = self.process.memory_info()
            self.memory_samples.append(memory_info.rss)


class BagAnalysisBenchmark:
    """Main benchmark class for comparing async vs sync performance"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        # Use the global analyzer instance to match analyze_bag_async behavior
        self.async_analyzer = get_async_analyzer()
        self.performance_monitor = PerformanceMonitor()
        self.results: List[BenchmarkResult] = []
        
    async def run_comprehensive_benchmark(
        self,
        test_bags: List[str],
        analysis_levels: List[Tuple[str, int]] = None,
        iterations: int = 3
    ) -> BenchmarkSummary:
        """Run comprehensive benchmark comparing async vs sync performance"""
        
        if analysis_levels is None:
            analysis_levels = [
                ("metadata", CacheLevel.METADATA),
                ("statistics", CacheLevel.STATISTICS),
                ("messages", CacheLevel.MESSAGES),
                ("fields", CacheLevel.FIELDS)
            ]
        
        self.console.print(Panel.fit(
            "[bold cyan]ROS Bag Analysis Performance Benchmark[/bold cyan]\n"
            f"Testing {len(test_bags)} bag files with {len(analysis_levels)} analysis levels\n"
            f"Iterations per test: {iterations}",
            title="🚀 Benchmark Setup"
        ))
        
        # Clear any existing cache
        self.async_analyzer.clear_cache()
        
        total_tests = len(test_bags) * len(analysis_levels) * 2 * iterations  # 2 for async/sync
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            
            main_task = progress.add_task("Running benchmark tests...", total=total_tests)
            
            # Test each bag file
            for bag_path in test_bags:
                if not os.path.exists(bag_path):
                    self.console.print(f"[red]Warning: Bag file {bag_path} not found, skipping[/red]")
                    continue
                
                bag_size = os.path.getsize(bag_path) / 1024 / 1024  # MB
                
                # Test each analysis level
                for level_name, level_value in analysis_levels:
                    
                    # Run async tests
                    for i in range(iterations):
                        await self._run_async_test(
                            bag_path, bag_size, level_name, level_value, i+1, progress, main_task
                        )
                    
                    # Run sync tests
                    for i in range(iterations):
                        await self._run_sync_test(
                            bag_path, bag_size, level_name, level_value, i+1, progress, main_task
                        )
                    
                    # Clear cache between different analysis levels
                    self.async_analyzer.clear_cache()
        
        # Generate summary
        summary = self._generate_summary()
        return summary
    
    async def _run_async_test(
        self,
        bag_path: str,
        bag_size: float,
        level_name: str,
        level_value: int,
        iteration: int,
        progress: Progress,
        main_task: TaskID
    ):
        """Run single async analysis test"""
        
        test_name = f"async_{level_name}_{Path(bag_path).stem}_iter{iteration}"
        
        try:
            # Start performance monitoring
            self.performance_monitor.start_monitoring()
            start_time = time.time()
            
            # Check if this will be a cache hit with more detailed logic
            cache_key = self.async_analyzer._get_cache_key(bag_path)
            cache_exists_before = cache_key in self.async_analyzer._analysis_cache
            if cache_exists_before:
                cache_level_before = self.async_analyzer._analysis_cache[cache_key].cache_level
                cache_hit_expected = cache_level_before >= level_value
            else:
                cache_level_before = 0
                cache_hit_expected = False
            
            # Sample memory before analysis
            self.performance_monitor.sample_memory()
            
            # Run async analysis
            result = await analyze_bag_async(
                bag_path=bag_path,
                console=None,  # No console output during benchmark
                required_level=level_value,
                background_full_analysis=False  # Don't start background tasks during benchmark
            )
            
            # Sample memory after analysis
            self.performance_monitor.sample_memory()
            
            # Stop monitoring
            end_time = time.time()
            peak_memory, avg_memory = self.performance_monitor.stop_monitoring()
            
            # Determine if cache was actually used
            # If the analysis took less than 0.01 seconds AND cache was expected, it's a cache hit
            analysis_time = end_time - start_time
            cache_hit = cache_hit_expected and analysis_time < 0.01
            
            # Create benchmark result
            benchmark_result = BenchmarkResult(
                test_name=test_name,
                analysis_type="async",
                file_size_mb=bag_size,
                topic_count=len(result.metadata.topics),
                message_count=result.total_messages,
                duration_seconds=end_time - start_time,
                memory_peak_mb=peak_memory,
                memory_avg_mb=avg_memory,
                cache_hit=cache_hit,
                analysis_level=level_name
            )
            
            self.results.append(benchmark_result)
            
            progress.update(main_task, advance=1, 
                          description=f"✓ {test_name} - {benchmark_result.duration_seconds:.2f}s")
            
        except Exception as e:
            self.performance_monitor.stop_monitoring()
            
            benchmark_result = BenchmarkResult(
                test_name=test_name,
                analysis_type="async",
                file_size_mb=bag_size,
                topic_count=0,
                message_count=0,
                duration_seconds=0.0,
                memory_peak_mb=0.0,
                memory_avg_mb=0.0,
                cache_hit=False,
                analysis_level=level_name,
                error=str(e)
            )
            
            self.results.append(benchmark_result)
            progress.update(main_task, advance=1, 
                          description=f"✗ {test_name} - ERROR: {str(e)[:50]}")
    
    async def _run_sync_test(
        self,
        bag_path: str,
        bag_size: float,
        level_name: str,
        level_value: int,
        iteration: int,
        progress: Progress,
        main_task: TaskID
    ):
        """Run single sync analysis test"""
        
        test_name = f"sync_{level_name}_{Path(bag_path).stem}_iter{iteration}"
        
        try:
            # Start performance monitoring
            self.performance_monitor.start_monitoring()
            start_time = time.time()
            
            # Sample memory before analysis
            self.performance_monitor.sample_memory()
            
            # Run sync analysis
            result = await self._run_sync_analysis(bag_path, level_name)
            
            # Sample memory after analysis
            self.performance_monitor.sample_memory()
            
            # Stop monitoring
            end_time = time.time()
            peak_memory, avg_memory = self.performance_monitor.stop_monitoring()
            
            # Create benchmark result
            benchmark_result = BenchmarkResult(
                test_name=test_name,
                analysis_type="sync",
                file_size_mb=bag_size,
                topic_count=len(result.get('topics', [])),
                message_count=result.get('total_messages', 0),
                duration_seconds=end_time - start_time,
                memory_peak_mb=peak_memory,
                memory_avg_mb=avg_memory,
                cache_hit=False,  # Sync analysis doesn't use cache
                analysis_level=level_name
            )
            
            self.results.append(benchmark_result)
            
            progress.update(main_task, advance=1, 
                          description=f"✓ {test_name} - {benchmark_result.duration_seconds:.2f}s")
            
        except Exception as e:
            self.performance_monitor.stop_monitoring()
            
            benchmark_result = BenchmarkResult(
                test_name=test_name,
                analysis_type="sync",
                file_size_mb=bag_size,
                topic_count=0,
                message_count=0,
                duration_seconds=0.0,
                memory_peak_mb=0.0,
                memory_avg_mb=0.0,
                cache_hit=False,
                analysis_level=level_name,
                error=str(e)
            )
            
            self.results.append(benchmark_result)
            progress.update(main_task, advance=1, 
                          description=f"✗ {test_name} - ERROR: {str(e)[:50]}")
    
    async def _run_sync_analysis(self, bag_path: str, level_name: str) -> Dict:
        """Run synchronous analysis (legacy mode)"""
        
        def _sync_analysis():
            parser = create_parser(ParserType.ROSBAGS)
            
            # Load basic metadata
            topics, connections, time_range = parser.load_bag(bag_path)
            
            result = {
                'topics': topics,
                'connections': connections,
                'time_range': time_range,
                'total_messages': 0,
                'statistics': {}
            }
            
            # For higher levels, collect more detailed statistics
            if level_name in ['statistics', 'messages', 'fields']:
                try:
                    # Use different methods based on analysis level for optimal performance
                    if level_name == 'statistics':
                        # For statistics level, use lightweight message counts
                        topic_counts = parser.get_message_counts(bag_path)
                        statistics = {}
                        total_messages = 0
                        
                        for topic in topics:
                            if topic in topic_counts:
                                count = topic_counts[topic]
                                statistics[topic] = {
                                    'count': count,
                                    'size': 0,  # Size not available in lightweight mode
                                    'avg_size': 0
                                }
                                total_messages += count
                            else:
                                statistics[topic] = {'count': 0, 'size': 0, 'avg_size': 0}
                                
                    else:
                        # For messages and fields levels, use full statistics
                        topic_stats = parser.get_topic_stats(bag_path)
                        statistics = {}
                        total_messages = 0
                        
                        for topic in topics:
                            if topic in topic_stats:
                                stats = topic_stats[topic]
                                statistics[topic] = {
                                    'count': stats['count'],
                                    'size': stats['size'],
                                    'avg_size': stats['avg_size']
                                }
                                total_messages += stats['count']
                            else:
                                statistics[topic] = {'count': 0, 'size': 0, 'avg_size': 0}
                    
                    result['statistics'] = statistics
                    result['total_messages'] = total_messages
                    
                except Exception as e:
                    logger.warning(f"Failed to get topic statistics: {e}")
                    # Fallback to basic statistics
                    statistics = {}
                    for topic in topics:
                        statistics[topic] = {'count': 0, 'size': 0, 'avg_size': 0}
                    result['statistics'] = statistics
                    result['total_messages'] = 0
            
            return result
        
        # Run sync analysis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_analysis)
    
    def _generate_summary(self) -> BenchmarkSummary:
        """Generate benchmark summary with performance comparison"""
        
        async_results = [r for r in self.results if r.analysis_type == "async" and r.error is None]
        sync_results = [r for r in self.results if r.analysis_type == "sync" and r.error is None]
        
        # Calculate performance metrics
        performance_comparison = {}
        
        # Group by analysis level
        for level in ["metadata", "statistics", "messages", "fields"]:
            async_level = [r for r in async_results if r.analysis_level == level]
            sync_level = [r for r in sync_results if r.analysis_level == level]
            
            if async_level and sync_level:
                async_times = [r.duration_seconds for r in async_level]
                sync_times = [r.duration_seconds for r in sync_level]
                
                async_memory = [r.memory_peak_mb for r in async_level]
                sync_memory = [r.memory_peak_mb for r in sync_level]
                
                performance_comparison[level] = {
                    'async_avg_time': mean(async_times),
                    'sync_avg_time': mean(sync_times),
                    'time_improvement': (mean(sync_times) - mean(async_times)) / mean(sync_times) * 100,
                    'async_avg_memory': mean(async_memory),
                    'sync_avg_memory': mean(sync_memory),
                    'cache_hit_rate': sum(1 for r in async_level if r.cache_hit) / len(async_level) * 100
                }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(performance_comparison)
        
        return BenchmarkSummary(
            async_results=async_results,
            sync_results=sync_results,
            performance_comparison=performance_comparison,
            recommendations=recommendations
        )
    
    def _generate_recommendations(self, comparison: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations based on benchmark results"""
        
        recommendations = []
        
        for level, metrics in comparison.items():
            time_improvement = metrics.get('time_improvement', 0)
            cache_hit_rate = metrics.get('cache_hit_rate', 0)
            
            if time_improvement > 20:
                recommendations.append(
                    f"✓ Async analysis shows {time_improvement:.1f}% performance improvement for {level} level"
                )
            elif time_improvement < -10:
                recommendations.append(
                    f"⚠ Sync analysis may be faster for {level} level in some cases"
                )
            
            if cache_hit_rate > 50:
                recommendations.append(
                    f"✓ High cache hit rate ({cache_hit_rate:.1f}%) for {level} level - async caching is effective"
                )
        
        # General recommendations
        recommendations.append("💡 Use async analysis for repeated analysis of the same bags")
        recommendations.append("💡 Use sync analysis for one-time analysis of small bags")
        recommendations.append("💡 Async analysis benefits increase with file size and complexity")
        
        return recommendations
    
    def display_results(self, summary: BenchmarkSummary):
        """Display benchmark results in a formatted table"""
        
        self.console.print("\n" + "="*80)
        self.console.print(Panel.fit(
            "[bold green]Benchmark Results Summary[/bold green]",
            title="📊 Performance Analysis"
        ))
        
        # Performance comparison table
        table = Table(title="Performance Comparison by Analysis Level")
        table.add_column("Level", style="cyan")
        table.add_column("Async Avg Time", style="green")
        table.add_column("Sync Avg Time", style="yellow")
        table.add_column("Time Improvement", style="bold")
        table.add_column("Cache Hit Rate", style="blue")
        table.add_column("Memory Usage", style="magenta")
        
        for level, metrics in summary.performance_comparison.items():
            improvement = metrics['time_improvement']
            improvement_color = "green" if improvement > 0 else "red"
            
            table.add_row(
                level.title(),
                f"{metrics['async_avg_time']:.3f}s",
                f"{metrics['sync_avg_time']:.3f}s",
                f"[{improvement_color}]{improvement:+.1f}%[/{improvement_color}]",
                f"{metrics['cache_hit_rate']:.1f}%",
                f"A:{metrics['async_avg_memory']:.1f}MB S:{metrics['sync_avg_memory']:.1f}MB"
            )
        
        self.console.print(table)
        
        # Recommendations
        self.console.print("\n")
        self.console.print(Panel.fit(
            "\n".join(summary.recommendations),
            title="🎯 Performance Recommendations",
            border_style="blue"
        ))
        
        # Detailed results
        if summary.async_results or summary.sync_results:
            self.console.print("\n[dim]Detailed Results:[/dim]")
            
            detail_table = Table(title="Detailed Benchmark Results")
            detail_table.add_column("Test", style="cyan")
            detail_table.add_column("Type", style="bold")
            detail_table.add_column("Level", style="green")
            detail_table.add_column("Duration", style="yellow")
            detail_table.add_column("Memory", style="magenta")
            detail_table.add_column("Cache Hit", style="blue")
            detail_table.add_column("File Size", style="dim")
            
            all_results = summary.async_results + summary.sync_results
            all_results.sort(key=lambda x: (x.analysis_level, x.analysis_type))
            
            for result in all_results:
                cache_indicator = "✓" if result.cache_hit else "✗"
                detail_table.add_row(
                    result.test_name[:30],
                    result.analysis_type.upper(),
                    result.analysis_level,
                    f"{result.duration_seconds:.3f}s",
                    f"{result.memory_peak_mb:.1f}MB",
                    cache_indicator,
                    f"{result.file_size_mb:.1f}MB"
                )
            
            self.console.print(detail_table)
    
    def save_results(self, summary: BenchmarkSummary, output_path: str):
        """Save benchmark results to JSON file"""
        
        results_data = {
            'benchmark_summary': {
                'total_tests': len(self.results),
                'successful_tests': len(summary.async_results) + len(summary.sync_results),
                'failed_tests': len([r for r in self.results if r.error is not None]),
                'timestamp': time.time()
            },
            'performance_comparison': summary.performance_comparison,
            'recommendations': summary.recommendations,
            'detailed_results': [
                {
                    'test_name': r.test_name,
                    'analysis_type': r.analysis_type,
                    'analysis_level': r.analysis_level,
                    'duration_seconds': r.duration_seconds,
                    'memory_peak_mb': r.memory_peak_mb,
                    'cache_hit': r.cache_hit,
                    'file_size_mb': r.file_size_mb,
                    'topic_count': r.topic_count,
                    'message_count': r.message_count,
                    'error': r.error
                }
                for r in self.results
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        self.console.print(f"[green]Results saved to: {output_path}[/green]")


# Demo function to run benchmark with sample data
async def run_benchmark_demo():
    """Run benchmark demo with sample bag files"""
    
    console = Console()
    
    # Create sample test bags list (you would replace these with actual bag files)
    test_bags = [
        # Add paths to actual bag files here
        # "/path/to/small_bag.bag",
        # "/path/to/medium_bag.bag", 
        # "/path/to/large_bag.bag"
    ]
    
    # If no test bags are provided, create mock test
    if not test_bags:
        console.print("[yellow]No test bag files provided. Please add actual bag file paths to test_bags list.[/yellow]")
        console.print("[dim]Example usage:[/dim]")
        console.print("test_bags = ['/path/to/your/bag1.bag', '/path/to/your/bag2.bag']")
        return
    
    # Create benchmark instance
    benchmark = BagAnalysisBenchmark(console=console)
    
    # Run comprehensive benchmark
    summary = await benchmark.run_comprehensive_benchmark(
        test_bags=test_bags,
        iterations=3
    )
    
    # Display results
    benchmark.display_results(summary)
    
    # Save results
    output_path = "benchmark_results.json"
    benchmark.save_results(summary, output_path)


if __name__ == "__main__":
    # Run the benchmark demo
    asyncio.run(run_benchmark_demo()) 