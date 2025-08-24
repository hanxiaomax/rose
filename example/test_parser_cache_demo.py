#!/usr/bin/env python3
"""
Demo script showing parser and cache integration with optimized data structure

This script demonstrates:
1. Using parser to analyze a bag file
2. Creating cache entries
3. Reading from cache
4. Accessing optimized data structure members
"""

import sys
import time
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append('.')

from roseApp.core.parser import create_parser
from roseApp.core.cache import create_bag_cache_manager
from roseApp.core.model import AnalysisLevel


async def main():

    bag_path = Path("roseApp/tests/demo.bag")

    
    print(f"Target bag file: {bag_path}")

 
    parser = create_parser()
    cache_manager = create_bag_cache_manager()
    cache_manager.clear(bag_path)
    print(cache_manager.get_all_cache_entries())
    start_time = time.time()
    
    try:
        bag_info, parse_time = await parser.load_bag_async(str(bag_path), build_index=True)
        total_time = time.time() - start_time
        print(cache_manager.get_all_cache_entries())
        print(f"Parsing completed in {parse_time:.3f}s (total: {total_time:.3f}s)")
        print(f"Analysis level: {bag_info.analysis_level.value}")
        print(f"File size: {bag_info.file_size_mb:.1f} MB")
        print(f"Topics found: {len(bag_info.topics)}")
        print()
        
    except Exception as e:
        print(f"Parsing failed: {e}")
        return
    

    
    # Time range information
    if bag_info.time_range:
        duration = bag_info.time_range.get_duration_seconds()
        print(f"Time range:")
        print(f"  Start: {bag_info.time_range.start_time}")
        print(f"  End: {bag_info.time_range.end_time}")
        print(f"  Duration: {duration:.3f} seconds")
        print()
    
    # Topics information using optimized list structure
    print(f"📝 Topics ({len(bag_info.topics)}):")
    topics= bag_info.get_topics() 
    topic_names = [topic.name for topic in topics]
    for i, topic_name in enumerate(topic_names[:5]):  # Show first 5
        topic = bag_info.find_topic(topic_name)  # Optimized find method
        if topic:
            print(f"  {i+1}. {topic.name}")
            print(f"     Type: {topic.message_type}")
            print(f"     Count: {topic.message_count or 'Unknown'}")
            print(f"     Frequency: {topic.message_frequency or 0:.1f} Hz")
    
    if len(topic_names) > 5:
        print(f"  ... and {len(topic_names) - 5} more topics")
    print()
    
    # Message types information
    if bag_info.message_types:
        print(f"Message types ({len(bag_info.message_types)}):")
        for i, msg_type in enumerate(bag_info.message_types[:3]):  # Show first 3
            print(f"  {i+1}. {msg_type.message_type}")
            if msg_type.fields:
                print(f"     Fields: {len(msg_type.fields)}")
        if len(bag_info.message_types) > 3:
            print(f"  ... and {len(bag_info.message_types) - 3} more types")
        print()
    

    cached_entry = cache_manager.get_analysis(bag_path)
    if cached_entry:
        print("✅ Cache entry found!")
        cached_bag_info = cached_entry.bag_info
        
        print(f"📊 Cache verification:")
        print(f"  File path matches: {cached_bag_info.file_path == bag_info.file_path}")
        print(f"  Topics count matches: {len(cached_bag_info.topics) == len(bag_info.topics)}")
        print(f"  Analysis level matches: {cached_bag_info.analysis_level == bag_info.analysis_level}")
        print(f"  Cache file path: {cached_entry.cache_path}")
        print(f"  Cache file size: {cached_entry.cache_file_size_mb:.1f} MB")
        print(f"  Memory footprint: {cached_bag_info.get_memory_footprint():,} bytes")
        print()
        
        # Test serialization/deserialization
        print("Testing serialization:")
        json_str = cached_bag_info.to_json()
        print(f"  JSON size: {len(json_str):,} characters")
        
        # Test deserialization
        from roseApp.core.model import ComprehensiveBagInfo
        restored = ComprehensiveBagInfo.from_json(json_str)
        print(f"  Restored topics: {len(restored.topics)}")
        print(f"  Serialization works: {len(restored.topics) == len(cached_bag_info.topics)}")
        print()
        
    else:
        print("❌ No cache entry found")
        print()
    
    # Step 6: Performance comparison
    print("⚡ Step 6: Performance comparison")
    
    # Test cache retrieval speed
    start_time = time.time()
    for _ in range(100):
        cached_entry = cache_manager.get_analysis(bag_path)
        if cached_entry:
            _ = cached_entry.bag_info.get_topic_names()
    cache_time = time.time() - start_time
    
    print(f"📈 Performance metrics:")
    print(f"  Cache retrieval (100x): {cache_time*1000:.1f}ms")
    print(f"  Average per retrieval: {cache_time*10:.1f}ms")
    print(f"  Topics access speed: Very fast (list iteration)")
    print()
    
    # Step 7: Memory usage analysis
    memory_footprint = bag_info.get_memory_footprint()
    print(f"📊 Memory analysis:")
    print(f"  Data structure footprint: {memory_footprint:,} bytes ({memory_footprint/1024:.1f} KB)")
    print(f"  Topics: {len(bag_info.topics)} items (List structure)")
    print(f"  Message types: {len(bag_info.message_types)} items (List structure)")
    print(f"  Memory efficiency: Optimized (no dictionary overhead)")
    print()
    
    
    print(bag_info.df.to_csv("df.csv"))
    
    range_data = bag_info.df[bag_info.df['topic'] == '/radar/range']['range']
    track_angles = bag_info.df['tracks[0].angle'].dropna()
    print(range_data)
    print(track_angles)



if __name__ == "__main__":
    asyncio.run(main())