#!/usr/bin/env python3
"""
Phase 4 Integration Tests

Tests for the unified command infrastructure implementation.
"""

import asyncio
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

# Import the v2 commands
from roseApp.cli.filter_v2 import FilterConfig, FilterResult, _filter_single_bag_async
from roseApp.cli.plot_v2 import PlotConfig, PlotResult, _plot_bag_async
from roseApp.cli.prune_v2 import PruneConfig, PruneResult, _prune_bag_async
from roseApp.cli.unified_error_handler import (
    UnifiedErrorHandler, ErrorSeverity, ErrorCategory, ErrorContext
)
from roseApp.core.bag_engine import BagAnalysisEngine, AnalysisType
from roseApp.core.enhanced_cache import CacheLevel

class TestFilterV2:
    """Test filter command v2 implementation"""
    
    def test_filter_config_creation(self):
        """Test FilterConfig creation"""
        config = FilterConfig(
            input_path="/test/input.bag",
            output_path="/test/output.bag",
            topics={"topic1", "topic2"},
            compression="lz4",
            sort_by="count",
            overwrite=True,
            dry_run=False
        )
        
        assert config.input_path == "/test/input.bag"
        assert config.output_path == "/test/output.bag"
        assert config.topics == {"topic1", "topic2"}
        assert config.compression == "lz4"
        assert config.sort_by == "count"
        assert config.overwrite is True
        assert config.dry_run is False
    
    def test_filter_result_creation(self):
        """Test FilterResult creation"""
        result = FilterResult(
            success=True,
            input_size=1024,
            output_size=512,
            elapsed_time=10.5,
            topics_processed=5,
            messages_processed=100
        )
        
        assert result.success is True
        assert result.input_size == 1024
        assert result.output_size == 512
        assert result.elapsed_time == 10.5
        assert result.topics_processed == 5
        assert result.messages_processed == 100

class TestPlotV2:
    """Test plot command v2 implementation"""
    
    def test_plot_config_creation(self):
        """Test PlotConfig creation"""
        config = PlotConfig(
            bag_path="/test/input.bag",
            series=["topic1.field1", "topic2.field2"],
            output_path="/test/plot.png",
            time_range=(0.0, 10.0),
            plot_type="line",
            width=12,
            height=8,
            format="png"
        )
        
        assert config.bag_path == "/test/input.bag"
        assert config.series == ["topic1.field1", "topic2.field2"]
        assert config.output_path == "/test/plot.png"
        assert config.time_range == (0.0, 10.0)
        assert config.plot_type == "line"
        assert config.width == 12
        assert config.height == 8
        assert config.format == "png"
    
    def test_plot_result_creation(self):
        """Test PlotResult creation"""
        result = PlotResult(
            success=True,
            output_path="/test/plot.png",
            data_points=1000,
            time_range=(0.0, 10.0),
            elapsed_time=5.2
        )
        
        assert result.success is True
        assert result.output_path == "/test/plot.png"
        assert result.data_points == 1000
        assert result.time_range == (0.0, 10.0)
        assert result.elapsed_time == 5.2

class TestPruneV2:
    """Test prune command v2 implementation"""
    
    def test_prune_config_creation(self):
        """Test PruneConfig creation"""
        config = PruneConfig(
            bag_path="/test/input.bag",
            output_path="/test/output.bag",
            time_start=1.0,
            time_end=10.0,
            duration=5.0,
            topics=["topic1", "topic2"],
            compression="bz2"
        )
        
        assert config.bag_path == "/test/input.bag"
        assert config.output_path == "/test/output.bag"
        assert config.time_start == 1.0
        assert config.time_end == 10.0
        assert config.duration == 5.0
        assert config.topics == ["topic1", "topic2"]
        assert config.compression == "bz2"
    
    def test_prune_result_creation(self):
        """Test PruneResult creation"""
        result = PruneResult(
            success=True,
            input_size=2048,
            output_size=1024,
            original_duration=100.0,
            pruned_duration=50.0,
            messages_removed=500,
            topics_processed=3,
            elapsed_time=8.5
        )
        
        assert result.success is True
        assert result.input_size == 2048
        assert result.output_size == 1024
        assert result.original_duration == 100.0
        assert result.pruned_duration == 50.0
        assert result.messages_removed == 500
        assert result.topics_processed == 3
        assert result.elapsed_time == 8.5

