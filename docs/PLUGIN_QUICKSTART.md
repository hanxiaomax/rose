# Rose 插件系统快速入门

## 5分钟上手插件开发

Rose 支持两种插件类型：**钩子插件**（自动执行）和**脚本插件**（手动执行）。

### 第1步：选择插件类型并创建

#### 创建钩子插件（自动执行）
```bash
# 创建基础钩子插件
rose plugin create hello_hook --template basic
```

#### 创建脚本插件（手动执行）
```bash
# 创建基础脚本插件
rose plugin create hello_script --template script_basic
```

插件将创建在 `~/.rose/cache/plugins/` 目录下。

### 第2步：查看和测试插件

```bash
# 查看所有插件列表
rose plugin list

# 按类型查看插件
rose plugin list --type hook      # 只显示钩子插件
rose plugin list --type script    # 只显示脚本插件

# 查看插件详细信息
rose plugin info hello_hook
rose plugin info hello_script
```

#### 测试钩子插件
```bash
# 钩子插件会在 load 操作时自动执行
rose load demo.bag --verbose
```

#### 测试脚本插件
```bash
# 脚本插件需要手动执行
rose plugin run hello_script --bag demo.bag
```

### 第3步：自定义插件功能

#### 自定义钩子插件

编辑钩子插件文件 `~/.rose/cache/plugins/hello_hook.py`：

```python
def initialize(self) -> bool:
    """初始化插件"""
    print(f"正在初始化 {self.plugin_info.name} 插件...")
    
    # 注册钩子 - 在加载 bag 后自动执行
    self.register_hook(HookType.AFTER_LOAD, self.on_bag_loaded)
    
    return True

def on_bag_loaded(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """当 bag 加载完成后自动调用"""
    bag_path = context.get('bag_path')
    
    # 获取数据接口
    data_interface = self.get_data_interface()
    
    # 获取 bag 统计信息
    stats = data_interface.get_bag_statistics(bag_path)
    
    print(f"🎉 {self.plugin_info.name}: 检测到新的 bag 文件!")
    print(f"   文件: {bag_path}")
    print(f"   主题数: {stats.get('topics_count', 0)}")
    print(f"   消息数: {stats.get('total_messages', 0)}")
    
    return context
```

#### 自定义脚本插件

编辑脚本插件文件 `~/.rose/cache/plugins/hello_script.py`：

```python
def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
    """脚本主执行函数"""
    context.print(f"[green]Hello from {self.plugin_info.name}![/green]")
    
    # 获取 bag 文件路径
    bag_path = args.get('bag_path')
    if not bag_path:
        context.print("[yellow]使用方法: --bag path/to/file.bag[/yellow]")
        return True
    
    # 加载 bag 文件
    if context.load_bag(bag_path):
        topics = context.get_topics()
        context.print(f"[cyan]发现 {len(topics)} 个主题[/cyan]")
        
        # 显示前5个主题
        for i, topic in enumerate(topics[:5], 1):
            context.print(f"  {i}. {topic}")
        
        # 用户交互
        if context.confirm("是否显示详细统计?"):
            bag_info = context.get_bag_info()
            context.print(f"文件大小: {bag_info.file_size_mb:.1f} MB")
            context.print(f"持续时间: {bag_info.duration_seconds:.1f} 秒")
    
    return True
```

### 第4步：重新加载并测试

```bash
# 重新加载插件
rose plugin reload hello_hook
rose plugin reload hello_script
```

#### 测试钩子插件
```bash
# 钩子插件会在加载时自动执行
rose load demo.bag --verbose
```

#### 测试脚本插件
```bash
# 脚本插件需要手动执行
rose plugin run hello_script --bag demo.bag
```

现在你有了两种不同的插件：钩子插件会在每次加载 bag 文件时自动运行，脚本插件可以按需执行！

## 常用插件模式

### 钩子插件模式

#### 数据分析钩子插件

```python
class DataAnalyzerPlugin(BasePlugin):
    def analyze_gps_data(self, context: Dict[str, Any]) -> bool:
        """分析 GPS 数据"""
        bag_path = context.get('bag_path')
        console = context.get('console')
        
        data_interface = self.get_data_interface()
        
        # 获取 GPS 主题数据
        gps_topics = data_interface.filter_topics(bag_path, ['gps'])
        
        for topic in gps_topics:
            df = data_interface.get_dataframe(bag_path, topic)
            if df is not None and 'latitude' in df.columns:
                # 分析 GPS 数据质量
                lat_range = df['latitude'].max() - df['latitude'].min()
                lon_range = df['longitude'].max() - df['longitude'].min()
                
                if console:
                    console.print(f"[cyan]{topic} GPS 分析:[/cyan]")
                    console.print(f"  纬度范围: {lat_range:.6f}°")
                    console.print(f"  经度范围: {lon_range:.6f}°")
                    console.print(f"  数据点数: {len(df)}")
        
        return True
```

