# ROS Bag Analysis Performance Benchmark

This benchmark suite compares the performance of async vs sync ROS bag analysis methods, helping you understand when to use each approach for optimal performance.

## Features

- **Comprehensive Performance Testing**: Tests both async and sync analysis across different analysis levels
- **Memory Monitoring**: Tracks peak and average memory usage during analysis
- **Cache Performance**: Measures cache hit rates for async analysis
- **Multiple Analysis Levels**: Tests metadata, statistics, messages, and field analysis
- **Rich Reporting**: Beautiful terminal output with performance recommendations
- **JSON Export**: Saves detailed results for further analysis

## Test Architecture

### Analysis Levels Tested

1. **Metadata Level** (`CacheLevel.METADATA`)
   - Basic bag information (topics, connections, time range)
   - Fastest analysis level
   - Minimal memory usage

2. **Statistics Level** (`CacheLevel.STATISTICS`)
   - Message counts, sizes, and frequencies
   - Moderate processing time
   - Standard memory usage

3. **Messages Level** (`CacheLevel.MESSAGES`)
   - Collects sample messages for analysis
   - Higher processing time
   - Increased memory usage

4. **Fields Level** (`CacheLevel.FIELDS`)
   - Complete field structure analysis
   - Highest processing time
   - Maximum memory usage

### Performance Metrics

- **Execution Time**: Duration of analysis in seconds
- **Memory Usage**: Peak and average memory consumption in MB
- **Cache Hit Rate**: Percentage of analysis requests served from cache
- **File Size Impact**: Performance scaling with bag file size
- **Topic Count Impact**: Performance scaling with topic complexity

## Usage

### Quick Start

1. **Run the demo script**:
   ```bash
   python benchmark_demo.py
   ```

2. **For testing with real bag files**, edit `benchmark_demo.py` and add your bag file paths:
   ```python
   test_bags = [
       "/path/to/small_test.bag",
       "/path/to/medium_test.bag",
       "/path/to/large_test.bag"
   ]
   ```

3. **Run the benchmark**:
   ```bash
   python benchmark_demo.py
   ```

### Advanced Usage

```python
from tests.benchmark.test_async_vs_sync_performance import BagAnalysisBenchmark

# Create benchmark instance
benchmark = BagAnalysisBenchmark()

# Run comprehensive benchmark
summary = await benchmark.run_comprehensive_benchmark(
    test_bags=["bag1.bag", "bag2.bag"],
    iterations=5
)

# Display results
benchmark.display_results(summary)

# Save results
benchmark.save_results(summary, "results.json")
```

### Custom Analysis Levels

```python
# Test specific analysis levels
analysis_levels = [
    ("metadata", CacheLevel.METADATA),
    ("statistics", CacheLevel.STATISTICS)
]

summary = await benchmark.run_comprehensive_benchmark(
    test_bags=test_bags,
    analysis_levels=analysis_levels,
    iterations=3
)
```

## Benchmark Results

### Sample Output

```
Performance Comparison by Analysis Level
┌──────────┬─────────────────┬──────────────────┬─────────────────────┬────────────────┬─────────────────────┐
│ Level    │ Async Avg Time  │ Sync Avg Time    │ Time Improvement    │ Cache Hit Rate │ Memory Usage        │
├──────────┼─────────────────┼──────────────────┼─────────────────────┼────────────────┼─────────────────────┤
│ Metadata │ 0.055s          │ 0.125s           │ +56.0%              │ 50.0%          │ A:135.0MB S:170.0MB │
│ Statistics│ 0.065s          │ 0.135s           │ +51.9%              │ 50.0%          │ A:135.0MB S:170.0MB │
│ Messages │ 0.075s          │ 0.145s           │ +48.3%              │ 50.0%          │ A:135.0MB S:170.0MB │
│ Fields   │ 0.085s          │ 0.155s           │ +45.2%              │ 50.0%          │ A:135.0MB S:170.0MB │
└──────────┴─────────────────┴──────────────────┴─────────────────────┴────────────────┴─────────────────────┘
```

### Performance Recommendations

- ✓ Async analysis shows 45-56% performance improvement across all levels
- ✓ High cache hit rate (50%) for all levels - async caching is effective
- 💡 Use async analysis for repeated analysis of the same bags
- 💡 Use sync analysis for one-time analysis of small bags
- 💡 Async analysis benefits increase with file size and complexity

## Key Performance Differences

### Async Analysis Benefits

1. **Intelligent Caching**: Reuses analysis results for repeated operations
2. **Background Processing**: Can warm up cache in the background
3. **Space-for-Time Optimization**: Trades memory for faster subsequent access
4. **Concurrent Processing**: Can handle multiple analysis requests efficiently

### Sync Analysis Benefits

1. **Lower Memory Usage**: No cache overhead
2. **Predictable Performance**: Consistent timing without cache effects
3. **Simpler Implementation**: Straightforward sequential processing
4. **Better for One-time Analysis**: No caching overhead for single-use scenarios

## Understanding the Results

### When to Use Async Analysis

- **Repeated Analysis**: When analyzing the same bags multiple times
- **Large Files**: Better performance scaling with file size
- **Complex Analysis**: Field-level analysis benefits most from caching
- **Production Environments**: Where analysis requests are frequent

### When to Use Sync Analysis

- **Small Files**: Overhead of async setup may not be worth it
- **One-time Analysis**: When bags are analyzed only once
- **Memory-Constrained Environments**: Lower memory footprint
- **Simple Analysis**: Basic metadata extraction

## Technical Implementation

### Async Analysis Features

- **ComprehensiveCache**: Multi-level caching system
- **Background Analysis**: Async warming of cache
- **Thread Pool Execution**: Parallel processing capability
- **Memory Optimization**: Efficient sample storage

### Sync Analysis Features

- **Direct Processing**: No caching overhead
- **Minimal Memory**: Lower memory footprint
- **Legacy Compatibility**: Works with older ROS bag formats
- **Simple Error Handling**: Straightforward error management

## File Structure

```
tests/benchmark/
├── test_async_vs_sync_performance.py  # Main benchmark implementation
├── README.md                          # This file
└── results/                           # Benchmark results (generated)
    ├── benchmark_results.json         # Detailed results
    └── performance_summary.html       # Visual results (optional)
```

## Requirements

- Python 3.7+
- rosbags library
- rich library for terminal output
- psutil for memory monitoring
- asyncio for async functionality

## Contributing

When adding new benchmark tests:

1. Follow the existing `BenchmarkResult` structure
2. Add proper error handling
3. Include memory monitoring
4. Update this README with new test descriptions
5. Ensure compatibility with both async and sync modes 