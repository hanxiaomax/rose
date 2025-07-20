#!/usr/bin/env python3
"""
Profile command for ROS bag performance analysis and benchmarking.
"""

import asyncio
import os
import sys
import time
import psutil
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from statistics import mean, median, stdev

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from ..core.analyzer import analyze_bag_async, AnalysisType
from ..core.parser import create_parser, ParserType
from ..core.util import set_app_mode, AppMode, get_logger, log_cli_error
from .error_handling import ValidationError, validate_file_exists

app = typer.Typer(name="profile", help="Performance analysis and benchmarking tools")
logger = get_logger("RoseProfile")


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
        self.sample_memory()
        
    def stop_monitoring(self) -> Tuple[float, float]:
        """Stop monitoring and return peak and average memory usage in MB"""
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
        
        total_tests = len(test_bags) * len(analysis_levels) * 2 * iterations
        
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
            
            # Check if this will be a cache hit
            cache_key = self.async_analyzer._get_cache_key(bag_path)
            cache_exists_before = cache_key in self.async_analyzer._analysis_cache
            if cache_exists_before:
                cache_level_before = self.async_analyzer._analysis_cache[cache_key].cache_level
                cache_hit_expected = cache_level_before >= level_value
            else:
                cache_hit_expected = False
            
            # Run async analysis
            result = await analyze_bag_async(
                bag_path=bag_path,
                console=None,
                required_level=level_value,
                background_full_analysis=False
            )
            
            # Stop monitoring
            end_time = time.time()
            peak_memory, avg_memory = self.performance_monitor.stop_monitoring()
            
            # Determine if cache was actually used
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
            
            # Run sync analysis
            result = await self._run_sync_analysis(bag_path, level_name)
            
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
                                    'size': 0,
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
            title="�� Performance Recommendations",
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


@app.command(name="run-benchmark")
def run_benchmark(
    bags: List[str] = typer.Option(
        [],
        "--bags",
        "-b",
        help="Path(s) to bag files for testing. If not specified, will prompt for files."
    ),
    iterations: int = typer.Option(
        2,
        "--iterations",
        "-i",
        help="Number of iterations per test (default: 2, max: 10)"
    ),
    output: str = typer.Option(
        "benchmark_results.json",
        "--output",
        "-o",
        help="Output file path for results (default: benchmark_results.json)"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Quiet mode - minimal output"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Force interactive mode even if bags are specified"
    )
):
    """
    Run performance benchmark comparing async vs sync ROS bag analysis.
    
    This command measures the performance differences between async and sync 
    bag analysis across multiple levels (metadata, statistics, messages, fields).
    It provides detailed metrics including timing, memory usage, and cache hit rates.
    
    Examples:
        rose profile run-benchmark                                    # Interactive mode
        rose profile run-benchmark --bags tests/demo.bag             # Single bag
        rose profile run-benchmark --bags file1.bag file2.bag        # Multiple bags
        rose profile run-benchmark --bags tests/demo.bag --iterations 3 --output my_results.json
    """
    
    # Set application mode
    set_app_mode(AppMode.CLI)
    
    # Validate iterations
    if not (1 <= iterations <= 10):
        logger.error(f"Invalid iterations: {iterations}. Must be between 1 and 10.")
        raise typer.Exit(code=1)
    
    # Run async benchmark
    try:
        asyncio.run(_run_benchmark_async(bags, iterations, output, quiet, interactive))
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
        raise typer.Exit(code=130)
    except Exception as e:
        log_cli_error(f"Benchmark failed: {e}")
        raise typer.Exit(code=1)