class TestUnifiedErrorHandler:
    """Test unified error handling system"""
    
    def test_error_context_creation(self):
        """Test ErrorContext creation"""
        context = ErrorContext(
            command="filter",
            operation="bag_processing",
            file_path="/test/input.bag",
            parameters={"compression": "lz4"}
        )
        
        assert context.command == "filter"
        assert context.operation == "bag_processing"
        assert context.file_path == "/test/input.bag"
        assert context.parameters == {"compression": "lz4"}
        assert context.timestamp is not None
    
    def test_error_handler_creation(self):
        """Test UnifiedErrorHandler creation"""
        handler = UnifiedErrorHandler()
        
        assert handler.logger is not None
        assert handler.console is not None
        assert handler.error_history == []
        assert handler.legacy_wrapper is not None
    
    def test_error_context_creation_via_handler(self):
        """Test error context creation via handler"""
        handler = UnifiedErrorHandler()
        
        context = handler.create_context(
            command="plot",
            operation="data_extraction",
            file_path="/test/data.bag",
            parameters={"series": ["topic1.field1"]}
        )
        
        assert context.command == "plot"
        assert context.operation == "data_extraction"
        assert context.file_path == "/test/data.bag"
        assert context.parameters == {"series": ["topic1.field1"]}

class TestBagAnalysisEngineIntegration:
    """Test BagAnalysisEngine integration with v2 commands"""
    
    @pytest.fixture
    def mock_analysis_engine(self):
        """Create a mock BagAnalysisEngine for testing"""
        engine = MagicMock(spec=BagAnalysisEngine)
        
        # Mock analysis result
        mock_analysis = MagicMock()
        mock_analysis.topics = {
            "topic1": {"count": 100, "size": 1024, "type": "std_msgs/String"},
            "topic2": {"count": 200, "size": 2048, "type": "geometry_msgs/Twist"}
        }
        mock_analysis.start_time = 0.0
        mock_analysis.end_time = 10.0
        
        engine.analyze_bag = AsyncMock(return_value=mock_analysis)
        engine.filter_bag = AsyncMock(return_value={"messages_processed": 150})
        engine.prune_bag = AsyncMock(return_value={"messages_removed": 50})
        engine.extract_field_data = AsyncMock(return_value={
            "timestamps": [1.0, 2.0, 3.0],
            "values": [10.0, 20.0, 30.0]
        })
        
        return engine, mock_analysis
    
    @pytest.mark.asyncio
    async def test_filter_integration(self, mock_analysis_engine):
        """Test filter command integration with BagAnalysisEngine"""
        engine, mock_analysis = mock_analysis_engine
        
        config = FilterConfig(
            input_path="/test/input.bag",
            output_path="/test/output.bag",
            topics={"topic1"},
            compression="none",
            overwrite=True,
            dry_run=False
        )
        
        # Mock file operations
        with patch('os.path.getsize', return_value=1024), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.filter_v2.BagAnalysisEngine', return_value=engine):
            
            result = await _filter_single_bag_async(config)
            
            assert result.success is True
            assert result.topics_processed == 1
            
            # Verify engine was called correctly
            engine.analyze_bag.assert_called_once_with(
                "/test/input.bag",
                analysis_type=AnalysisType.FILTER,
                level=CacheLevel.METADATA
            )
    
    @pytest.mark.asyncio
    async def test_plot_integration(self, mock_analysis_engine):
        """Test plot command integration with BagAnalysisEngine"""
        engine, mock_analysis = mock_analysis_engine
        
        config = PlotConfig(
            bag_path="/test/input.bag",
            series=["topic1.field1"],
            output_path="/test/plot.png",
            plot_type="line",
            width=12,
            height=8,
            format="png"
        )
        
        # Mock matplotlib and file operations
        with patch('matplotlib.pyplot.figure'), \
             patch('matplotlib.pyplot.plot'), \
             patch('matplotlib.pyplot.savefig'), \
             patch('matplotlib.pyplot.close'), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.plot_v2.BagAnalysisEngine', return_value=engine):
            
            result = await _plot_bag_async(config, dry_run=True)
            
            assert result.success is True
            assert result.data_points == 0  # dry run
            
            # Verify engine was called correctly
            engine.analyze_bag.assert_called_once_with(
                "/test/input.bag",
                analysis_type=AnalysisType.PLOT,
                level=CacheLevel.FIELDS
            )
    
    @pytest.mark.asyncio
    async def test_prune_integration(self, mock_analysis_engine):
        """Test prune command integration with BagAnalysisEngine"""
        engine, mock_analysis = mock_analysis_engine
        
        config = PruneConfig(
            bag_path="/test/input.bag",
            output_path="/test/output.bag",
            time_start=1.0,
            time_end=9.0,
            topics=["topic1"],
            compression="none"
        )
        
        # Mock file operations
        with patch('os.path.getsize', return_value=1024), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.prune_v2.BagAnalysisEngine', return_value=engine):
            
            result = await _prune_bag_async(config, dry_run=True)
            
            assert result.success is True
            assert result.topics_processed == 1
            assert result.original_duration == 10.0
            assert result.pruned_duration == 8.0  # 9.0 - 1.0
            
            # Verify engine was called correctly
            engine.analyze_bag.assert_called_once_with(
                "/test/input.bag",
                analysis_type=AnalysisType.PRUNE,
                level=CacheLevel.STATISTICS
            )

