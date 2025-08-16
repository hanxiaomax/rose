#!/usr/bin/env python3
"""
Cache Analysis Demo: Understanding DataFrame storage and scalability

This demo analyzes how DataFrames are cached and evaluates storage efficiency
for scenarios with many topics.
"""

import pickle
import sys
from pathlib import Path
import time

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from roseApp.core.cache import get_cache, BagCacheManager
from roseApp.core.optimized_storage import MessageStore, TopicDataFrame
import pandas as pd


def analyze_cache_storage():
    """Analyze how DataFrames are currently stored in cache"""
    
    print("🔍 Cache Storage Analysis")
    print("=" * 50)
    
    # Get cache instance
    cache = get_cache()
    cache_stats = cache.get_stats()
    
    print(f"📊 Cache Statistics:")
    print(f"   - Cache directory: {cache_stats['cache_dir']}")
    print(f"   - Total cache files: {cache_stats['entry_count']}")
    print(f"   - Total cache size: {cache_stats['total_size_bytes'] / 1024 / 1024:.1f} MB")
    print(f"   - Memory entries: {cache_stats['memory_entries']}")
    
    # Analyze individual cache files
    cache_dir = Path(cache_stats['cache_dir'])
    cache_files = list(cache_dir.glob("*.pkl"))
    
    print(f"\n📁 Cache File Analysis:")
    for cache_file in sorted(cache_files, key=lambda x: x.stat().st_size, reverse=True):
        size_mb = cache_file.stat().st_size / 1024 / 1024
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cache_file.stat().st_mtime))
        
        print(f"   {cache_file.name}:")
        print(f"     - Size: {size_mb:.1f} MB")
        print(f"     - Modified: {mtime}")
        
        # Try to analyze content
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            if hasattr(data, 'bag_info') and hasattr(data.bag_info, 'df'):
                df = data.bag_info.df
                if df is not None:
                    print(f"     - Contains DataFrame: {df.shape}")
                    print(f"     - DataFrame memory: {df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
                    print(f"     - Sparsity: {(df.isnull().sum().sum() / df.size):.2%}")
                else:
                    print(f"     - No DataFrame")
            else:
                print(f"     - Type: {type(data)}")
                
        except Exception as e:
            print(f"     - Error reading: {e}")


def simulate_large_topic_scenario():
    """Simulate storage requirements for scenarios with many topics"""
    
    print(f"\n🚀 Large Topic Scenario Simulation")
    print("=" * 50)
    
    # Simulate different scenarios
    scenarios = [
        {"topics": 10, "messages_per_topic": 1000, "columns_per_topic": 20},
        {"topics": 50, "messages_per_topic": 1000, "columns_per_topic": 30},
        {"topics": 100, "messages_per_topic": 1000, "columns_per_topic": 25},
        {"topics": 500, "messages_per_topic": 500, "columns_per_topic": 20},
        {"topics": 1000, "messages_per_topic": 200, "columns_per_topic": 15},
    ]
    
    print(f"📈 Storage Comparison: Sparse vs Optimized")
    print(f"{'Scenario':<12} {'Topics':<8} {'Messages':<10} {'Sparse MB':<12} {'Optimized MB':<15} {'Savings':<10}")
    print("-" * 80)
    
    for i, scenario in enumerate(scenarios, 1):
        topics = scenario["topics"]
        messages_per_topic = scenario["messages_per_topic"]
        columns_per_topic = scenario["columns_per_topic"]
        
        # Calculate sparse DataFrame size
        total_messages = topics * messages_per_topic
        total_columns = topics * columns_per_topic  # All topics combined
        
        # Assume 8 bytes per cell (float64) + overhead
        sparse_size_mb = (total_messages * total_columns * 8) / 1024 / 1024
        
        # Calculate optimized storage size (only non-null data)
        optimized_size_mb = (topics * messages_per_topic * columns_per_topic * 8) / 1024 / 1024
        
        savings_pct = (1 - optimized_size_mb / sparse_size_mb) * 100
        
        print(f"Scenario {i:<4} {topics:<8} {total_messages:<10} {sparse_size_mb:<12.1f} {optimized_size_mb:<15.1f} {savings_pct:<10.1f}%")


def analyze_messagestore_scalability():
    """Analyze MessageStore scalability for many topics"""
    
    print(f"\n⚡ MessageStore Scalability Analysis")
    print("=" * 50)
    
    # Create test MessageStore with varying topic counts
    test_scenarios = [10, 50, 100, 500, 1000]
    
    print(f"📊 Memory Usage per Topic Count:")
    print(f"{'Topics':<8} {'Store Size':<12} {'Lookup Time':<12} {'Memory/Topic':<15}")
    print("-" * 50)
    
    for topic_count in test_scenarios:
        # Create mock MessageStore
        store = MessageStore()
        
        # Add mock topics
        for i in range(topic_count):
            # Create small test DataFrame
            test_data = {
                'timestamp_sec': [1000.0 + j for j in range(100)],
                'topic': [f'/topic_{i}'] * 100,
                'value': [j * 0.1 for j in range(100)]
            }
            df = pd.DataFrame(test_data)
            
            topic_df = TopicDataFrame(
                topic_name=f'/topic_{i}',
                message_type=f'test_msgs/Topic{i}',
                df=df
            )
            store.add_topic_dataframe(topic_df)
        
        # Measure memory usage
        memory_summary = store.get_memory_summary()
        total_memory_mb = memory_summary['total_memory_mb']
        memory_per_topic = total_memory_mb / topic_count
        
        # Measure lookup time
        start_time = time.time()
        for i in range(min(100, topic_count)):  # Test up to 100 lookups
            _ = store.get_topic_data(f'/topic_{i}')
        lookup_time_ms = (time.time() - start_time) * 1000 / min(100, topic_count)
        
        print(f"{topic_count:<8} {total_memory_mb:<12.2f} {lookup_time_ms:<12.3f} {memory_per_topic:<15.3f}")


def recommend_storage_strategy():
    """Provide recommendations for different use cases"""
    
    print(f"\n💡 Storage Strategy Recommendations")
    print("=" * 50)
    
    recommendations = [
        {
            "scenario": "Small datasets (< 20 topics)",
            "strategy": "Either approach works well",
            "reason": "Memory overhead is minimal"
        },
        {
            "scenario": "Medium datasets (20-100 topics)",
            "strategy": "Optimized MessageStore recommended",
            "reason": "Significant memory savings with good performance"
        },
        {
            "scenario": "Large datasets (100-500 topics)",
            "strategy": "MessageStore with selective caching",
            "reason": "Cache only frequently accessed topics"
        },
        {
            "scenario": "Very large datasets (500+ topics)",
            "strategy": "Hybrid approach with lazy loading",
            "reason": "Load topics on-demand, cache hot topics only"
        }
    ]
    
    for rec in recommendations:
        print(f"\n📋 {rec['scenario']}:")
        print(f"   Strategy: {rec['strategy']}")
        print(f"   Reason: {rec['reason']}")


def propose_cache_optimization():
    """Propose optimizations for caching with many topics"""
    
    print(f"\n🔧 Proposed Cache Optimizations")
    print("=" * 50)
    
    optimizations = [
        {
            "name": "Selective Topic Caching",
            "description": "Cache only frequently accessed topics",
            "implementation": "Add access tracking and LRU eviction"
        },
        {
            "name": "Compressed Storage",
            "description": "Use compression for cached DataFrames",
            "implementation": "Compress pickle data with gzip/lz4"
        },
        {
            "name": "Lazy Loading",
            "description": "Load topic DataFrames on first access",
            "implementation": "Store metadata only, load data on demand"
        },
        {
            "name": "Topic Grouping",
            "description": "Group related topics in single cache entries",
            "implementation": "Group by message type or namespace"
        },
        {
            "name": "Time-based Partitioning",
            "description": "Split large topics by time ranges",
            "implementation": "Partition DataFrames by time windows"
        }
    ]
    
    for opt in optimizations:
        print(f"\n🔨 {opt['name']}:")
        print(f"   Description: {opt['description']}")
        print(f"   Implementation: {opt['implementation']}")


def main():
    """Main analysis function"""
    
    print("🎯 ROS Bag DataFrame Cache Analysis")
    print("=" * 60)
    
    # Step 1: Analyze current cache storage
    analyze_cache_storage()
    
    # Step 2: Simulate large topic scenarios
    simulate_large_topic_scenario()
    
    # Step 3: Analyze MessageStore scalability
    analyze_messagestore_scalability()
    
    # Step 4: Provide recommendations
    recommend_storage_strategy()
    
    # Step 5: Propose optimizations
    propose_cache_optimization()
    
    print(f"\n✅ Analysis completed!")


if __name__ == "__main__":
    main()
