"""
Export Manager - Handles result export to various formats (JSON, YAML, CSV, XML, HTML, Markdown)
Provides unified export functionality for analysis and extraction results
"""

import json
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from rich.console import Console
from rich.markdown import Markdown

from .util import get_logger

_logger = get_logger("export_manager")


class OutputFormat(Enum):
    """Supported output formats"""
    TABLE = "table"
    LIST = "list"
    SUMMARY = "summary"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"
    XML = "xml"
    HTML = "html"
    MARKDOWN = "markdown"


@dataclass
class RenderOptions:
    """Options for result rendering"""
    format: OutputFormat = OutputFormat.TABLE
    verbose: bool = False
    show_fields: bool = False
    show_cache_stats: bool = True
    show_summary: bool = True
    color: bool = True
    width: Optional[int] = None
    title: Optional[str] = None


@dataclass
class ExportOptions:
    """Options for result export"""
    format: OutputFormat = OutputFormat.JSON
    output_file: Optional[Path] = None
    pretty: bool = True
    include_metadata: bool = True
    compress: bool = False


class ExportManager:
    """
    Export Manager for handling result export to various formats
    
    Provides methods for:
    - JSON export with pretty printing
    - YAML export with proper formatting
    - CSV export for tabular data
    - XML export with structured data
    - HTML export with styled tables
    - Markdown export for documentation
    """
    
    @classmethod
    def export_result(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """
        Export result to file in specified format
        
        Args:
            result: Analysis result from BagManager
            options: Export options
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            if options.format == OutputFormat.JSON:
                return cls._export_json(result, options)
            elif options.format == OutputFormat.YAML:
                return cls._export_yaml(result, options)
            elif options.format == OutputFormat.CSV:
                return cls._export_csv(result, options)
            elif options.format == OutputFormat.XML:
                return cls._export_xml(result, options)
            elif options.format == OutputFormat.HTML:
                return cls._export_html(result, options)
            elif options.format == OutputFormat.MARKDOWN:
                return cls._export_markdown(result, options)
            else:
                _logger.error(f"Unsupported export format: {options.format}")
                return False
        except Exception as e:
            _logger.error(f"Export failed: {e}")
            return False
    
    @classmethod
    def render_result(cls, result: Dict[str, Any], options: Optional[RenderOptions] = None,
                     console: Optional[Console] = None) -> str:
        """
        Render result in specified format for console output
        
        Args:
            result: Analysis result from BagManager or extraction result
            options: Rendering options
            console: Console instance
            
        Returns:
            Rendered string (for non-console formats)
        """
        if console is None:
            console = Console()
        if options is None:
            options = RenderOptions()
        
        # Check if this is an extraction result
        if result.get('operation') == 'extract_topics':
            return cls._render_extraction_result(result, options, console)
        
        # Route to appropriate renderer for inspection results
        if options.format == OutputFormat.JSON:
            return cls._render_json(result, options, console)
        elif options.format == OutputFormat.YAML:
            return cls._render_yaml(result, options, console)
        elif options.format == OutputFormat.MARKDOWN:
            return cls._render_markdown(result, options, console)
        else:
            _logger.warning(f"Unsupported render format: {options.format}")
            return ""  # Return empty string for unsupported formats
    
    # ========================================================================
    # Private Export Methods
    # ========================================================================
    
    @classmethod
    def _export_json(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as JSON file"""
        if options.output_file is None:
            return False
            
        json_result = cls._prepare_serializable_result(result)
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            json.dump(
                json_result, 
                f, 
                indent=2 if options.pretty else None, 
                ensure_ascii=False,
                default=str
            )
        
        _logger.info(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_yaml(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as YAML file"""
        if not YAML_AVAILABLE:
            _logger.error("YAML library not available")
            return False
            
        if options.output_file is None:
            return False
        
        yaml_result = cls._prepare_serializable_result(result)
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                yaml_result, 
                f, 
                default_flow_style=False, 
                indent=2,
                allow_unicode=True
            )
        
        _logger.info(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_csv(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as CSV file"""
        if options.output_file is None:
            return False
            
        topics = result.get('topics', [])
        
        with open(options.output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['topic', 'message_type', 'message_count', 'frequency']
            if any('field_paths' in topic for topic in topics):
                fieldnames.append('field_count')
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for topic_info in topics:
                row = {
                    'topic': topic_info.get('name', ''),
                    'message_type': topic_info.get('message_type', ''),
                    'message_count': topic_info.get('message_count', 0),
                    'frequency': topic_info.get('frequency', 0)
                }
                
                if 'field_count' in fieldnames:
                    row['field_count'] = len(topic_info.get('field_paths', []))
                
                writer.writerow(row)
        
        _logger.info(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_xml(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as XML file"""
        if options.output_file is None:
            return False
            
        root = ET.Element("bag_analysis")
        
        # Add bag info
        bag_info_elem = ET.SubElement(root, "bag_info")
        for key, value in result.get('bag_info', {}).items():
            elem = ET.SubElement(bag_info_elem, key)
            elem.text = str(value)
        
        # Add topics
        topics_elem = ET.SubElement(root, "topics")
        for topic_info in result.get('topics', []):
            topic_elem = ET.SubElement(topics_elem, "topic")
            for key, value in topic_info.items():
                if key == 'field_paths':
                    fields_elem = ET.SubElement(topic_elem, "field_paths")
                    for field in value:
                        field_elem = ET.SubElement(fields_elem, "field")
                        field_elem.text = field
                else:
                    elem = ET.SubElement(topic_elem, key)
                    elem.text = str(value)
        
        # Write to file
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)  # Pretty print
        tree.write(options.output_file, encoding='utf-8', xml_declaration=True)
        
        _logger.info(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_html(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as HTML file"""
        if options.output_file is None:
            return False
            
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ROS Bag Analysis Report - {bag_info.get('file_name', 'Unknown')}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 2rem; }}
        .header {{ border-bottom: 2px solid #007acc; padding-bottom: 1rem; margin-bottom: 2rem; }}
        .summary {{ margin-bottom: 2rem; background: #f8f9fa; padding: 1rem; border-radius: 5px; }}
        .topics {{ margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #007acc; color: white; font-weight: 600; }}
        .topic {{ font-family: monospace; }}
        .count {{ text-align: right; }}
        .frequency {{ text-align: right; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ROS Bag Analysis Report</h1>
        <p>{bag_info.get('file_name', 'Unknown')} • Generated at {cls._get_timestamp()}</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Topics:</strong> {bag_info.get('topics_count', 0)}</p>
        <p><strong>Messages:</strong> {bag_info.get('total_messages', 0):,}</p>
        <p><strong>File Size:</strong> {cls._format_size(bag_info.get('file_size', 0))}</p>
        <p><strong>Duration:</strong> {bag_info.get('duration_seconds', 0):.1f}s</p>
        <p><strong>Analysis Time:</strong> {bag_info.get('analysis_time', 0):.3f}s</p>
        <p><strong>Cached:</strong> {'Yes' if bag_info.get('cached', False) else 'No'}</p>
    </div>
    
    <div class="topics">
        <h2>Topics ({len(topics)})</h2>
        <table>
            <thead>
                <tr>
                    <th>Topic</th>
                    <th>Message Type</th>
                    <th>Count</th>
                    <th>Frequency</th>
                </tr>
            </thead>
            <tbody>"""
        
        for topic_info in topics:
            html_content += f"""
                <tr>
                    <td class="topic">{topic_info.get('name', '')}</td>
                    <td>{topic_info.get('message_type', '')}</td>
                    <td class="count">{topic_info.get('message_count', 0):,}</td>
                    <td class="frequency">{topic_info.get('frequency', 0):.1f} Hz</td>
                </tr>"""
        
        html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>"""
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        _logger.info(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_markdown(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as Markdown file"""
        if options.output_file is None:
            return False
            
        md_content = cls._render_markdown(result, RenderOptions(show_fields=True), Console())
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        _logger.info(f"Results exported to {options.output_file}")
        return True
    
    # ========================================================================
    # Private Render Methods
    # ========================================================================
    
    @classmethod
    def _render_json(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as JSON"""
        json_result = cls._prepare_serializable_result(result)
        json_str = json.dumps(json_result, indent=2 if options.verbose else None, default=str)
        
        if options.color:
            console.print_json(data=json_result)
        else:
            console.print(json_str)
        
        return json_str
    
    @classmethod
    def _render_yaml(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as YAML"""
        if not YAML_AVAILABLE:
            console.print("[red]YAML library not available. Install with: pip install pyyaml[/red]")
            return ""
        
        yaml_result = cls._prepare_serializable_result(result)
        yaml_str = yaml.dump(yaml_result, default_flow_style=False, indent=2)
        
        console.print(f"```yaml\n{yaml_str}```")
        return yaml_str
    
    @classmethod
    def _render_markdown(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as Markdown"""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        md_content = f"""# Bag Analysis Report

## Summary
- **File**: {bag_info.get('file_name', 'Unknown')}
- **Topics**: {bag_info.get('topics_count', 0)}
- **Messages**: {bag_info.get('total_messages', 0):,}
- **Duration**: {bag_info.get('duration_seconds', 0):.1f}s
- **File Size**: {cls._format_size(bag_info.get('file_size', 0))}

## Topics

| Topic | Message Type | Count | Frequency |
|-------|--------------|-------|-----------|
"""
        
        for topic_info in topics:
            name = topic_info.get('name', '')
            msg_type = topic_info.get('message_type', '')
            count = topic_info.get('message_count', 0)
            frequency = topic_info.get('frequency', 0)
            
            md_content += f"| `{name}` | {msg_type} | {count:,} | {frequency:.1f} Hz |\n"
        
        markdown = Markdown(md_content)
        console.print(markdown)
        
        return md_content
    
    @classmethod
    def _render_extraction_result(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render extraction result in specified format"""
        if options.format == OutputFormat.JSON:
            return cls._render_json(result, options, console)
        elif options.format == OutputFormat.YAML:
            return cls._render_yaml(result, options, console)
        elif options.format == OutputFormat.MARKDOWN:
            return cls._render_extraction_markdown(result, options, console)
        else:
            return ""  # Return empty string for unsupported formats
    
    @classmethod
    def _render_extraction_markdown(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render extraction result as Markdown"""
        stats = result.get('statistics', {})
        bag_info = result.get('bag_info', {})
        
        md_content = f"""# ROS Bag Extraction Report

## Operation Summary
- **Input File**: {result.get('input_file', 'Unknown')}
- **Output File**: {result.get('output_file', 'Unknown')}
- **Compression**: {result.get('compression', 'none')}
- **Operation**: {'Dry Run' if result.get('dry_run') else 'Extraction'}
- **Status**: {'Success' if result.get('success') else 'Failed'}

## Statistics
- **Topics**: {stats.get('selected_topics', 0)} / {stats.get('total_topics', 0)} ({stats.get('selection_percentage', 0):.1f}%)
- **Messages**: {stats.get('selected_messages', 0):,} / {stats.get('total_messages', 0):,} ({stats.get('message_percentage', 0):.1f}%)
- **Duration**: {bag_info.get('duration_seconds', 0):.1f}s

## Selected Topics

| Topic | Message Count | Status |
|-------|---------------|--------|
"""
        
        topics_to_extract = result.get('topics_to_extract', [])
        for topic in result.get('all_topics', []):
            topic_name = topic['name']
            count = topic['message_count']
            status = "✓ Keep" if topic_name in topics_to_extract else "✗ Drop"
            md_content += f"| `{topic_name}` | {count:,} | {status} |\n"
        
        if result.get('performance'):
            perf = result['performance']
            md_content += f"""
## Performance
- **Extraction Time**: {perf.get('extraction_time', 0):.3f}s
- **Processing Rate**: {perf.get('messages_per_sec', 0):.0f} messages/sec
- **Analysis Time**: {perf.get('analysis_time', 0):.3f}s
- **Total Time**: {perf.get('total_time', 0):.3f}s
"""
        
        markdown = Markdown(md_content)
        console.print(markdown)
        
        return md_content
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    @classmethod
    def _prepare_serializable_result(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare result for JSON/YAML serialization"""
        def make_serializable(obj):
            if isinstance(obj, dict):
                return {key: make_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(item) for item in obj]
            elif isinstance(obj, Path):
                return str(obj)
            elif hasattr(obj, '__dict__'):
                return make_serializable(obj.__dict__)
            else:
                return obj
        
        return make_serializable(result)
    
    @classmethod
    def _format_size(cls, size_bytes: int) -> str:
        """Format file size in human readable format"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    @classmethod
    def _get_timestamp(cls) -> str:
        """Get current timestamp for reports"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')