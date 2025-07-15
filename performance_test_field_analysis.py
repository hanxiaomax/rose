#!/usr/bin/env python3
"""
Performance Test Script for Field Analysis Optimization
Tests and compares the performance of optimized vs legacy field analysis methods.
"""

import time
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from roseApp.core.unified_analyzer import get_unified_analyzer
from roseApp.core.message_type_analyzer import get_message_type_analyzer
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.unified_cache import CacheLevel
from roseApp.core.util import get_logger

logger = get_logger("PerformanceTest")


class FieldAnalysisPerformanceTest:
    """Performance test for field analysis optimization"""
    
    def __init__(self, console: Console):
        self.console = console
        self.analyzer = get_unified_analyzer()
        self.type_analyzer = get_message_type_analyzer()
        self.parser = create_parser(ParserType.ROSBAGS)
        
    def run_comprehensive_test(self, bag_path: str, iterations: int = 5):
        """Run comprehensive performance test"""
        
        self.console.print(Panel.fit(
            "[bold cyan]Field Analysis Performance Test[/bold cyan]\n\n"
            "Testing optimized message type analysis vs legacy sample-based analysis.\n"
            "This test compares static type definition analysis with message deserialization.",
            title="Performance Test"
        ))
        
        if not Path(bag_path).exists():
            self.console.print(f"[red]Error: Bag file not found: {bag_path}[/red]")
            return
        
        # Get bag metadata first
        topics, connections, time_range = self.parser.load_bag(bag_path)
        
        self.console.print(f"\n[cyan]Testing bag: {bag_path}[/cyan]")
        self.console.print(f"[dim]Topics: {len(topics)}, Connections: {len(connections)}[/dim]")
        
        # Test 1: Legacy sample-based analysis
        self.console.print("\n[yellow]Test 1: Legacy Sample-Based Field Analysis[/yellow]")
        legacy_times = []
        for i in range(iterations):
            start_time = time.time()
            legacy_results = self._run_legacy_analysis(bag_path, topics, connections)
            end_time = time.time()
            
            duration = end_time - start_time
            legacy_times.append(duration)
            self.console.print(f"  Iteration {i+1}: {duration:.3f}s")
        
        # Test 2: Optimized type system analysis
        self.console.print("\n[yellow]Test 2: Optimized Type System Field Analysis[/yellow]")
        optimized_times = []
        for i in range(iterations):
            start_time = time.time()
            optimized_results = self._run_optimized_analysis(bag_path, topics, connections)
            end_time = time.time()
            
            duration = end_time - start_time
            optimized_times.append(duration)
            self.console.print(f"  Iteration {i+1}: {duration:.3f}s")
        
        # Test 3: Cache performance test
        self.console.print("\n[yellow]Test 3: Cache Performance Test[/yellow]")
        cache_times = []
        for i in range(iterations):
            start_time = time.time()
            cache_results = self._run_cache_test(bag_path, topics, connections)
            end_time = time.time()
            
            duration = end_time - start_time
            cache_times.append(duration)
            self.console.print(f"  Iteration {i+1}: {duration:.3f}s")
        
        # Display results
        self._display_results(legacy_times, optimized_times, cache_times, len(topics))
        
        # Display type analyzer stats
        self._display_analyzer_stats()
        
    def _run_legacy_analysis(self, bag_path: str, topics: List[str], connections: Dict[str, str]) -> Dict[str, Any]:
        """Run legacy sample-based field analysis"""
        results = {}
        
        for topic in topics:
            if topic not in connections:
                continue
                
            msg_type = connections[topic]
            
            # Legacy method: read message samples and analyze
            messages = []
            message_count = 0
            max_samples = 5
            
            try:
                for timestamp, msg_data in self.parser.read_messages(bag_path, [topic]):
                    if message_count >= max_samples:
                        break
                    messages.append(msg_data)
                    message_count += 1
                
                if messages:
                    # Analyze the structure of the first message
                    fields = self._extract_message_fields_legacy(messages[0])
                    results[topic] = {
                        'fields': fields,
                        'message_type': msg_type,
                        'samples_analyzed': len(messages),
                        'analysis_source': 'legacy_samples'
                    }
                else:
                    results[topic] = {
                        'fields': {},
                        'message_type': msg_type,
                        'samples_analyzed': 0,
                        'analysis_source': 'no_messages'
                    }
                    
            except Exception as e:
                results[topic] = {
                    'fields': {},
                    'message_type': msg_type,
                    'samples_analyzed': 0,
                    'analysis_source': 'error',
                    'error': str(e)
                }
        
        return results
    
    def _run_optimized_analysis(self, bag_path: str, topics: List[str], connections: Dict[str, str]) -> Dict[str, Any]:
        """Run optimized type system field analysis"""
        return self.analyzer._analyze_fields_optimized(bag_path, topics, connections)
    
    def _run_cache_test(self, bag_path: str, topics: List[str], connections: Dict[str, str]) -> Dict[str, Any]:
        """Run cache performance test (second call should be faster)"""
        return self.analyzer._analyze_fields_optimized(bag_path, topics, connections)
    
    def _extract_message_fields_legacy(self, msg_data: Any, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """Legacy field extraction method"""
        fields = {}
        
        if current_depth >= max_depth:
            return {'...': f'(max depth {max_depth} reached)'}
        
        if hasattr(msg_data, '__dict__'):
            for attr_name in dir(msg_data):
                if not attr_name.startswith('_'):
                    try:
                        attr_value = getattr(msg_data, attr_name)
                        if not callable(attr_value):
                            field_name = f"{prefix}.{attr_name}" if prefix else attr_name
                            field_info = self._get_field_info_legacy(attr_value, field_name, max_depth, current_depth + 1)
                            fields[attr_name] = field_info
                    except Exception:
                        continue
        elif isinstance(msg_data, dict):
            for key, value in msg_data.items():
                field_name = f"{prefix}.{key}" if prefix else key
                field_info = self._get_field_info_legacy(value, field_name, max_depth, current_depth + 1)
                fields[key] = field_info
        else:
            fields['value'] = self._get_field_info_legacy(msg_data, prefix, max_depth, current_depth)
        
        return fields
    
    def _get_field_info_legacy(self, value: Any, field_name: str, max_depth: int, current_depth: int) -> Dict[str, Any]:
        """Legacy field info extraction"""
        field_info = {
            'type': type(value).__name__,
            'full_path': field_name
        }
        
        if isinstance(value, (int, float, bool)):
            field_info['value'] = value
        elif isinstance(value, str):
            field_info['value'] = f'"{value}"' if len(value) <= 50 else f'"{value[:47]}..."'
        elif isinstance(value, (list, tuple)):
            field_info['length'] = len(value)
            if len(value) > 0 and current_depth < max_depth:
                field_info['element_type'] = type(value[0]).__name__
                if hasattr(value[0], '__dict__') or isinstance(value[0], dict):
                    field_info['element_structure'] = self._extract_message_fields_legacy(value[0], f"{field_name}[0]", max_depth, current_depth + 1)
        elif hasattr(value, '__dict__') or isinstance(value, dict):
            if current_depth < max_depth:
                field_info['fields'] = self._extract_message_fields_legacy(value, field_name, max_depth, current_depth + 1)
        
        return field_info
    
    def _display_results(self, legacy_times: List[float], optimized_times: List[float], cache_times: List[float], topic_count: int):
        """Display performance test results"""
        
        # Calculate statistics
        legacy_avg = sum(legacy_times) / len(legacy_times)
        legacy_min = min(legacy_times)
        legacy_max = max(legacy_times)
        
        optimized_avg = sum(optimized_times) / len(optimized_times)
        optimized_min = min(optimized_times)
        optimized_max = max(optimized_times)
        
        cache_avg = sum(cache_times) / len(cache_times)
        cache_min = min(cache_times)
        cache_max = max(cache_times)
        
        # Performance improvements
        improvement_avg = ((legacy_avg - optimized_avg) / legacy_avg) * 100
        improvement_min = ((legacy_min - optimized_min) / legacy_min) * 100
        improvement_max = ((legacy_max - optimized_max) / legacy_max) * 100
        
        cache_improvement = ((optimized_avg - cache_avg) / optimized_avg) * 100
        
        # Create results table
        table = Table(title="Performance Test Results")
        table.add_column("Method", style="cyan")
        table.add_column("Average", style="magenta")
        table.add_column("Min", style="green")
        table.add_column("Max", style="red")
        table.add_column("Improvement", style="yellow")
        
        table.add_row(
            "Legacy (Sample-based)",
            f"{legacy_avg:.3f}s",
            f"{legacy_min:.3f}s",
            f"{legacy_max:.3f}s",
            "Baseline"
        )
        
        table.add_row(
            "Optimized (Type System)",
            f"{optimized_avg:.3f}s",
            f"{optimized_min:.3f}s",
            f"{optimized_max:.3f}s",
            f"{improvement_avg:+.1f}%"
        )
        
        table.add_row(
            "Cache (Second Call)",
            f"{cache_avg:.3f}s",
            f"{cache_min:.3f}s",
            f"{cache_max:.3f}s",
            f"{cache_improvement:+.1f}%"
        )
        
        self.console.print("\n")
        self.console.print(table)
        
        # Summary
        summary = f"""
[bold green]Performance Summary:[/bold green]
• Topics analyzed: {topic_count}
• Optimization improvement: {improvement_avg:.1f}%
• Cache improvement: {cache_improvement:.1f}%
• Best speedup: {improvement_max:.1f}%
• Worst case: {improvement_min:.1f}%

[bold cyan]Key Benefits:[/bold cyan]
• No message deserialization required
• Type definition caching
• Reduced I/O operations
• Better scalability with large bags
"""
        
        self.console.print(Panel.fit(summary, title="Optimization Results"))
    
    def _display_analyzer_stats(self):
        """Display message type analyzer statistics"""
        stats = self.type_analyzer.get_analysis_stats()
        
        if stats['total_requests'] > 0:
            stats_table = Table(title="Message Type Analyzer Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="magenta")
            
            stats_table.add_row("Total Requests", str(stats['total_requests']))
            stats_table.add_row("Cache Hits", str(stats['cache_hits']))
            stats_table.add_row("Type System Analyses", str(stats['type_system_analyses']))
            stats_table.add_row("Sample Fallbacks", str(stats['sample_fallbacks']))
            stats_table.add_row("Cache Hit Rate", f"{stats['cache_hit_rate']:.1f}%")
            stats_table.add_row("Type System Success Rate", f"{stats['type_system_success_rate']:.1f}%")
            stats_table.add_row("Fallback Rate", f"{stats['fallback_rate']:.1f}%")
            
            self.console.print("\n")
            self.console.print(stats_table)


def main():
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
    test = FieldAnalysisPerformanceTest(console)
    test.run_comprehensive_test(bag_path, iterations=3)


if __name__ == "__main__":
    main() 