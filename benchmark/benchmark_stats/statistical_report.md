# Benchmark Statistical Report

- Input Bag: `../demo4.bag`
- Number of Runs: 20
- Date: 2025-02-09 15:10:24

## Statistical Results

### PYTHON Implementation
#### Processing Time
- Mean Time: 2.22 seconds
- Standard Deviation: 0.26 seconds
- Minimum Time: 1.76 seconds
- Maximum Time: 2.76 seconds
- Median Time: 2.11 seconds

#### Throughput
- Mean Throughput: 2456.49 messages/second
- Standard Deviation: 271.32 messages/second
- Minimum Throughput: 1949.97 messages/second
- Maximum Throughput: 3058.66 messages/second
- Median Throughput: 2551.36 messages/second

### ROS_CLI Implementation
#### Processing Time
- Mean Time: 2.71 seconds
- Standard Deviation: 0.40 seconds
- Minimum Time: 2.15 seconds
- Maximum Time: 3.57 seconds
- Median Time: 2.61 seconds

#### Throughput
- Mean Throughput: 2034.62 messages/second
- Standard Deviation: 293.16 messages/second
- Minimum Throughput: 1508.29 messages/second
- Maximum Throughput: 2501.67 messages/second
- Median Throughput: 2064.11 messages/second

### CPP Implementation
#### Processing Time
- Mean Time: 1.95 seconds
- Standard Deviation: 0.25 seconds
- Minimum Time: 1.46 seconds
- Maximum Time: 2.37 seconds
- Median Time: 1.96 seconds

#### Throughput
- Mean Throughput: 2821.41 messages/second
- Standard Deviation: 392.08 messages/second
- Minimum Throughput: 2277.80 messages/second
- Maximum Throughput: 3702.81 messages/second
- Median Throughput: 2753.34 messages/second

## Performance Comparisons
- Average Speedup (C++ vs Python): 1.14x
- Average Speedup (C++ vs ROS CLI): 1.39x
- Average Speedup (ROS CLI vs Python): 0.82x
