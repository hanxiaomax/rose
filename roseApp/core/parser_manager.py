#!/usr/bin/env python3
"""
Intelligent parser management with automatic fallback mechanisms.

This module provides a centralized parser management system that automatically
selects the best available parser and provides clear warnings when falling back
to legacy parsers.
"""

import time
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import os

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..core.util import get_logger
from ..core.parser import create_parser, ParserType, IBagParser
from ..core.legacy_parser import get_legacy_parser_wrapper, LegacyParserWrapper


class ParserHealth(Enum):
    """Parser health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class ParserTest:
    """Parser test result"""
    parser_type: ParserType
    success: bool
    duration: float
    error: Optional[str] = None
    warnings: List[str] = None


@dataclass
class ParserCapabilities:
    """Parser capabilities information"""
    parser_type: ParserType
    supports_compression: bool
    supports_lz4: bool
    supports_async: bool
    performance_tier: int  # 1 = high, 2 = medium, 3 = low
    compatibility_score: float  # 0.0 to 1.0


class ParserHealthChecker:
    """Health checking and diagnostics for parsers"""
    
    def __init__(self, test_timeout: float = 5.0):
        """
        Initialize parser health checker
        
        Args:
            test_timeout: Timeout for parser health tests
        """
        self.test_timeout = test_timeout
        self.health_cache: Dict[str, Tuple[ParserHealth, float]] = {}
        self.logger = get_logger(__name__)
        
    async def check_parser_health(self, parser_type: ParserType, 
                                 bag_path: str) -> ParserHealth:
        """
        Check if parser can handle the bag file
        
        Args:
            parser_type: Parser type to test
            bag_path: Path to test bag file
            
        Returns:
            ParserHealth status
        """
        cache_key = f"{parser_type.name}_{bag_path}"
        
        # Check cache first
        if cache_key in self.health_cache:
            health, timestamp = self.health_cache[cache_key]
            if time.time() - timestamp < 300:  # 5 minute cache
                return health
        
        # Perform health check
        try:
            test_result = await self._test_parser(parser_type, bag_path)
            
            if test_result.success:
                if test_result.warnings:
                    health = ParserHealth.DEGRADED
                else:
                    health = ParserHealth.HEALTHY
            else:
                health = ParserHealth.FAILED
                
        except Exception as e:
            self.logger.error(f"Error checking parser health for {parser_type.name}: {e}")
            health = ParserHealth.UNKNOWN
            
        # Cache result
        self.health_cache[cache_key] = (health, time.time())
        return health
        
    async def _test_parser(self, parser_type: ParserType, 
                          bag_path: str) -> ParserTest:
        """Test parser with timeout"""
        start_time = time.time()
        
        try:
            # Run parser test with timeout
            result = await asyncio.wait_for(
                self._run_parser_test(parser_type, bag_path),
                timeout=self.test_timeout
            )
            return result
            
        except asyncio.TimeoutError:
            return ParserTest(
                parser_type=parser_type,
                success=False,
                duration=time.time() - start_time,
                error="Parser test timed out"
            )
        except Exception as e:
            return ParserTest(
                parser_type=parser_type,
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            
    async def _run_parser_test(self, parser_type: ParserType, 
                              bag_path: str) -> ParserTest:
        """Run actual parser test"""
        loop = asyncio.get_event_loop()
        start_time = time.time()
        
        def _test():
            try:
                parser = create_parser(parser_type)
                topics, connections, time_range = parser.load_bag(bag_path)
                
                # Basic validation
                if not topics or not isinstance(topics, list):
                    raise ValueError("Invalid topics returned")
                    
                if not connections or not isinstance(connections, dict):
                    raise ValueError("Invalid connections returned")
                    
                warnings = []
                
                # Check for specific issues
                if parser_type == ParserType.CPP:
                    # Check for potential legacy issues
                    if len(topics) > 50:
                        warnings.append("Large number of topics may impact performance")
                    
                    try:
                        file_size = os.path.getsize(bag_path)
                        if file_size > 1024 * 1024 * 1024:  # > 1GB
                            warnings.append("Large file size will significantly impact performance")
                    except Exception:
                        pass
                
                return ParserTest(
                    parser_type=parser_type,
                    success=True,
                    duration=time.time() - start_time,
                    warnings=warnings
                )
                
            except Exception as e:
                return ParserTest(
                    parser_type=parser_type,
                    success=False,
                    duration=time.time() - start_time,
                    error=str(e)
                )
                
        return await loop.run_in_executor(None, _test)
        
    def get_parser_capabilities(self, parser_type: ParserType) -> ParserCapabilities:
        """Get parser capabilities information"""
        if parser_type == ParserType.ROSBAGS:
            return ParserCapabilities(
                parser_type=parser_type,
                supports_compression=True,
                supports_lz4=True,
                supports_async=True,
                performance_tier=1,
                compatibility_score=0.95
            )
        else:  # CPP (Legacy)
            return ParserCapabilities(
                parser_type=parser_type,
                supports_compression=False,
                supports_lz4=False,
                supports_async=False,
                performance_tier=3,
                compatibility_score=1.0
            )
            
    def get_detailed_diagnostics(self, parser_type: ParserType, 
                               bag_path: str) -> Dict[str, Any]:
        """Get detailed diagnostics for parser and bag combination"""
        try:
            # Get basic capabilities
            capabilities = self.get_parser_capabilities(parser_type)
            
            # Get file info
            file_info = {}
            if os.path.exists(bag_path):
                stat = os.stat(bag_path)
                file_info = {
                    'size': stat.st_size,
                    'size_mb': stat.st_size / (1024 * 1024),
                    'modified': stat.st_mtime
                }
                
            # Check for specific issues
            issues = []
            recommendations = []
            
            if parser_type == ParserType.CPP:
                # Legacy parser specific diagnostics
                if file_info.get('size_mb', 0) > 1024:  # > 1GB
                    issues.append("Large file size will cause significant performance degradation")
                    recommendations.append("Consider using rosbags parser for better performance")
                    
                # Check for compression
                try:
                    with open(bag_path, 'rb') as f:
                        header = f.read(12)
                        if b'LZ4' in header:
                            issues.append("LZ4 compression detected - not supported by legacy parser")
                            recommendations.append("Install rosbags library to handle LZ4 compression")
                except Exception:
                    pass
                    
                issues.append("Legacy parser has 70-80% slower performance")
                recommendations.append("Upgrade to rosbags parser: pip install rosbags")
                
            return {
                'parser_type': parser_type.name,
                'capabilities': capabilities,
                'file_info': file_info,
                'issues': issues,
                'recommendations': recommendations,
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'parser_type': parser_type.name,
                'error': str(e),
                'timestamp': time.time()
            }


class ParserManager:
    """Intelligent parser management with automatic fallback"""
    
    def __init__(self):
        """Initialize parser manager"""
        self.health_checker = ParserHealthChecker()
        self.console = Console()
        self.logger = get_logger(__name__)
        self.fallback_warnings_shown: Dict[str, bool] = {}
        self.legacy_wrapper = get_legacy_parser_wrapper()
        
        # Parser preference order (highest to lowest priority)
        self.parser_preference = [
            ParserType.ROSBAGS,
            ParserType.CPP
        ]
        
    async def get_optimal_parser(self, bag_path: str, 
                               preferred_type: Optional[ParserType] = None) -> Tuple[IBagParser, ParserType]:
        """
        Get the best available parser for a bag file
        
        Args:
            bag_path: Path to bag file
            preferred_type: Preferred parser type (if specified)
            
        Returns:
            Tuple of (parser instance, parser type used)
        """
        # If preferred type is specified, try it first
        if preferred_type:
            health = await self.health_checker.check_parser_health(preferred_type, bag_path)
            if health in [ParserHealth.HEALTHY, ParserHealth.DEGRADED]:
                parser = self._create_parser_with_wrapper(preferred_type, bag_path)
                if health == ParserHealth.DEGRADED:
                    self._show_degraded_warning(preferred_type, bag_path)
                return parser, preferred_type
        
        # Try parsers in preference order
        for parser_type in self.parser_preference:
            try:
                health = await self.health_checker.check_parser_health(parser_type, bag_path)
                
                if health == ParserHealth.HEALTHY:
                    parser = self._create_parser_with_wrapper(parser_type, bag_path)
                    return parser, parser_type
                    
                elif health == ParserHealth.DEGRADED:
                    parser = self._create_parser_with_wrapper(parser_type, bag_path)
                    self._show_degraded_warning(parser_type, bag_path)
                    return parser, parser_type
                    
            except Exception as e:
                self.logger.warning(f"Failed to create {parser_type.name} parser: {e}")
                continue
        
        # If all parsers failed, try legacy as last resort
        try:
            self._show_fallback_warning("All primary parsers failed", bag_path)
            parser = self._create_parser_with_wrapper(ParserType.CPP, bag_path)
            return parser, ParserType.CPP
            
        except Exception as e:
            raise RuntimeError(f"All parsers failed. Last error: {e}")
            
    def _create_parser_with_wrapper(self, parser_type: ParserType, bag_path: str) -> IBagParser:
        """Create parser with appropriate wrapper"""
        if parser_type == ParserType.CPP:
            # For legacy parser, we don't return the wrapper directly
            # Instead, we return the actual parser but log the usage
            self.logger.info(f"Using legacy parser for {bag_path}")
            return create_parser(parser_type)
        else:
            # For modern parsers, create directly
            return create_parser(parser_type)
            
    def _show_fallback_warning(self, reason: str, bag_path: str) -> None:
        """Show prominent warning when using fallback parser"""
        warning_key = f"fallback_{reason}_{bag_path}"
        
        if not self.fallback_warnings_shown.get(warning_key, False):
            # Use legacy wrapper to show comprehensive warning
            self.legacy_wrapper._show_comprehensive_warning(bag_path, "fallback")
            self.fallback_warnings_shown[warning_key] = True
            
    def _show_degraded_warning(self, parser_type: ParserType, bag_path: str) -> None:
        """Show warning when parser is in degraded state"""
        warning_key = f"degraded_{parser_type.name}_{bag_path}"
        
        if not self.fallback_warnings_shown.get(warning_key, False):
            if parser_type == ParserType.CPP:
                # Use legacy wrapper for comprehensive warning
                self.legacy_wrapper._show_comprehensive_warning(bag_path, "degraded")
            else:
                # Standard degraded warning
                self.console.print(Panel(
                    f"[bold yellow]⚠️  Parser Warning ⚠️[/bold yellow]\n\n"
                    f"Parser {parser_type.name} is running in degraded mode.\n"
                    f"Some features may be limited or unavailable.\n\n"
                    f"Consider checking your ROS environment configuration.",
                    title="Performance Notice",
                    border_style="yellow"
                ))
            self.fallback_warnings_shown[warning_key] = True
            
    async def diagnose_parser_issues(self, bag_path: str) -> Dict[ParserType, Any]:
        """
        Diagnose parser issues for a bag file
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Dictionary of parser types and their diagnostic results
        """
        results = {}
        
        for parser_type in [ParserType.ROSBAGS, ParserType.CPP]:
            try:
                health = await self.health_checker.check_parser_health(parser_type, bag_path)
                capabilities = self.health_checker.get_parser_capabilities(parser_type)
                detailed_diagnostics = self.health_checker.get_detailed_diagnostics(parser_type, bag_path)
                
                results[parser_type] = {
                    'health': health,
                    'capabilities': capabilities,
                    'diagnostics': detailed_diagnostics,
                    'available': True
                }
                
            except Exception as e:
                results[parser_type] = {
                    'health': ParserHealth.FAILED,
                    'error': str(e),
                    'available': False
                }
                
        return results
        
    def get_parser_recommendation(self, bag_path: str) -> str:
        """Get recommendation for parser selection"""
        try:
            file_size = os.path.getsize(bag_path)
            size_mb = file_size / (1024 * 1024)
            
            if size_mb > 1024:  # > 1GB
                return (
                    "For large files (>1GB), rosbags parser is STRONGLY recommended.\n"
                    "Legacy parser will be very slow and may consume excessive memory.\n"
                    "Install with: pip install rosbags"
                )
            elif size_mb > 100:  # > 100MB
                return (
                    "For medium-large files (>100MB), rosbags parser is recommended.\n"
                    "Performance improvement will be significant.\n"
                    "Install with: pip install rosbags"
                )
            else:
                return (
                    "For best performance, use rosbags parser.\n"
                    "Install with: pip install rosbags"
                )
                
        except Exception:
            return (
                "For best performance, ensure rosbags library is installed.\n"
                "Use legacy parser only when compatibility issues prevent "
                "using the high-performance rosbags parser."
            )
            
    def get_legacy_diagnostics(self, bag_path: str) -> Dict[str, Any]:
        """Get legacy parser specific diagnostics"""
        return self.legacy_wrapper.get_diagnostics_report(bag_path)
        
    def parse_with_legacy_safely(self, bag_path: str, operation: str = "analysis", **kwargs) -> Any:
        """
        Parse with legacy parser using safe wrapper
        
        Args:
            bag_path: Path to bag file
            operation: Operation type
            **kwargs: Additional arguments
            
        Returns:
            Parse result
        """
        return self.legacy_wrapper.parse_with_legacy(bag_path, operation, **kwargs)
        
    def clear_warning_cache(self):
        """Clear the fallback warning cache"""
        self.fallback_warnings_shown.clear()
        self.legacy_wrapper.clear_warnings()
        
    def get_parser_stats(self) -> Dict[str, Any]:
        """Get parser usage statistics"""
        return {
            'warnings_shown': len(self.fallback_warnings_shown),
            'health_cache_size': len(self.health_checker.health_cache),
            'available_parsers': [p.name for p in self.parser_preference],
            'legacy_performance_data': self.legacy_wrapper.get_performance_data()
        }


# Global parser manager instance
_global_parser_manager: Optional[ParserManager] = None


def get_parser_manager() -> ParserManager:
    """Get global parser manager instance"""
    global _global_parser_manager
    if _global_parser_manager is None:
        _global_parser_manager = ParserManager()
    return _global_parser_manager


async def get_optimal_parser_async(bag_path: str, 
                                  preferred_type: Optional[ParserType] = None) -> Tuple[IBagParser, ParserType]:
    """
    Async convenience function to get optimal parser
    
    Args:
        bag_path: Path to bag file
        preferred_type: Preferred parser type
        
    Returns:
        Tuple of (parser instance, parser type used)
    """
    manager = get_parser_manager()
    return await manager.get_optimal_parser(bag_path, preferred_type)


def diagnose_bag_parsers(bag_path: str) -> Dict[str, Any]:
    """
    Synchronous function to diagnose parser issues
    
    Args:
        bag_path: Path to bag file
        
    Returns:
        Diagnostic information
    """
    manager = get_parser_manager()
    
    # Run async diagnosis in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(manager.diagnose_parser_issues(bag_path))
        return result
    finally:
        loop.close() 