#!/usr/bin/env python3

"""
Visualization script for rosbag benchmark results.
Creates comparative plots and generates a detailed report.
"""

import json
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def load_results(results_file: str) -> dict:
    """
    Load benchmark results from JSON file.
    
    Args:
        results_file: Path to the results JSON file
        
    Returns:
        Dict containing the benchmark results
    """
    with open(results_file, 'r') as f:
        return json.load(f)

def create_time_comparison_plot(results: dict, output_dir: Path):
    """
    Create a bar plot comparing processing times.
    
    Args:
        results: Benchmark results dictionary
        output_dir: Directory to save the plot
    """
    plt.figure(figsize=(12, 6))
    
    implementations = ['Python Lib:Rosbag', 'ROS CLI:Filter']
    times = [results['python_impl']['time'], results['ros_cli']['time']]
    
    if results['cpp_impl']:
        implementations.append('Our C++ Interface')
        times.append(results['cpp_impl']['time'])
    
    bars = plt.bar(implementations, times)
    plt.title('Rosbag Processing Time Comparison')
    plt.ylabel('Time (seconds)')
    plt.grid(True, alpha=0.3)
    
    # Add value labels on top of each bar
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}s',
                ha='center', va='bottom')
    
    plt.savefig(output_dir / 'time_comparison.png', bbox_inches='tight')
    plt.close()

def create_throughput_plot(results: dict, output_dir: Path):
    """
    Create a plot showing messages per second throughput.
    
    Args:
        results: Benchmark results dictionary
        output_dir: Directory to save the plot
    """
    plt.figure(figsize=(12, 6))
    
    implementations = ['Python Lib:Rosbag', 'ROS CLI:Filter']
    throughputs = [
        results['python_impl']['messages'] / results['python_impl']['time'],
        results['ros_cli']['messages'] / results['ros_cli']['time']
    ]
    
    if results['cpp_impl']:
        implementations.append('Our C++ Interface')
        cpp_throughput = results['cpp_impl']['messages'] / results['cpp_impl']['time']
        throughputs.append(cpp_throughput)
    
    bars = plt.bar(implementations, throughputs)
    plt.title('Message Processing Throughput')
    plt.ylabel('Messages per Second')
    plt.grid(True, alpha=0.3)
    
    # Add value labels on top of each bar
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)} msg/s',
                ha='center', va='bottom')
    
    plt.savefig(output_dir / 'throughput_comparison.png', bbox_inches='tight')
    plt.close()

def generate_report(results: dict, output_dir: Path):
    """
    Generate a detailed markdown report of the benchmark results.
    
    Args:
        results: Benchmark results dictionary
        output_dir: Directory to save the report
    """
    bag_info = results['bag_info']
    
    report = [
        "# Rosbag Benchmark Report\n",
        "## Bag Information",
        f"- File: `{bag_info['path']}`",
        f"- Size: {bag_info['size'] / (1024*1024):.2f} MB",
        f"- Duration: {bag_info['duration']:.2f} seconds",
        f"- Total Messages: {bag_info['message_count']}",
        f"- Topics: {', '.join(bag_info['topics'])}",
        "\n## Benchmark Results\n",
        "### Python Lib:Rosbag",
        f"- Processing Time: {results['python_impl']['time']:.2f} seconds",
        f"- Messages Processed: {results['python_impl']['messages']}",
        f"- Throughput: {results['python_impl']['messages'] / results['python_impl']['time']:.2f} messages/second",
        f"- Output File: `{results['python_impl']['output_path']}`",
        "\n### ROS CLI:Filter",
        f"- Processing Time: {results['ros_cli']['time']:.2f} seconds",
        f"- Messages Processed: {results['ros_cli']['messages']}",
        f"- Throughput: {results['ros_cli']['messages'] / results['ros_cli']['time']:.2f} messages/second",
        f"- Output File: `{results['ros_cli']['output_path']}`"
    ]
    
    if results['cpp_impl']:
        report.extend([
            "\n### Our C++ Interface",
            f"- Processing Time: {results['cpp_impl']['time']:.2f} seconds",
            f"- Messages Processed: {results['cpp_impl']['messages']}",
            f"- Throughput: {results['cpp_impl']['messages'] / results['cpp_impl']['time']:.2f} messages/second",
            f"- Output File: `{results['cpp_impl']['output_path']}`",
            "\n### Performance Comparison",
            f"- Speedup (C++ vs Python): {results['python_impl']['time'] / results['cpp_impl']['time']:.2f}x",
            f"- Speedup (C++ vs ROS CLI): {results['ros_cli']['time'] / results['cpp_impl']['time']:.2f}x",
            f"- Speedup (ROS CLI vs Python): {results['python_impl']['time'] / results['ros_cli']['time']:.2f}x"
        ])
    
    with open(output_dir / 'report.md', 'w') as f:
        f.write('\n'.join(report))

def main():
    parser = argparse.ArgumentParser(description='Visualize rosbag benchmark results')
    parser.add_argument('results_file', type=str, help='Path to benchmark results JSON file')
    parser.add_argument('--output-dir', type=str, default='benchmark_results',
                      help='Directory to save visualization results (default: benchmark_results)')
    
    args = parser.parse_args()
    results = load_results(args.results_file)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Generate visualizations and report
    create_time_comparison_plot(results, output_dir)
    create_throughput_plot(results, output_dir)
    generate_report(results, output_dir)
    
    print(f"Visualization results saved to {output_dir}")

if __name__ == '__main__':
    main() 