async def _run_benchmark_async(
    bags: List[str], 
    iterations: int, 
    output: str, 
    quiet: bool, 
    interactive: bool
):
    """Internal async function to run the benchmark"""
    
    console = Console(quiet=quiet)
    
    if not quiet:
        console.print(Panel.fit(
            "[bold cyan]ROS Bag Analysis Performance Benchmark[/bold cyan]\n\n"
            "This tool compares the performance of async vs sync bag analysis.\n"
            "It will test real bag files and provide accurate performance metrics.\n\n"
            "[yellow]Features:[/yellow]\n"
            "• Multi-level analysis (metadata, statistics, messages, fields)\n"
            "• Memory usage monitoring\n"
            "• Cache hit rate measurement\n"
            "• Performance improvement calculations\n"
            "• JSON results export",
            title="Performance Benchmark"
        ))
    
    # Get bag files
    test_bags = []
    
    if bags and not interactive:
        # Command line mode
        for bag_path in bags:
            try:
                validate_file_exists(bag_path)
                test_bags.append(bag_path)
                if not quiet:
                    size_mb = os.path.getsize(bag_path) / (1024 * 1024)
                    console.print(f"[green]OK Added: {bag_path} ({size_mb:.1f} MB)[/green]")
            except ValidationError as e:
                console.print(f"[red]ERROR {e}[/red]")
        
        if not test_bags:
            console.print("[red]ERROR No valid bag files found. Exiting.[/red]")
            raise typer.Exit(code=1)
    else:
        # Interactive mode
        test_bags = _get_test_bags_interactive(console)
        
        if not test_bags:
            console.print("[red]ERROR No valid bag files provided. Exiting.[/red]")
            raise typer.Exit(code=1)
    
    if not quiet:
        console.print(f"[green]OK Found {len(test_bags)} bag files to test[/green]")
        for i, bag in enumerate(test_bags, 1):
            size_mb = os.path.getsize(bag) / (1024 * 1024)
            console.print(f"  {i}. {bag} ({size_mb:.1f} MB)")
        
        console.print(f"\n[cyan]Starting benchmark with {iterations} iterations per test...[/cyan]")
    
    # Create benchmark instance
    benchmark = BagAnalysisBenchmark(console=console)
    
    # Run comprehensive benchmark
    try:
        summary = await benchmark.run_comprehensive_benchmark(
            test_bags=test_bags,
            iterations=iterations
        )
        
        # Display results
        if not quiet:
            benchmark.display_results(summary)
        
        # Save results
        benchmark.save_results(summary, output)
        
        if not quiet:
            console.print(f"\n[green]OK Benchmark completed successfully![/green]")
            console.print(f"Results saved to: {output}")
        else:
            console.print(f"Benchmark completed. Results saved to: {output}")
            
    except Exception as e:
        console.print(f"[red]ERROR Benchmark failed: {e}[/red]")
        if not quiet:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise


def _get_test_bags_interactive(console: Console) -> List[str]:
    """Get bag files from user input in interactive mode"""
    
    test_bags = []
    
    # Check for common bag file locations
    common_paths = [
        "tests/demo.bag",
        "tests/test_data/demo.bag",
        "test_data/demo.bag",
        "demo.bag"
    ]
    
    console.print("\n[yellow]Checking for common bag files...[/yellow]")
    found_bags = []
    for path in common_paths:
        if os.path.exists(path):
            found_bags.append(path)
            console.print(f"  [green]OK Found: {path}[/green]")
    
    if found_bags:
        console.print(f"\n[cyan]Found {len(found_bags)} bag files. Do you want to use them?[/cyan]")
        for i, bag in enumerate(found_bags, 1):
            size_mb = os.path.getsize(bag) / (1024 * 1024)
            console.print(f"  {i}. {bag} ({size_mb:.1f} MB)")
        
        try:
            use_found = typer.prompt(
                "\nUse these bag files? (y/n)",
                default="y"
            ).lower().strip()
            
            if use_found in ["y", "yes"]:
                test_bags.extend(found_bags)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Interrupted by user[/yellow]")
            return []
    
    # Allow user to add more bags
    console.print("\n[yellow]You can add more bag files (press Enter when done):[/yellow]")
    while True:
        try:
            bag_path = typer.prompt("Enter bag file path (or press Enter to finish)", default="")
            if not bag_path:
                break
            
            if os.path.exists(bag_path):
                if bag_path not in test_bags:
                    test_bags.append(bag_path)
                    size_mb = os.path.getsize(bag_path) / (1024 * 1024)
                    console.print(f"  [green]OK Added: {bag_path} ({size_mb:.1f} MB)[/green]")
                else:
                    console.print(f"  [yellow]Already added: {bag_path}[/yellow]")
            else:
                console.print(f"  [red]ERROR File not found: {bag_path}[/red]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Interrupted by user[/yellow]")
            break
    
    return test_bags


def main():
    """Main entry point for profile command"""
    app()


if __name__ == "__main__":
    main()
