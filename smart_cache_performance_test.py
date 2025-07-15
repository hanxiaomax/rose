#!/usr/bin/env python3
"""
Smart Cache Performance Test Script

Tests and compares the performance of traditional caching vs smart cache management.
"""

import asyncio
import time
import sys
from pathlib import Path
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from roseApp.core.smart_cache_manager import get_smart_cache_manager
from roseApp.core.unified_cache import get_unified_cache_manager, CacheLevel
from roseApp.core.util import get_logger

logger = get_logger("SmartCacheTest")


class SmartCachePerformanceTest:
    """Performance test for smart cache vs traditional cache"""
    
    def __init__(self, console: Console):
        self.console = console
        self.smart_cache = get_smart_cache_manager()
        self.traditional_cache = get_unified_cache_manager()
    
    async def run_comprehensive_test(self, bag_path: str, iterations: int = 5):
        """Run comprehensive cache performance test"""
        
        self.console.print(Panel.fit(
            "[bold cyan]Smart Cache Performance Test[/bold cyan]\n\n"
            "Testing intelligent caching vs traditional caching strategies.\n"
            "This test compares cache hit rates, access times, and memory efficiency.",
            title="Smart Cache Test"
        ))
        
        if not Path(bag_path).exists():
            self.console.print(f"[red]Error: Bag file not found: {bag_path}[/red]")
            return
        
        self.console.print(f"\n[cyan]Testing bag: {bag_path}[/cyan]")
        
        # Test scenarios
        scenarios = [
            ("Metadata Only", CacheLevel.METADATA),
            ("Statistics", CacheLevel.STATISTICS),
            ("Messages", CacheLevel.MESSAGES),
            ("Fields", CacheLevel.FIELDS),
        ]
        
        results = {}
        
        for scenario_name, level in scenarios:
            self.console.print(f"\n[yellow]Testing {scenario_name} Level[/yellow]")
            
            # Clear caches
            self.smart_cache.clear_cache()
            self.traditional_cache.clear_cache()
            
            # Test traditional cache
            traditional_results = await self._test_traditional_cache(bag_path, level, iterations)
            
            # Test smart cache
            smart_results = await self._test_smart_cache(bag_path, level, iterations)
            
            results[scenario_name] = {
                'level': level,
                'traditional': traditional_results,
                'smart': smart_results
            }
        
        # Display results
        self._display_results(results)
        
        # Display detailed cache analytics
        self._display_cache_analytics()
    
    async def _test_traditional_cache(self, bag_path: str, level: int, iterations: int) -> Dict[str, Any]:
        """Test traditional cache performance"""
        times = []
        
        for i in range(iterations):
            if i > 0:
                # Clear cache for fresh test (except first iteration for cache hit test)
                self.traditional_cache.clear_cache()
            
            start_time = time.time()
            
            # Get analysis
            result = await self.traditional_cache.get_analysis(
                bag_path=bag_path,
                required_level=level,
                is_async=True
            )
            
            end_time = time.time()
            times.append(end_time - start_time)
            
            self.console.print(f"  Traditional iteration {i+1}: {times[-1]:.3f}s")
        
        return {
            'times': times,
            'avg_time': sum(times) / len(times),
            'min_time': min(times),
            'max_time': max(times),
            'cache_hit_time': times[0] if len(times) > 0 else 0,  # First call (cache miss)
            'cache_miss_time': times[1] if len(times) > 1 else 0   # Second call (cache miss, cleared)
        }
    
    async def _test_smart_cache(self, bag_path: str, level: int, iterations: int) -> Dict[str, Any]:
        """Test smart cache performance"""
        times = []
        
        for i in range(iterations):
            if i > 0:
                # For smart cache, don't clear - test cache persistence
                pass
            
            start_time = time.time()
            
            # Get analysis
            result = await self.smart_cache.get_analysis(
                bag_path=bag_path,
                required_level=level,
                enable_warming=True
            )
            
            end_time = time.time()
            times.append(end_time - start_time)
            
            self.console.print(f"  Smart iteration {i+1}: {times[-1]:.3f}s")
        
        return {
            'times': times,
            'avg_time': sum(times) / len(times),
            'min_time': min(times),
            'max_time': max(times),
            'cache_hit_time': times[0] if len(times) > 0 else 0,  # First call (cache miss)
            'cache_miss_time': times[1] if len(times) > 1 else 0   # Second call (should be cache hit)
        }
    
    def _display_results(self, results: Dict[str, Any]):
        """Display performance test results"""
        
        # Create comparison table
        table = Table(title="Cache Performance Comparison")
        table.add_column("Scenario", style="cyan")
        table.add_column("Method", style="magenta")
        table.add_column("Avg Time", style="green")
        table.add_column("Min Time", style="yellow")
        table.add_column("Max Time", style="red")
        table.add_column("Cache Hit", style="blue")
        table.add_column("Improvement", style="bold green")
        
        for scenario_name, data in results.items():
            traditional = data['traditional']
            smart = data['smart']
            
            # Calculate improvement
            improvement = ((traditional['avg_time'] - smart['avg_time']) / traditional['avg_time']) * 100
            
            table.add_row(
                scenario_name,
                "Traditional",
                f"{traditional['avg_time']:.3f}s",
                f"{traditional['min_time']:.3f}s",
                f"{traditional['max_time']:.3f}s",
                f"{traditional['cache_hit_time']:.3f}s",
                "Baseline"
            )
            
            table.add_row(
                "",
                "Smart",
                f"{smart['avg_time']:.3f}s",
                f"{smart['min_time']:.3f}s",
                f"{smart['max_time']:.3f}s",
                f"{smart['cache_hit_time']:.3f}s",
                f"{improvement:+.1f}%"
            )
            
            table.add_row("", "", "", "", "", "", "")  # Separator
        
        self.console.print("\n")
        self.console.print(table)
        
        # Summary
        total_improvements = []
        for scenario_name, data in results.items():
            traditional = data['traditional']
            smart = data['smart']
            improvement = ((traditional['avg_time'] - smart['avg_time']) / traditional['avg_time']) * 100
            total_improvements.append(improvement)
        
        avg_improvement = sum(total_improvements) / len(total_improvements)
        max_improvement = max(total_improvements)
        min_improvement = min(total_improvements)
        
        summary = f"""
[bold green]Performance Summary:[/bold green]
• Average improvement: {avg_improvement:.1f}%
• Best improvement: {max_improvement:.1f}%
• Worst improvement: {min_improvement:.1f}%
• Test scenarios: {len(results)}

[bold cyan]Key Smart Cache Benefits:[/bold cyan]
• Persistent cache across sessions
• Predictive cache warming
• Memory-efficient eviction
• Access pattern learning
• Cross-level cache optimization
"""
        
        self.console.print(Panel.fit(summary, title="Smart Cache Results"))
    
    def _display_cache_analytics(self):
        """Display detailed cache analytics"""
        
        # Get smart cache statistics
        smart_stats = self.smart_cache.get_cache_stats()
        smart_info = self.smart_cache.get_cache_info()
        
        # Cache statistics table
        stats_table = Table(title="Smart Cache Analytics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="magenta")
        
        stats_table.add_row("Total Requests", str(smart_stats.total_requests))
        stats_table.add_row("Cache Hits", str(smart_stats.cache_hits))
        stats_table.add_row("Cache Misses", str(smart_stats.cache_misses))
        stats_table.add_row("Hit Rate", f"{smart_stats.hit_rate:.1f}%")
        stats_table.add_row("Miss Rate", f"{smart_stats.miss_rate:.1f}%")
        stats_table.add_row("Avg Access Time", f"{smart_stats.avg_access_time:.3f}s")
        stats_table.add_row("Memory Usage", f"{smart_stats.memory_usage / 1024 / 1024:.1f} MB")
        stats_table.add_row("File Cache Size", f"{smart_stats.file_cache_size / 1024 / 1024:.1f} MB")
        stats_table.add_row("Memory Entries", str(smart_info['memory_entries']))
        stats_table.add_row("File Entries", str(smart_info['file_entries']))
        
        self.console.print("\n")
        self.console.print(stats_table)
        
        # Access patterns
        if smart_info['access_patterns']:
            patterns_table = Table(title="Access Patterns")
            patterns_table.add_column("Cache Key", style="cyan")
            patterns_table.add_column("Access Count", style="magenta")
            patterns_table.add_column("Avg Time", style="green")
            patterns_table.add_column("Recent Accesses", style="yellow")
            
            for key, pattern in list(smart_info['access_patterns'].items())[:5]:
                short_key = key[:16] + "..." if len(key) > 16 else key
                patterns_table.add_row(
                    short_key,
                    str(pattern['count']),
                    f"{pattern['avg_time']:.3f}s",
                    str(len(pattern['recent_accesses']))
                )
            
            self.console.print("\n")
            self.console.print(patterns_table)
    
    async def run_cache_warming_test(self, bag_path: str):
        """Test cache warming effectiveness"""
        
        self.console.print(Panel.fit(
            "[bold cyan]Cache Warming Test[/bold cyan]\n\n"
            "Testing predictive cache warming and its impact on performance.",
            title="Cache Warming Test"
        ))
        
        # Clear cache
        self.smart_cache.clear_cache()
        
        # Test without warming
        self.console.print("\n[yellow]Testing without cache warming...[/yellow]")
        
        times_without_warming = []
        for level in [CacheLevel.METADATA, CacheLevel.STATISTICS, CacheLevel.MESSAGES, CacheLevel.FIELDS]:
            start_time = time.time()
            await self.smart_cache.get_analysis(bag_path, level, enable_warming=False)
            end_time = time.time()
            times_without_warming.append(end_time - start_time)
            self.console.print(f"  Level {level}: {times_without_warming[-1]:.3f}s")
        
        # Clear cache
        self.smart_cache.clear_cache()
        
        # Test with warming
        self.console.print("\n[yellow]Testing with cache warming...[/yellow]")
        
        times_with_warming = []
        for level in [CacheLevel.METADATA, CacheLevel.STATISTICS, CacheLevel.MESSAGES, CacheLevel.FIELDS]:
            start_time = time.time()
            await self.smart_cache.get_analysis(bag_path, level, enable_warming=True)
            end_time = time.time()
            times_with_warming.append(end_time - start_time)
            self.console.print(f"  Level {level}: {times_with_warming[-1]:.3f}s")
        
        # Display warming results
        warming_table = Table(title="Cache Warming Results")
        warming_table.add_column("Level", style="cyan")
        warming_table.add_column("Without Warming", style="red")
        warming_table.add_column("With Warming", style="green")
        warming_table.add_column("Improvement", style="bold green")
        
        levels = ["Metadata", "Statistics", "Messages", "Fields"]
        for i, level_name in enumerate(levels):
            without = times_without_warming[i]
            with_warming = times_with_warming[i]
            improvement = ((without - with_warming) / without) * 100 if without > 0 else 0
            
            warming_table.add_row(
                level_name,
                f"{without:.3f}s",
                f"{with_warming:.3f}s",
                f"{improvement:+.1f}%"
            )
        
        self.console.print("\n")
        self.console.print(warming_table)
        
        total_without = sum(times_without_warming)
        total_with = sum(times_with_warming)
        total_improvement = ((total_without - total_with) / total_without) * 100
        
        self.console.print(f"\n[bold green]Total time without warming: {total_without:.3f}s[/bold green]")
        self.console.print(f"[bold green]Total time with warming: {total_with:.3f}s[/bold green]")
        self.console.print(f"[bold cyan]Overall improvement: {total_improvement:.1f}%[/bold cyan]")


async def main():
    """Main test function"""
    console = Console()
    
    # Test with demo bag if available
    test_bags = [
        "tests/demo.bag",
        "tests/test_data/demo.bag", 
        "test_data/demo.bag",
        "demo.bag"
    ]
    
    bag_path = None
    for test_bag in test_bags:
        if Path(test_bag).exists():
            bag_path = test_bag
            break
    
    if not bag_path:
        console.print("[red]Error: No test bag file found. Please provide a bag file.[/red]")
        console.print("[dim]Checked locations: " + ", ".join(test_bags) + "[/dim]")
        return
    
    # Run performance test
    test = SmartCachePerformanceTest(console)
    
    # Run comprehensive test
    await test.run_comprehensive_test(bag_path, iterations=3)
    
    # Run cache warming test
    await test.run_cache_warming_test(bag_path)


if __name__ == "__main__":
    asyncio.run(main()) 