#!/usr/bin/env python3

"""
ROS Bag reading performance benchmark script.
Compares performance between rosbag and rosbag_io_py implementations.
"""

import os
import time
import json
import argparse
from typing import Dict, List, Tuple
from pathlib import Path
import rosbag
from tqdm import tqdm

try:
    import rosbag_io_py
    HAS_CPP_IMPL = True
except ImportError:
    HAS_CPP_IMPL = False
    print("Warning: rosbag_io_py not found, will only test Python implementation")

def get_bag_info(bag_path: str) -> Dict:
    """
    Get basic information about the bag file.
    
    Args:
        bag_path: Path to the bag file
        
    Returns:
        Dict containing bag information
    """
    with rosbag.Bag(bag_path) as bag:
        info = bag.get_type_and_topic_info()
        return {
            'path': bag_path,
            'size': os.path.getsize(bag_path),
            'duration': bag.get_end_time() - bag.get_start_time(),
            'message_count': bag.get_message_count(),
            'topics': list(info.topics.keys())
        }

def benchmark_python_impl(bag_path: str, output_path: str) -> Tuple[float, int]:
    """
    Benchmark the Python rosbag implementation.
    
    Args:
        bag_path: Input bag file path
        output_path: Output bag file path
        
    Returns:
        Tuple of (processing_time, message_count)
    """
    start_time = time.time()
    msg_count = 0
    
    with rosbag.Bag(bag_path) as inbag:
        with rosbag.Bag(output_path, 'w') as outbag:
            for topic, msg, t in tqdm(inbag.read_messages()):
                outbag.write(topic, msg, t)
                msg_count += 1
                
    end_time = time.time()
    return end_time - start_time, msg_count

def benchmark_cpp_impl(bag_path: str, output_path: str) -> Tuple[float, int]:
    """
    Benchmark the C++ rosbag_io_py implementation.
    
    Args:
        bag_path: Input bag file path
        output_path: Output bag file path
        
    Returns:
        Tuple of (processing_time, message_count)
    """
    if not HAS_CPP_IMPL:
        raise ImportError("rosbag_io_py is not available")
        
    start_time = time.time()
    
    # 创建rosbag_io对象
    bag_io = rosbag_io_py.rosbag_io()
    
    # 加载输入bag文件
    bag_io.load(bag_path)
    
    # 获取所有话题
    topics = bag_io.get_topics()
    
    # 获取时间范围
    time_range = bag_io.get_time_range()
    
    # 导出到新的bag文件
    msg_count = 0
    with tqdm() as pbar:
        bag_io.dump(output_path, topics, time_range)
        # 获取消息数量
        with rosbag.Bag(output_path) as outbag:
            msg_count = outbag.get_message_count()
            pbar.update(msg_count)
    
    end_time = time.time()
    return end_time - start_time, msg_count

def run_benchmark(input_bag: str) -> Dict:
    """
    Run the benchmark comparison.
    
    Args:
        input_bag: Path to input bag file
        
    Returns:
        Dict containing benchmark results
    """
    results = {
        'bag_info': get_bag_info(input_bag),
        'python_impl': {},
        'cpp_impl': {} if HAS_CPP_IMPL else None
    }
    
    # Python implementation benchmark
    py_output = str(Path(input_bag).parent / f"{Path(input_bag).stem}_py_output.bag")
    py_time, py_msgs = benchmark_python_impl(input_bag, py_output)
    results['python_impl'] = {
        'time': py_time,
        'messages': py_msgs,
        'output_path': py_output
    }
    
    # C++ implementation benchmark (if available)
    if HAS_CPP_IMPL:
        cpp_output = str(Path(input_bag).parent / f"{Path(input_bag).stem}_cpp_output.bag")
        cpp_time, cpp_msgs = benchmark_cpp_impl(input_bag, cpp_output)
        results['cpp_impl'] = {
            'time': cpp_time,
            'messages': cpp_msgs,
            'output_path': cpp_output
        }
    
    return results

def main():
    parser = argparse.ArgumentParser(description='ROS Bag reading performance benchmark')
    parser.add_argument('bag_path', type=str, help='Path to input bag file')
    parser.add_argument('--output', type=str, default='benchmark_results.json',
                      help='Path to save benchmark results (default: benchmark_results.json)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.bag_path):
        print(f"Error: Bag file {args.bag_path} does not exist")
        return
    
    print(f"Running benchmark on {args.bag_path}")
    results = run_benchmark(args.bag_path)
    
    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {args.output}")
    print("\nSummary:")
    print(f"Python implementation: {results['python_impl']['time']:.2f} seconds")
    if results['cpp_impl']:
        print(f"C++ implementation: {results['cpp_impl']['time']:.2f} seconds")
        speedup = results['python_impl']['time'] / results['cpp_impl']['time']
        print(f"Speedup: {speedup:.2f}x")

if __name__ == '__main__':
    main() 