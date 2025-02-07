# Rosbag Benchmark Report

## Bag Information
- File: `../demo3.bag`
- Size: 696.15 MB
- Duration: 20.00 seconds
- Total Messages: 5390
- Topics: /diagnostics, /diagnostics_agg, /diagnostics_toplevel_state, /gps/fix, /gps/rtkfix, /gps/time, /image_raw, /obs1/gps/fix, /obs1/gps/rtkfix, /obs1/gps/time, /radar/points, /radar/range, /radar/tracks, /tf, /velodyne_nodelet_manager/bond, /velodyne_packets, /velodyne_points

## Benchmark Results

### Python Lib:Rosbag
- Processing Time: 3.52 seconds
- Messages Processed: 5390
- Throughput: 1530.40 messages/second
- Output File: `../demo3_py_output.bag`

### Our C++ Interface
- Processing Time: 1.52 seconds
- Messages Processed: 5390
- Throughput: 3543.30 messages/second
- Output File: `../demo3_cpp_output.bag`

### Performance Comparison
- Speedup (C++ vs Python): 2.32x