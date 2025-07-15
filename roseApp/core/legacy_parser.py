#!/usr/bin/env python3
"""
Legacy parser wrapper with enhanced warnings and diagnostics.

This module provides an isolated wrapper for legacy ROS bag parsers with
prominent warnings about performance implications and clear recommendations.
"""

import os
import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align

from ..core.util import get_logger
from ..core.parser import create_parser, ParserType, IBagParser


class LegacyIssueType(Enum):
    """Types of legacy parser issues"""
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    FEATURES = "features"
    STABILITY = "stability"


@dataclass
class LegacyIssue:
    """Legacy parser issue description"""
    issue_type: LegacyIssueType
    title: str
    description: str
    impact: str
    recommendation: str
    severity: str  # "low", "medium", "high", "critical"


class LegacyParserDiagnostics:
    """Diagnostics for legacy parser issues"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.known_issues = self._initialize_known_issues()
        
    def _initialize_known_issues(self) -> List[LegacyIssue]:
        """Initialize known legacy parser issues"""
        return [
            LegacyIssue(
                issue_type=LegacyIssueType.PERFORMANCE,
                title="Slow Parsing Performance",
                description="Legacy parser is 70-80% slower than modern rosbags parser",
                impact="Significantly longer analysis times, especially for large bags",
                recommendation="Install rosbags library: pip install rosbags",
                severity="high"
            ),
            LegacyIssue(
                issue_type=LegacyIssueType.FEATURES,
                title="No LZ4 Compression Support",
                description="Legacy parser cannot handle LZ4 compressed bags",
                impact="Cannot process modern compressed bag files",
                recommendation="Use rosbags parser for LZ4 support",
                severity="medium"
            ),
            LegacyIssue(
                issue_type=LegacyIssueType.FEATURES,
                title="Limited Async Support",
                description="Legacy parser has limited asynchronous processing capabilities",
                impact="Poor performance in multi-threaded environments",
                recommendation="Upgrade to unified analyzer system",
                severity="medium"
            ),
            LegacyIssue(
                issue_type=LegacyIssueType.FEATURES,
                title="No Advanced Caching",
                description="Legacy parser lacks intelligent caching mechanisms",
                impact="Repeated analysis requires full reprocessing",
                recommendation="Use unified cache manager with modern parsers",
                severity="medium"
            ),
            LegacyIssue(
                issue_type=LegacyIssueType.STABILITY,
                title="Memory Usage Issues",
                description="Legacy parser may have higher memory consumption",
                impact="Potential memory issues with very large bags",
                recommendation="Monitor memory usage and consider alternatives",
                severity="low"
            )
        ]
        
    def diagnose_issues(self, bag_path: str) -> List[LegacyIssue]:
        """Diagnose specific issues for a bag file"""
        issues = []
        
        # Check file size for performance impact
        try:
            file_size = os.path.getsize(bag_path)
            if file_size > 1024 * 1024 * 1024:  # > 1GB
                issues.append(LegacyIssue(
                    issue_type=LegacyIssueType.PERFORMANCE,
                    title="Large File Performance Impact",
                    description=f"Bag file is {file_size / (1024*1024*1024):.1f}GB - legacy parser will be very slow",
                    impact="Processing time may be 10+ minutes vs 1-2 minutes with modern parser",
                    recommendation="Strongly recommend installing rosbags library",
                    severity="critical"
                ))
        except Exception:
            pass
            
        # Check for compression
        try:
            with open(bag_path, 'rb') as f:
                header = f.read(12)
                if b'LZ4' in header or header.startswith(b'\x04"M\x18'):
                    issues.append(LegacyIssue(
                        issue_type=LegacyIssueType.COMPATIBILITY,
                        title="LZ4 Compression Detected",
                        description="Bag file uses LZ4 compression which is not supported by legacy parser",
                        impact="May fail to parse or produce incorrect results",
                        recommendation="Install rosbags library immediately",
                        severity="critical"
                    ))
        except Exception:
            pass
            
        # Add general issues that always apply
        issues.extend(self.known_issues)
        
        return issues
        
    def get_upgrade_recommendations(self) -> List[str]:
        """Get specific upgrade recommendations"""
        return [
            "Install rosbags library: pip install rosbags",
            "Update ROS environment to latest version",
            "Check system dependencies: apt update && apt upgrade ros-*",
            "Verify Python environment: python --version should be 3.8+",
            "Test installation: python -c 'import rosbags; print(rosbags.__version__)'",
            "Consider using conda/mamba for dependency management"
        ]


class LegacyParserWrapper:
    """Isolated wrapper for legacy rosbag parser with enhanced warnings"""
    
    def __init__(self):
        self.console = Console()
        self.logger = get_logger(__name__)
        self.diagnostics = LegacyParserDiagnostics()
        
        # Warning tracking
        self.warnings_shown: Dict[str, bool] = {}
        self.warning_lock = threading.Lock()
        
        # Performance tracking
        self.performance_data: Dict[str, Dict[str, Any]] = {}
        
    def parse_with_legacy(self, bag_path: str, operation: str = "analysis", **kwargs) -> Any:
        """
        Parse bag with legacy parser and show comprehensive warnings
        
        Args:
            bag_path: Path to bag file
            operation: Type of operation being performed
            **kwargs: Additional arguments for parser
            
        Returns:
            Parsed bag data
        """
        # Show warnings before parsing
        self._show_comprehensive_warning(bag_path, operation)
        
        # Record start time
        start_time = time.time()
        
        try:
            # Create legacy parser
            parser = create_parser(ParserType.CPP)
            
            # Perform the requested operation
            if operation == "analysis":
                result = self._perform_analysis(parser, bag_path, **kwargs)
            elif operation == "filter":
                result = self._perform_filter(parser, bag_path, **kwargs)
            elif operation == "info":
                result = self._perform_info(parser, bag_path, **kwargs)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
            # Record performance data
            duration = time.time() - start_time
            self._record_performance(bag_path, operation, duration, success=True)
            
            # Show post-processing summary
            self._show_performance_summary(bag_path, operation, duration)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self._record_performance(bag_path, operation, duration, success=False, error=str(e))
            
            # Show error guidance
            self._show_error_guidance(bag_path, str(e))
            raise
            
    def _show_comprehensive_warning(self, bag_path: str, operation: str) -> None:
        """Show comprehensive warning about legacy parser usage"""
        warning_key = f"{bag_path}_{operation}"
        
        with self.warning_lock:
            if self.warnings_shown.get(warning_key, False):
                return
                
            self.warnings_shown[warning_key] = True
            
        # Diagnose specific issues
        issues = self.diagnostics.diagnose_issues(bag_path)
        
        # Create warning panel
        warning_content = self._create_warning_content(bag_path, operation, issues)
        
        self.console.print(Panel(
            warning_content,
            title="[bold red]⚠️  LEGACY PARSER WARNING ⚠️[/bold red]",
            border_style="red",
            padding=(1, 2),
            expand=False
        ))
        
        # Show detailed diagnostics if there are critical issues
        critical_issues = [i for i in issues if i.severity == "critical"]
        if critical_issues:
            self._show_critical_issues_panel(critical_issues)
            
    def _create_warning_content(self, bag_path: str, operation: str, issues: List[LegacyIssue]) -> Text:
        """Create warning content text"""
        content = Text()
        
        # Header
        content.append("Using legacy parser for: ", style="bold yellow")
        content.append(f"{operation}\n", style="bold white")
        content.append("File: ", style="yellow")
        content.append(f"{os.path.basename(bag_path)}\n\n", style="white")
        
        # Performance impact
        content.append("Performance Impact:\n", style="bold red")
        content.append("• 70-80% slower than modern parser\n", style="red")
        content.append("• No intelligent caching\n", style="red")
        content.append("• Limited async support\n", style="red")
        content.append("• Higher memory usage\n\n", style="red")
        
        # Issue summary
        high_priority = [i for i in issues if i.severity in ["critical", "high"]]
        if high_priority:
            content.append("Critical Issues:\n", style="bold red")
            for issue in high_priority[:3]:  # Show top 3
                content.append(f"• {issue.title}\n", style="red")
            content.append("\n")
            
        # Quick fix
        content.append("Quick Fix:\n", style="bold green")
        content.append("pip install rosbags\n", style="bold green")
        content.append("Then restart the application\n\n", style="green")
        
        # Estimated time
        try:
            file_size = os.path.getsize(bag_path)
            estimated_time = self._estimate_processing_time(file_size, operation)
            content.append("Estimated Processing Time: ", style="bold yellow")
            content.append(f"{estimated_time}\n", style="yellow")
        except Exception:
            pass
            
        return content
        
    def _show_critical_issues_panel(self, critical_issues: List[LegacyIssue]) -> None:
        """Show detailed panel for critical issues"""
        if not critical_issues:
            return
            
        # Create issues table
        table = Table(title="Critical Issues Detected", show_header=True, header_style="bold red")
        table.add_column("Issue", style="red", width=20)
        table.add_column("Impact", style="yellow", width=30)
        table.add_column("Recommendation", style="green", width=25)
        
        for issue in critical_issues:
            table.add_row(
                issue.title,
                issue.impact,
                issue.recommendation
            )
            
        self.console.print(Panel(
            table,
            title="[bold red]Critical Issues[/bold red]",
            border_style="red"
        ))
        
    def _estimate_processing_time(self, file_size: int, operation: str) -> str:
        """Estimate processing time based on file size"""
        # Base estimates (in seconds per MB)
        base_rates = {
            "analysis": 0.05,  # 50ms per MB
            "filter": 0.1,     # 100ms per MB
            "info": 0.01       # 10ms per MB
        }
        
        rate = base_rates.get(operation, 0.05)
        size_mb = file_size / (1024 * 1024)
        estimated_seconds = size_mb * rate
        
        if estimated_seconds < 1:
            return f"< 1 second"
        elif estimated_seconds < 60:
            return f"~{int(estimated_seconds)} seconds"
        else:
            minutes = int(estimated_seconds / 60)
            return f"~{minutes} minutes"
            
    def _perform_analysis(self, parser: IBagParser, bag_path: str, **kwargs) -> Any:
        """Perform analysis with legacy parser"""
        topics, connections, time_range = parser.load_bag(bag_path)
        
        # Basic analysis result
        return {
            'topics': topics,
            'connections': connections,
            'time_range': time_range,
            'parser_type': 'legacy',
            'performance_tier': 'low'
        }
        
    def _perform_filter(self, parser: IBagParser, bag_path: str, **kwargs) -> Any:
        """Perform filtering with legacy parser"""
        output_path = kwargs.get('output_path')
        topics = kwargs.get('topics', [])
        compression = kwargs.get('compression', 'none')
        
        # Use parser's filter method
        return parser.filter_bag(bag_path, output_path, topics, compression)
        
    def _perform_info(self, parser: IBagParser, bag_path: str, **kwargs) -> Any:
        """Get bag info with legacy parser"""
        topics, connections, time_range = parser.load_bag(bag_path)
        
        return {
            'topics': len(topics),
            'connections': len(connections),
            'time_range': time_range,
            'file_size': os.path.getsize(bag_path)
        }
        
    def _record_performance(self, bag_path: str, operation: str, duration: float, 
                          success: bool, error: Optional[str] = None) -> None:
        """Record performance data"""
        key = f"{bag_path}_{operation}"
        
        self.performance_data[key] = {
            'operation': operation,
            'duration': duration,
            'success': success,
            'error': error,
            'timestamp': time.time(),
            'file_size': os.path.getsize(bag_path) if os.path.exists(bag_path) else 0
        }
        
    def _show_performance_summary(self, bag_path: str, operation: str, duration: float) -> None:
        """Show performance summary after operation"""
        try:
            file_size = os.path.getsize(bag_path)
            size_mb = file_size / (1024 * 1024)
            
            # Estimate modern parser performance
            modern_duration = duration * 0.3  # Modern parser is ~70% faster
            time_wasted = duration - modern_duration
            
            summary = Text()
            summary.append(f"Legacy Parser Performance Summary:\n", style="bold yellow")
            summary.append(f"Operation: {operation}\n", style="white")
            summary.append(f"Duration: {duration:.1f}s\n", style="white")
            summary.append(f"File Size: {size_mb:.1f}MB\n", style="white")
            summary.append(f"Estimated Modern Parser Time: {modern_duration:.1f}s\n", style="green")
            summary.append(f"Time Wasted: {time_wasted:.1f}s\n", style="red")
            
            self.console.print(Panel(
                summary,
                title="[yellow]Performance Summary[/yellow]",
                border_style="yellow",
                padding=(0, 1)
            ))
            
        except Exception as e:
            self.logger.warning(f"Could not show performance summary: {e}")
            
    def _show_error_guidance(self, bag_path: str, error: str) -> None:
        """Show guidance when errors occur"""
        guidance = Text()
        guidance.append("Legacy Parser Error Guidance:\n\n", style="bold red")
        guidance.append(f"Error: {error}\n\n", style="red")
        
        guidance.append("Common Solutions:\n", style="bold yellow")
        guidance.append("1. Install rosbags library: pip install rosbags\n", style="yellow")
        guidance.append("2. Check bag file integrity\n", style="yellow")
        guidance.append("3. Verify ROS environment setup\n", style="yellow")
        guidance.append("4. Try with a different bag file\n", style="yellow")
        
        guidance.append("\nGet Help:\n", style="bold green")
        guidance.append("• Check documentation: docs/PERFORMANCE_OPTIMIZATION.md\n", style="green")
        guidance.append("• Run diagnostic: rose diagnose\n", style="green")
        
        self.console.print(Panel(
            guidance,
            title="[bold red]Error Guidance[/bold red]",
            border_style="red"
        ))
        
    def get_performance_data(self) -> Dict[str, Dict[str, Any]]:
        """Get recorded performance data"""
        return dict(self.performance_data)
        
    def clear_warnings(self) -> None:
        """Clear warning cache"""
        with self.warning_lock:
            self.warnings_shown.clear()
            
    def get_diagnostics_report(self, bag_path: str) -> Dict[str, Any]:
        """Get comprehensive diagnostics report"""
        issues = self.diagnostics.diagnose_issues(bag_path)
        recommendations = self.diagnostics.get_upgrade_recommendations()
        
        return {
            'bag_path': bag_path,
            'issues': [
                {
                    'type': issue.issue_type.value,
                    'title': issue.title,
                    'description': issue.description,
                    'impact': issue.impact,
                    'recommendation': issue.recommendation,
                    'severity': issue.severity
                }
                for issue in issues
            ],
            'recommendations': recommendations,
            'critical_issues': len([i for i in issues if i.severity == "critical"]),
            'performance_data': self.performance_data
        }


# Global legacy parser wrapper instance
_global_legacy_wrapper: Optional[LegacyParserWrapper] = None


def get_legacy_parser_wrapper() -> LegacyParserWrapper:
    """Get global legacy parser wrapper instance"""
    global _global_legacy_wrapper
    if _global_legacy_wrapper is None:
        _global_legacy_wrapper = LegacyParserWrapper()
    return _global_legacy_wrapper


def parse_with_legacy_warnings(bag_path: str, operation: str = "analysis", **kwargs) -> Any:
    """
    Convenience function to parse with legacy parser and full warnings
    
    Args:
        bag_path: Path to bag file
        operation: Type of operation
        **kwargs: Additional arguments
        
    Returns:
        Parse result
    """
    wrapper = get_legacy_parser_wrapper()
    return wrapper.parse_with_legacy(bag_path, operation, **kwargs) 