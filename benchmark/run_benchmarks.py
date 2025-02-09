#!/usr/bin/env python3

"""
One-click benchmark runner with statistical analysis.
This script runs the benchmark multiple times and generates statistical results.
"""

import os
import json
import argparse
import numpy as np
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt
from datetime import datetime
import shutil
from rosbag_benchmark import run_benchmark

class BenchmarkRunner:
    """
    A class to manage multiple benchmark runs and generate statistical results.
    """
    
    def __init__(self, bag_path: str, runs: int, output_dir: str):
        """
        Initialize the benchmark runner.
        
        Args:
            bag_path: Path to the input bag file
            runs: Number of benchmark runs
            output_dir: Directory to save results
        """
        self.bag_path = bag_path
        self.runs = runs
        self.output_dir = Path(output_dir)
        self.results: List[Dict] = []
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def run(self):
        """Run multiple benchmark tests"""
        print(f"\nStarting {self.runs} benchmark runs...")
        
        for i in range(self.runs):
            print(f"\nRun #{i+1}/{self.runs}")
            
            # Run single benchmark and get results directly
            result = run_benchmark(self.bag_path)
            
            # Store results in memory
            self.results.append(result)
            
            # Clean up generated bag files immediately after each run
            self._cleanup_output_bags(result)
    
    def _cleanup_output_bags(self, result: Dict):
        """Clean up benchmark-generated bag files immediately after processing"""
        for impl in ['python_impl', 'cpp_impl', 'ros_cli']:
            if impl in result and result[impl] and 'output_path' in result[impl]:
                try:
                    if os.path.exists(result[impl]['output_path']):
                        os.remove(result[impl]['output_path'])
                        print(f"Cleaned up temporary file: {result[impl]['output_path']}")
                except OSError as e:
                    print(f"Error cleaning up {result[impl]['output_path']}: {e}")

    def analyze(self):
        """Analyze results and generate statistics"""
        print("\nGenerating statistical analysis...")
        
        # Save all results to a single file
        self._save_combined_results()
        
        # Extract processing times and calculate throughput for each implementation
        times = {
            'python': [r['python_impl']['time'] for r in self.results],
            'ros_cli': [r['ros_cli']['time'] for r in self.results]
        }
        
        throughput = {
            'python': [r['python_impl']['messages'] / r['python_impl']['time'] for r in self.results],
            'ros_cli': [r['ros_cli']['messages'] / r['ros_cli']['time'] for r in self.results]
        }
        
        if self.results[0]['cpp_impl']:
            times['cpp'] = [r['cpp_impl']['time'] for r in self.results]
            throughput['cpp'] = [r['cpp_impl']['messages'] / r['cpp_impl']['time'] for r in self.results]
        
        # Calculate statistics
        stats = {}
        for impl in times.keys():
            stats[impl] = {
                'time': {
                    'mean': np.mean(times[impl]),
                    'std': np.std(times[impl]),
                    'min': np.min(times[impl]),
                    'max': np.max(times[impl]),
                    'median': np.median(times[impl])
                },
                'throughput': {
                    'mean': np.mean(throughput[impl]),
                    'std': np.std(throughput[impl]),
                    'min': np.min(throughput[impl]),
                    'max': np.max(throughput[impl]),
                    'median': np.median(throughput[impl])
                }
            }
        
        # Generate reports and plots
        self._generate_stats_report(stats)
        self._create_boxplot(times, 'time')
        self._create_boxplot(throughput, 'throughput')
        self._create_bar_plots(stats)
        
        return stats
    
    def _save_combined_results(self):
        """Save all results to a single JSON file"""
        combined_file = self.output_dir / 'all_results.json'
        try:
            with open(combined_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"Saved combined results to {combined_file}")
        except Exception as e:
            print(f"Error saving combined results: {e}")
    
    def _generate_stats_report(self, stats: Dict):
        """Generate statistical report"""
        report = [
            "# Benchmark Statistical Report\n",
            f"- Input Bag: `{self.bag_path}`",
            f"- Number of Runs: {self.runs}",
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "## Statistical Results\n"
        ]
        
        for impl, data in stats.items():
            report.extend([
                f"### {impl.upper()} Implementation",
                "#### Processing Time",
                f"- Mean Time: {data['time']['mean']:.2f} seconds",
                f"- Standard Deviation: {data['time']['std']:.2f} seconds",
                f"- Minimum Time: {data['time']['min']:.2f} seconds",
                f"- Maximum Time: {data['time']['max']:.2f} seconds",
                f"- Median Time: {data['time']['median']:.2f} seconds",
                "\n#### Throughput",
                f"- Mean Throughput: {data['throughput']['mean']:.2f} messages/second",
                f"- Standard Deviation: {data['throughput']['std']:.2f} messages/second",
                f"- Minimum Throughput: {data['throughput']['min']:.2f} messages/second",
                f"- Maximum Throughput: {data['throughput']['max']:.2f} messages/second",
                f"- Median Throughput: {data['throughput']['median']:.2f} messages/second\n"
            ])
        
        # Add performance comparisons if C++ implementation is available
        if 'cpp' in stats:
            report.extend([
                "## Performance Comparisons",
                f"- Average Speedup (C++ vs Python): {stats['python']['time']['mean'] / stats['cpp']['time']['mean']:.2f}x",
                f"- Average Speedup (C++ vs ROS CLI): {stats['ros_cli']['time']['mean'] / stats['cpp']['time']['mean']:.2f}x",
                f"- Average Speedup (ROS CLI vs Python): {stats['python']['time']['mean'] / stats['ros_cli']['time']['mean']:.2f}x\n"
            ])
        
        with open(self.output_dir / 'statistical_report.md', 'w') as f:
            f.write('\n'.join(report))
    
    def _create_boxplot(self, data: Dict, metric: str):
        """Create box plot for time or throughput distribution"""
        plt.figure(figsize=(10, 6))
        
        # Prepare data
        plot_data = []
        labels = []
        for impl, values in data.items():
            plot_data.append(values)
            labels.append(impl.upper())
        
        # Create box plot
        plt.boxplot(plot_data, labels=labels)
        title = 'Processing Time Distribution' if metric == 'time' else 'Throughput Distribution'
        ylabel = 'Time (seconds)' if metric == 'time' else 'Messages per Second'
        plt.title(title)
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.3)
        
        # Save plot
        filename = 'time_distribution.png' if metric == 'time' else 'throughput_distribution.png'
        plt.savefig(self.output_dir / filename, bbox_inches='tight')
        plt.close()

    def _create_bar_plots(self, stats: Dict):
        """Create bar plots for time and throughput comparisons"""
        metrics = ['time', 'throughput']
        for metric in metrics:
            plt.figure(figsize=(12, 6))
            
            implementations = list(stats.keys())
            x = np.arange(len(implementations))
            width = 0.25
            
            # Extract data
            means = [stats[impl][metric]['mean'] for impl in implementations]
            mins = [stats[impl][metric]['min'] for impl in implementations]
            maxs = [stats[impl][metric]['max'] for impl in implementations]
            
            # Create bars
            plt.bar(x, means, width, label='Mean', color='skyblue')
            plt.bar(x - width, mins, width, label='Best', color='lightgreen')
            plt.bar(x + width, maxs, width, label='Worst', color='salmon')
            
            # Customize plot
            title = 'Processing Time Comparison' if metric == 'time' else 'Throughput Comparison'
            ylabel = 'Time (seconds)' if metric == 'time' else 'Messages per Second'
            plt.title(title)
            plt.ylabel(ylabel)
            plt.xlabel('Implementation')
            plt.xticks(x, [impl.upper() for impl in implementations])
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            # Add value labels
            for i, v in enumerate(means):
                plt.text(i, v, f'{v:.2f}', ha='center', va='bottom')
                plt.text(i - width, mins[i], f'{mins[i]:.2f}', ha='center', va='bottom')
                plt.text(i + width, maxs[i], f'{maxs[i]:.2f}', ha='center', va='bottom')
            
            # Save plot
            filename = 'time_comparison.png' if metric == 'time' else 'throughput_comparison.png'
            plt.savefig(self.output_dir / filename, bbox_inches='tight')
            plt.close()