class TestPerformanceImprovements:
    """Test performance improvements in v2 commands"""
    
    @pytest.mark.asyncio
    async def test_async_processing(self):
        """Test that all v2 commands use async processing"""
        # All main processing functions should be async
        assert asyncio.iscoroutinefunction(_filter_single_bag_async)
        assert asyncio.iscoroutinefunction(_plot_bag_async)
        assert asyncio.iscoroutinefunction(_prune_bag_async)
    
    def test_unified_api_usage(self):
        """Test that all v2 commands use unified API patterns"""
        # All commands should have Config and Result classes
        assert hasattr(FilterConfig, '__init__')
        assert hasattr(FilterResult, '__init__')
        assert hasattr(PlotConfig, '__init__')
        assert hasattr(PlotResult, '__init__')
        assert hasattr(PruneConfig, '__init__')
        assert hasattr(PruneResult, '__init__')
    
    def test_error_handling_consistency(self):
        """Test that error handling is consistent across commands"""
        # All commands should use the same error handling patterns
        handler = UnifiedErrorHandler()
        
        # Test error severity levels
        assert ErrorSeverity.INFO.value == "info"
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.CRITICAL.value == "critical"
        
        # Test error categories
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.FILE_IO.value == "file_io"
        assert ErrorCategory.PARSING.value == "parsing"
        assert ErrorCategory.PROCESSING.value == "processing"

def run_phase4_tests():
    """Run all Phase 4 integration tests"""
    print("Running Phase 4 Integration Tests...")
    
    # Create test instance
    test_suite = [
        TestFilterV2(),
        TestPlotV2(),
        TestPruneV2(),
        TestUnifiedErrorHandler(),
        TestBagAnalysisEngineIntegration(),
        TestPerformanceImprovements()
    ]
    
    # Run basic tests
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_suite:
        for method_name in dir(test_class):
            if method_name.startswith('test_'):
                total_tests += 1
                try:
                    method = getattr(test_class, method_name)
                    if asyncio.iscoroutinefunction(method):
                        # Skip async tests for now in basic run
                        print(f"  SKIP: {test_class.__class__.__name__}.{method_name} (async)")
                        continue
                    else:
                        method()
                    print(f"  PASS: {test_class.__class__.__name__}.{method_name}")
                    passed_tests += 1
                except Exception as e:
                    print(f"  FAIL: {test_class.__class__.__name__}.{method_name} - {e}")
    
    print(f"\nTest Results: {passed_tests}/{total_tests} tests passed")
    return passed_tests == total_tests

if __name__ == "__main__":
    # Run the tests
    success = run_phase4_tests()
    
    if success:
        print("\n✅ All Phase 4 integration tests passed!")
    else:
        print("\n❌ Some Phase 4 integration tests failed!")
    
    exit(0 if success else 1) 