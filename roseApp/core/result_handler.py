"""
Result Handler - Universal renderer and exporter for bag analysis results
Provides unified interface for displaying and exporting results in multiple formats
"""
import json
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from io import StringIO
import logging

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich.markdown import Markdown


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
    output_file: Path = None
    pretty: bool = True
    include_metadata: bool = True
    compress: bool = False


class ResultHandler:
    """
    Universal result handler for bag analysis results
    
    Provides unified interface for:
    - Rendering results in various formats (table, list, summary, etc.)
    - Exporting results to files (JSON, YAML, CSV, XML, HTML, etc.)
    - Format conversion between different output types
    
    Example usage:
        handler = ResultHandler()
        handler.render(result, RenderOptions(format=OutputFormat.TABLE))
        handler.export(result, ExportOptions(format=OutputFormat.JSON, output_file=Path("report.json")))
    """
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize result handler"""
        self.console = console or Console()
        self.logger = logging.getLogger(__name__)
    
    def render(self, result: Dict[str, Any], options: RenderOptions = None) -> str:
        """
        Render result in specified format
        
        Args:
            result: Analysis result from BagManager or extraction result
            options: Rendering options
            
        Returns:
            Rendered string (for non-console formats)
        """
        if options is None:
            options = RenderOptions()
        
        # Check if this is an extraction result
        if result.get('operation') == 'extract_topics':
            return self._render_extraction_result(result, options)
        
        # Route to appropriate renderer for inspection results
        if options.format == OutputFormat.TABLE:
            return self._render_table(result, options)
        elif options.format == OutputFormat.LIST:
            return self._render_list(result, options)
        elif options.format == OutputFormat.SUMMARY:
            return self._render_summary(result, options)
        elif options.format == OutputFormat.JSON:
            return self._render_json(result, options)
        elif options.format == OutputFormat.YAML:
            return self._render_yaml(result, options)
        elif options.format == OutputFormat.MARKDOWN:
            return self._render_markdown(result, options)
        else:
            self.logger.warning(f"Unsupported render format: {options.format}")
            return self._render_table(result, options)  # Fallback to table
    
    def export(self, result: Dict[str, Any], options: ExportOptions) -> bool:
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
                return self._export_json(result, options)
            elif options.format == OutputFormat.YAML:
                return self._export_yaml(result, options)
            elif options.format == OutputFormat.CSV:
                return self._export_csv(result, options)
            elif options.format == OutputFormat.XML:
                return self._export_xml(result, options)
            elif options.format == OutputFormat.HTML:
                return self._export_html(result, options)
            elif options.format == OutputFormat.MARKDOWN:
                return self._export_markdown(result, options)
            else:
                self.logger.error(f"Unsupported export format: {options.format}")
                return False
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return False
    
    def convert_format(
        self, 
        result: Dict[str, Any], 
        from_format: OutputFormat, 
        to_format: OutputFormat
    ) -> str:
        """
        Convert result from one format to another
        
        Args:
            result: Analysis result
            from_format: Source format (currently unused, result is always dict)
            to_format: Target format
            
        Returns:
            Converted result as string
        """
        options = RenderOptions(format=to_format)
        return self.render(result, options)
    
    # Table rendering
    def _render_table(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render result as rich table"""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        # Show summary if requested
        if options.show_summary:
            self._display_summary(bag_info, options)
        
        # Create topics table
        table = Table(
            title=options.title or f"Topics in {bag_info.get('file_name', 'Unknown')}",
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("Topic", style="cyan", no_wrap=True)
        table.add_column("Message Type", style="magenta")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Frequency", justify="right", style="blue")
        
        if options.show_fields:
            table.add_column("Fields", style="yellow")
        
        # Add topic rows
        for topic_info in topics:
            frequency_str = f"{topic_info.get('frequency', 0):.1f} Hz"
            row = [
                topic_info.get('name', ''),
                topic_info.get('message_type', ''),
                f"{topic_info.get('message_count', 0):,}",
                frequency_str
            ]
            
            if options.show_fields and 'field_paths' in topic_info:
                fields_count = len(topic_info['field_paths'])
                row.append(f"{fields_count} fields")
            elif options.show_fields:
                row.append("N/A")
            
            table.add_row(*row)
        
        self.console.print(table)
        
        # Show field analysis if available
        if options.show_fields and result.get('field_analysis'):
            self._display_field_analysis(result['field_analysis'])
        
        # Show cache stats if requested
        if options.show_cache_stats and result.get('cache_stats'):
            self._display_cache_stats(result['cache_stats'])
        
        return ""  # Console output, no string return
    
    def _render_list(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render result as list format"""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        if options.show_summary:
            self._display_summary(bag_info, options)
        
        self.console.print()
        
        for topic_info in topics:
            name = topic_info.get('name', '')
            count = topic_info.get('message_count', 0)
            frequency = topic_info.get('frequency', 0)
            
            parts = [f"[bold]{name}[/bold]"]
            parts.append(f"[green]{count:,} msgs[/green]")
            
            if frequency > 0:
                parts.append(f"[blue]{frequency:.1f} Hz[/blue]")
            
            self.console.print(" | ".join(parts))
        
        return ""
    
    def _render_summary(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render result as summary only"""
        bag_info = result.get('bag_info', {})
        self._display_summary(bag_info, options)
        return ""
    
    def _render_json(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render result as JSON"""
        json_result = self._prepare_serializable_result(result)
        json_str = json.dumps(json_result, indent=2 if options.verbose else None, default=str)
        
        if options.color:
            self.console.print_json(data=json_result)
        else:
            self.console.print(json_str)
        
        return json_str
    
    def _render_yaml(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render result as YAML"""
        if not YAML_AVAILABLE:
            self.console.print("[red]YAML library not available. Install with: pip install pyyaml[/red]")
            return ""
        
        yaml_result = self._prepare_serializable_result(result)
        yaml_str = yaml.dump(yaml_result, default_flow_style=False, indent=2)
        
        self.console.print(f"```yaml\n{yaml_str}```")
        return yaml_str
    
    def _render_markdown(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render result as Markdown"""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        md_content = f"""# Bag Analysis Report

## Summary
- **File**: {bag_info.get('file_name', 'Unknown')}
- **Topics**: {bag_info.get('topics_count', 0)}
- **Messages**: {bag_info.get('total_messages', 0):,}
- **Duration**: {bag_info.get('duration_seconds', 0):.1f}s
- **File Size**: {self._format_size(bag_info.get('file_size', 0))}

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
        
        if options.show_fields and result.get('field_analysis'):
            md_content += "\n## Field Analysis\n\n"
            for topic, analysis in result['field_analysis'].items():
                md_content += f"### {topic}\n\n"
                md_content += f"**Message Type**: {analysis.get('message_type', 'Unknown')}\n\n"
                md_content += f"**Fields** ({len(analysis.get('field_paths', []))}):\n\n"
                for field in analysis.get('field_paths', []):
                    md_content += f"- `{field}`\n"
                md_content += "\n"
        
        markdown = Markdown(md_content)
        self.console.print(markdown)
        
        return md_content
    
    def _render_extraction_result(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render extraction result in specified format"""
        if options.format == OutputFormat.SUMMARY:
            return self._render_extraction_summary(result, options)
        elif options.format == OutputFormat.TABLE:
            return self._render_extraction_table(result, options)
        elif options.format == OutputFormat.LIST:
            return self._render_extraction_list(result, options)
        elif options.format == OutputFormat.JSON:
            return self._render_json(result, options)
        elif options.format == OutputFormat.YAML:
            return self._render_yaml(result, options)
        elif options.format == OutputFormat.MARKDOWN:
            return self._render_extraction_markdown(result, options)
        else:
            return self._render_extraction_summary(result, options)  # Fallback
    
    def _render_extraction_summary(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render extraction result as summary panel"""
        
        # Create summary text
        summary_text = Text()
        
        # File information
        summary_text.append("File Information:\n", style="bold cyan")
        summary_text.append(f"  Input:  {result.get('input_file', 'Unknown')}\n", style="green")
        summary_text.append(f"  Output: {result.get('output_file', 'Unknown')}\n", style="blue")
        summary_text.append(f"  Compression: {result.get('compression', 'none')}\n")
        
        # Statistics
        stats = result.get('statistics', {})
        bag_info = result.get('bag_info', {})
        
        summary_text.append("\nStatistics:\n", style="bold cyan")
        
        if result.get('success') and not result.get('dry_run'):
            # Show actual results with before → after format
            summary_text.append(f"  Topics: {stats.get('total_topics', 0)} → {stats.get('selected_topics', 0)} ({stats.get('selection_percentage', 0):.1f}%)\n")
            summary_text.append(f"  Messages: {stats.get('total_messages', 0):,} → {stats.get('selected_messages', 0):,} ({stats.get('message_percentage', 0):.1f}%)\n")
            
            # Add file size info if available
            file_stats = result.get('file_stats', {})
            if file_stats:
                input_size = file_stats.get('input_size_bytes', 0) / 1024 / 1024
                output_size = file_stats.get('output_size_bytes', 0) / 1024 / 1024
                size_reduction = file_stats.get('size_reduction_percent', 0)
                summary_text.append(f"  Size: {input_size:.1f} MB → {output_size:.1f} MB ({100 - size_reduction:.1f}%)\n")
        else:
            # Show preview/estimation format
            summary_text.append(f"  Topics: {stats.get('total_topics', 0)} total, {stats.get('selected_topics', 0)} selected ({stats.get('selection_percentage', 0):.1f}%)\n")
            summary_text.append(f"  Messages: {stats.get('total_messages', 0):,} total, {stats.get('selected_messages', 0):,} selected ({stats.get('message_percentage', 0):.1f}%)\n")
        
        duration = bag_info.get('duration_seconds', 0)
        if duration > 0:
            summary_text.append(f"  Duration: {duration:.1f}s\n")
        
        # Performance information
        if result.get('performance'):
            perf = result['performance']
            summary_text.append("\nPerformance:\n", style="bold cyan")
            summary_text.append(f"  Extraction Time: {perf.get('extraction_time', 0):.3f}s\n")
            if perf.get('messages_per_sec', 0) > 0:
                summary_text.append(f"  Processing Rate: {perf.get('messages_per_sec', 0):.0f} messages/sec\n")
        
        # Add verbose information if requested
        if options.verbose:
            cache_stats = result.get('cache_stats', {})
            analysis_time = bag_info.get('analysis_time', 0)
            cached = bag_info.get('cached', False)
            
            summary_text.append("\nDetailed Information:\n", style="bold cyan")
            summary_text.append(f"  Analysis Time: {analysis_time:.3f}s\n")
            summary_text.append(f"  Cached Result: {'Yes' if cached else 'No'}\n")
            summary_text.append(f"  Parser: rosbags (high-performance)\n")
            
            if cache_stats:
                hit_rate = cache_stats.get('hit_rate', 0) * 100
                summary_text.append(f"  Cache Hit Rate: {hit_rate:.1f}%\n")
            
            if result.get('performance'):
                perf = result['performance']
                if perf.get('total_time', 0) > 0:
                    efficiency = (analysis_time / perf['total_time']) * 100
                    summary_text.append(f"  Total Time: {perf.get('total_time', 0):.3f}s\n")
                    summary_text.append(f"  Analysis Efficiency: {efficiency:.1f}%\n")
        
        # Add topics overview
        summary_text.append("\nTopics Overview:\n", style="bold cyan")
        summary_text.append(f"  Keeping {stats.get('selected_topics', 0)}, Excluding {stats.get('excluded_topics', 0)}\n")
        
        # Add topics table
        summary_text.append("\n")
        
        # Create topics table with full width
        table = Table(show_header=True, header_style="bold magenta", box=None, expand=True)
        table.add_column("Status", style="bold", width=8, justify="center")
        table.add_column("Topic", style="cyan")  # Remove width constraints to allow expansion
        table.add_column("Count", style="yellow", justify="right", width=10)
        table.add_column("Size Est.", style="green", justify="right", width=12)
        
        topics_to_extract = result.get('topics_to_extract', [])
        
        for topic in result.get('all_topics', []):
            topic_name = topic['name']
            message_count = topic['message_count']
            size_estimate = topic.get('estimated_size_bytes', 0)
            
            should_keep = topic_name in topics_to_extract
            
            if should_keep:
                status = "●"
                status_style = "green"
            else:
                status = "○"
                status_style = "red dim"
                topic_name = f"[dim]{topic_name}[/dim]"
            
            # Format size
            if size_estimate > 1024 * 1024:
                size_str = f"{size_estimate / 1024 / 1024:.1f}MB"
            elif size_estimate > 1024:
                size_str = f"{size_estimate / 1024:.1f}KB"
            else:
                size_str = f"{size_estimate}B"
            
            table.add_row(
                f"[{status_style}]{status}[/{status_style}]",
                topic_name,
                f"{message_count:,}",
                size_str
            )
        
        # Create legend
        legend_text = Text()
        legend_text.append("● = Keep (included in output)  ", style="green")
        legend_text.append("○ = Drop (excluded from output)", style="red dim")
        
        # Create combined content
        from rich.align import Align
        from rich.console import Group
        
        combined_content = Group(
            summary_text,
            table,  # Remove center alignment to use full width
            "",
            Align.center(legend_text)
        )
        
        # Create panel
        panel_title = "Summary"
        if options.verbose:
            panel_title += " (Verbose)"
        
        panel = Panel(
            combined_content,
            title=panel_title,
            border_style="cyan"
        )
        self.console.print(panel)
        
        return ""
    
    def _render_extraction_table(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render extraction result as table format"""
        # Show summary first
        self._render_extraction_summary(result, options)
        return ""
    
    def _render_extraction_list(self, result: Dict[str, Any], options: RenderOptions) -> str:
        """Render extraction result as list format"""
        stats = result.get('statistics', {})
        
        self.console.print(f"\n[bold]Extraction Operation[/bold]")
        self.console.print(f"Topics: {stats.get('selected_topics', 0)}/{stats.get('total_topics', 0)} selected")
        self.console.print(f"Messages: {stats.get('selected_messages', 0):,}/{stats.get('total_messages', 0):,} selected")
        
        if result.get('topics_to_extract'):
            self.console.print(f"\n[bold]Selected Topics:[/bold]")
            for topic_name in result['topics_to_extract']:
                self.console.print(f"  • [green]{topic_name}[/green]")
        
        return ""
    
    def _render_extraction_markdown(self, result: Dict[str, Any], options: RenderOptions) -> str:
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
        self.console.print(markdown)
        
        return md_content
    
    # Export functions
    def _export_json(self, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as JSON file"""
        json_result = self._prepare_serializable_result(result)
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            json.dump(
                json_result, 
                f, 
                indent=2 if options.pretty else None, 
                ensure_ascii=False,
                default=str
            )
        
        self.console.print(f"Results exported to {options.output_file}")
        return True
    
    def _export_yaml(self, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as YAML file"""
        if not YAML_AVAILABLE:
            self.console.print("[red]YAML library not available[/red]")
            return False
        
        yaml_result = self._prepare_serializable_result(result)
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                yaml_result, 
                f, 
                default_flow_style=False, 
                indent=2,
                allow_unicode=True
            )
        
        self.console.print(f"Results exported to {options.output_file}")
        return True
    
    def _export_csv(self, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as CSV file"""
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
        
        self.console.print(f"Results exported to {options.output_file}")
        return True
    
    def _export_xml(self, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as XML file"""
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
        
        self.console.print(f"Results exported to {options.output_file}")
        return True
    
    def _export_html(self, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as HTML file"""
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
        .field-analysis {{ margin-top: 2rem; }}
        .field-list {{ columns: 2; column-gap: 2rem; }}
        .field-item {{ break-inside: avoid; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ROS Bag Analysis Report</h1>
        <p>{bag_info.get('file_name', 'Unknown')} • Generated at {self._get_timestamp()}</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Topics:</strong> {bag_info.get('topics_count', 0)}</p>
        <p><strong>Messages:</strong> {bag_info.get('total_messages', 0):,}</p>
        <p><strong>File Size:</strong> {self._format_size(bag_info.get('file_size', 0))}</p>
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
    </div>"""
        
        # Add field analysis if available
        if result.get('field_analysis'):
            html_content += """
    <div class="field-analysis">
        <h2>Field Analysis</h2>"""
            
            for topic, analysis in result['field_analysis'].items():
                field_paths = analysis.get('field_paths', [])
                html_content += f"""
        <h3>{topic}</h3>
        <p><strong>Message Type:</strong> {analysis.get('message_type', 'Unknown')}</p>
        <p><strong>Fields:</strong> {len(field_paths)}</p>
        <div class="field-list">"""
                
                for field in field_paths:
                    html_content += f'<div class="field-item">• <code>{field}</code></div>'
                
                html_content += "</div>"
            
            html_content += "</div>"
        
        html_content += """
</body>
</html>"""
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.console.print(f"Results exported to {options.output_file}")
        return True
    
    def _export_markdown(self, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as Markdown file"""
        md_content = self._render_markdown(result, RenderOptions(show_fields=True))
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        self.console.print(f"Results exported to {options.output_file}")
        return True
    
    # Helper functions
    def _display_summary(self, bag_info: Dict[str, Any], options: RenderOptions):
        """Display bag summary information"""
        if options.verbose:
            self.console.print("\n[bold]Bag File Summary[/bold]")
            self.console.print(f"File: {bag_info.get('file_name', 'Unknown')}")
            self.console.print(f"Path: {bag_info.get('file_path', 'Unknown')}")
            self.console.print(f"Analysis Time: {bag_info.get('analysis_time', 0):.3f}s")
            self.console.print(f"Cached: {'Yes' if bag_info.get('cached', False) else 'No'}")
            self.console.print("-" * 60)
        
        self.console.print(f"Topics: {bag_info.get('topics_count', 0)}")
        self.console.print(f"Messages: {bag_info.get('total_messages', 0):,}")
        self.console.print(f"File Size: {self._format_size(bag_info.get('file_size', 0))}")
        self.console.print(f"Duration: {bag_info.get('duration_seconds', 0):.1f}s")
        
        if bag_info.get('total_messages', 0) > 0 and bag_info.get('duration_seconds', 0) > 0:
            avg_rate = bag_info['total_messages'] / bag_info['duration_seconds']
            self.console.print(f"Avg Rate: {avg_rate:.1f} Hz")
        
        self.console.print()
    
    def _display_field_analysis(self, field_analysis: Dict[str, Any]):
        """Display field analysis information"""
        self.console.print()
        for topic, analysis in field_analysis.items():
            self.console.print(f"\n[bold]Fields for {topic}[/bold]")
            self.console.print(f"Message Type: {analysis.get('message_type', 'Unknown')}")
            self.console.print(f"Samples Analyzed: {analysis.get('samples_analyzed', 0)}")
            self.console.print()
            self.console.print("Available Fields:")
            
            for field_path in analysis.get('field_paths', []):
                self.console.print(f"  • {field_path}")
    
    def _display_cache_stats(self, cache_stats: Dict[str, Any]):
        """Display cache performance statistics"""
        if cache_stats.get('total_requests', 0) > 0:
            hit_rate = cache_stats.get('hit_rate', 0) * 100
            total_requests = cache_stats.get('total_requests', 0)
            self.console.print(f"\nCache Performance: {hit_rate:.1f}% hit rate ({total_requests} requests)")
    
    def _prepare_serializable_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
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
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for reports"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S') 