def main():
    parser = argparse.ArgumentParser(description='Run multiple benchmarks with statistical analysis')
    parser.add_argument('bag_path', type=str, help='Path to input bag file')
    parser.add_argument('--runs', type=int, default=5,
                      help='Number of benchmark runs (default: 5)')
    parser.add_argument('--output-dir', type=str, default='benchmark_stats',
                      help='Directory to save statistical results (default: benchmark_stats)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.bag_path):
        print(f"Error: Bag file {args.bag_path} does not exist")
        return
    
    # Run benchmarks
    runner = BenchmarkRunner(args.bag_path, args.runs, args.output_dir)
    runner.run()
    stats = runner.analyze()
    
    print(f"\nStatistical results saved to {args.output_dir}")
    print("\nPerformance Summary:")
    for impl, data in stats.items():
        print(f"\n{impl.upper()}:")
        print(f"  Mean Time: {data['time']['mean']:.2f} ± {data['time']['std']:.2f} seconds")
        print(f"  Time Range: [{data['time']['min']:.2f}, {data['time']['max']:.2f}] seconds")
        print(f"  Mean Throughput: {data['throughput']['mean']:.2f} ± {data['throughput']['std']:.2f} msg/s")
        print(f"  Throughput Range: [{data['throughput']['min']:.2f}, {data['throughput']['max']:.2f}] msg/s")

if __name__ == '__main__':
    main() 