### 脚本插件模式

#### 交互式数据分析脚本

```python
class InteractiveAnalyzerScript(BaseScriptPlugin):
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        """交互式数据分析"""
        bag_path = args.get('bag_path')
        if not bag_path or not context.load_bag(bag_path):
            return False
        
        # 交互式主题选择
        topics = context.get_topics()
        context.print(f"[green]发现 {len(topics)} 个主题[/green]")
        
        # 显示主题列表
        for i, topic in enumerate(topics, 1):
            context.print(f"  {i:2d}. {topic}")
        
        # 用户选择
        selection = context.ask_user("选择主题编号 (逗号分隔)", "1")
        
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected_topics = [topics[i] for i in indices if 0 <= i < len(topics)]
            
            # 分析选中的主题
            results = []
            for topic in selected_topics:
                df = context.get_dataframe(topic)
                if df is not None:
                    result = {
                        'topic': topic,
                        'messages': len(df),
                        'columns': len(df.columns),
                        'numeric_cols': len(df.select_dtypes(include=['number']).columns)
                    }
                    results.append(result)
            
            # 显示结果表格
            context.print_table(results, "分析结果")
            
            # 询问是否导出
            if context.confirm("是否导出结果?"):
                output = args.get('output', 'analysis_results.json')
                import json
                with open(output, 'w') as f:
                    json.dump(results, f, indent=2)
                context.print(f"[green]结果已导出到 {output}[/green]")
            
        except (ValueError, IndexError):
            context.print("[red]无效的选择[/red]")
            return False
        
        return True
```

#### 批处理脚本插件

```python
class BatchProcessorScript(BaseScriptPlugin):
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        """批处理多个主题"""
        bag_path = args.get('bag_path')
        topics = args.get('topics', [])
        output_dir = args.get('output', 'batch_output')
        
        if not context.load_bag(bag_path):
            return False
        
        # 如果没有指定主题，获取所有数值主题
        if not topics:
            all_topics = context.get_topics()
            topics = []
            
            for topic in all_topics:
                df = context.get_dataframe(topic)
                if df is not None and len(df.select_dtypes(include=['number']).columns) > 0:
                    topics.append(topic)
        
        context.print(f"[cyan]批处理 {len(topics)} 个主题[/cyan]")
        
        # 创建输出目录
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # 批处理每个主题
        for i, topic in enumerate(topics, 1):
            context.print(f"[yellow]处理 {i}/{len(topics)}: {topic}[/yellow]")
            
            df = context.get_dataframe(topic)
            if df is not None:
                # 导出为 CSV
                filename = f"{topic.replace('/', '_')}.csv"
                output_path = os.path.join(output_dir, filename)
                
                if context.export_csv(df, output_path):
                    context.print(f"  ✓ 已导出到 {output_path}")
                else:
                    context.print(f"  ✗ 导出失败: {topic}")
        
        context.print(f"[green]批处理完成! 输出目录: {output_dir}[/green]")
        return True
```

### 自动化插件

```python
class AutoProcessPlugin(BasePlugin):
    def initialize(self) -> bool:
        # 在每次导出后自动执行后处理
        self.register_hook(HookType.AFTER_EXPORT, self.post_process)
        return True
    
    def post_process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """导出后自动处理"""
        output_path = context.get('output_path')
        success = context.get('success', False)
        
        if success and output_path:
            # 自动压缩导出的文件
            import gzip
            import shutil
            
            with open(output_path, 'rb') as f_in:
                with gzip.open(f"{output_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            print(f"✨ 自动压缩完成: {output_path}.gz")
        
        return context
```

## 进阶技巧

### 1. 插件间通信

```python
def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    # 从其他插件获取数据
    other_plugin_data = context.get('other_plugin_result')
    
    # 为其他插件提供数据
    context['my_plugin_data'] = self.process_data()
    
    return context
```

### 2. 条件执行

```python
def conditional_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    # 只在特定条件下执行
    bag_path = context.get('bag_path')
    
    if bag_path and 'gps' in str(bag_path):
        # 只处理包含 'gps' 的 bag 文件
        self.process_gps_bag(context)
    
    return context
```

### 3. 配置管理

```python
class ConfigurablePlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载插件配置"""
        config_file = Path.home() / '.rose' / 'config' / f'{self.plugin_info.name}.json'
        
        if config_file.exists():
            import json
            with open(config_file) as f:
                return json.load(f)
        
        # 默认配置
        return {
            'auto_export': True,
            'output_format': 'csv',
            'compression': True
        }
```

开始创建你的插件吧！🚀
