# Rosbag Performance Benchmark

这个目录包含了用于对比Python rosbag和C++ rosbag_io_py实现性能的基准测试工具。

## 依赖项

确保已安装以下Python包：
```bash
pip install rosbag matplotlib pandas tqdm numpy
```

如果要测试C++实现，还需要安装`rosbag_io_py`。

## 使用方法

1. 运行基准测试：
```bash
python rosbag_benchmark.py path/to/your/bagfile.bag [--output results.json]
```

2. 可视化结果：
```bash
python visualize.py results.json [--output-dir benchmark_results]
```

## 输出说明

基准测试会生成以下内容：

1. JSON格式的详细测试结果
2. 使用Python实现处理后的bag文件
3. 使用C++实现处理后的bag文件（如果可用）

可视化脚本会生成：

1. 处理时间对比图表
2. 消息处理吞吐量对比图表
3. 详细的Markdown格式报告

## 示例

```bash
# 运行基准测试
python rosbag_benchmark.py demo.bag

# 可视化结果
python visualize.py benchmark_results.json
```

## 注意事项

1. 确保有足够的磁盘空间，因为会生成与输入大小相当的输出文件
2. 对于大型bag文件，处理可能需要较长时间
3. 如果没有安装`rosbag_io_py`，将只测试Python实现 