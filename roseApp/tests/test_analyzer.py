"""
Test cases for analyzer module
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from roseApp.core.analyzer import (
    BagAnalyzer, AnalysisType, BagInfo, MessageTypeInfo, AnalysisResult,
    analyze_bag_async, cleanup_analyzer
)


class TestBagInfo:
    """Test cases for BagInfo class"""
    
    def test_bag_info_creation(self):
        """Test basic BagInfo creation"""
        info = BagInfo(
            path=Path("/tmp/test.bag"),
            size_bytes=1024000,
            topics={"/topic1", "/topic2"},
            message_counts={"/topic1": 100, "/topic2": 50},
            time_range=((123456789, 0), (123456790, 0)),
            connections={"/topic1": "std_msgs/String", "/topic2": "geometry_msgs/Twist"},
            duration_seconds=1.0
        )
        
        assert info.path == Path("/tmp/test.bag")
        assert info.size_bytes == 1024000
        assert len(info.topics) == 2
        assert info.duration_seconds == 1.0


class TestMessageTypeInfo:
    """Test cases for MessageTypeInfo class"""
    
    def test_message_type_info_creation(self):
        """Test basic MessageTypeInfo creation"""
        msg_type = MessageTypeInfo(
            type_name="std_msgs/String",
            fields={"data": {"type": "str"}},
            definition="string data",
            md5sum="992ce8a1687cec8c8bd883ec73ca41d1"
        )
        
        assert msg_type.type_name == "std_msgs/String"
        assert "data" in msg_type.fields
    
    def test_get_field_paths_empty(self):
        """Test getting field paths from empty fields"""
        msg_type = MessageTypeInfo(type_name="std_msgs/Empty")
        paths = msg_type.get_field_paths()
        assert paths == []
    
    def test_get_field_paths_simple(self):
        """Test getting field paths from simple fields"""
        msg_type = MessageTypeInfo(
            type_name="std_msgs/String",
            fields={"data": {"type": "str"}}
        )
        paths = msg_type.get_field_paths()
        assert "data" in paths
    
    def test_get_field_paths_nested(self):
        """Test getting field paths from nested fields"""
        msg_type = MessageTypeInfo(
            type_name="geometry_msgs/Twist",
            fields={
                "linear": {
                    "type": "geometry_msgs/Vector3",
                    "fields": {
                        "x": {"type": "float64"},
                        "y": {"type": "float64"},
                        "z": {"type": "float64"}
                    }
                },
                "angular": {
                    "type": "geometry_msgs/Vector3",
                    "fields": {
                        "x": {"type": "float64"},
                        "y": {"type": "float64"},
                        "z": {"type": "float64"}
                    }
                }
            }
        )
        
        paths = msg_type.get_field_paths()
        assert "linear.x" in paths
        assert "linear.y" in paths
        assert "linear.z" in paths
        assert "angular.x" in paths
        assert "angular.y" in paths
        assert "angular.z" in paths


class TestAnalysisResult:
    """Test cases for AnalysisResult class"""
    
    def test_analysis_result_creation(self):
        """Test basic AnalysisResult creation"""
        bag_info = BagInfo(
            path=Path("/tmp/test.bag"),
            size_bytes=1024000,
            topics={"/topic1"},
            message_counts={"/topic1": 100}
        )
        
        result = AnalysisResult(
            bag_info=bag_info,
            message_types={"std_msgs/String": MessageTypeInfo(type_name="std_msgs/String")},
            analysis_type=AnalysisType.METADATA,
            analysis_time=0.5,
            cached=False
        )
        
        assert result.bag_info == bag_info
        assert result.analysis_type == AnalysisType.METADATA
        assert result.analysis_time == 0.5
        assert not result.cached
    
    def test_get_topic_field_paths(self):
        """Test getting topic field paths"""
        bag_info = BagInfo(
            path=Path("/tmp/test.bag"),
            size_bytes=1024000,
            topics={"/topic1"},
            message_counts={"/topic1": 100},
            connections={"/topic1": "std_msgs/String"}
        )
        
        result = AnalysisResult(
            bag_info=bag_info,
            message_types={"std_msgs/String": MessageTypeInfo(type_name="std_msgs/String")}
        )
        
        paths = result.get_topic_field_paths("/topic1")
        assert paths == []


class TestBagAnalyzer:
    """Test cases for BagAnalyzer class"""
    
    @pytest.fixture
    def mock_parser(self):
        """Create a mock parser"""
        mock = Mock()
        mock.load_bag.return_value = (
            ["/topic1", "/topic2"],
            {"/topic1": "std_msgs/String", "/topic2": "geometry_msgs/Twist"},
            ((123456789, 0), (123456790, 0))
        )
        mock.get_message_counts.return_value = {"/topic1": 100, "/topic2": 50}
        return mock
    
    def test_analyzer_initialization(self):
        """Test basic analyzer initialization"""
        analyzer = BagAnalyzer(max_workers=2)
        assert analyzer.max_workers == 2
    
    @pytest.mark.asyncio
    async def test_analyze_bag_async_metadata(self, temp_dir, mock_parser):
        """Test async bag analysis with metadata type"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('roseApp.core.parser.create_best_parser', return_value=mock_parser):
            with patch.object(bag_path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = 1024000
                mock_stat.return_value.st_mtime = 1234567890
                
                analyzer = BagAnalyzer()
                result = await analyzer.analyze_bag_async(
                    bag_path=bag_path,
                    analysis_type=AnalysisType.METADATA
                )
                
                assert isinstance(result, AnalysisResult)
                assert result.analysis_type == AnalysisType.METADATA
                assert result.bag_info.path == bag_path
                assert len(result.bag_info.topics) == 2
                assert result.bag_info.message_counts["/topic1"] == 100
    
    @pytest.mark.asyncio
    async def test_analyze_bag_async_full_analysis(self, temp_dir, mock_parser):
        """Test async bag analysis with full analysis type"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('roseApp.core.parser.create_best_parser', return_value=mock_parser):
            with patch.object(bag_path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = 1024000
                mock_stat.return_value.st_mtime = 1234567890
                
                # Mock the message reading
                def mock_read_messages(bag_path, topics):
                    # Mock message objects
                    class MockMessage:
                        def __init__(self):
                            self.data = "test"
                    
                    yield ((123456789, 0), MockMessage())
                
                mock_parser.read_messages = mock_read_messages
                
                analyzer = BagAnalyzer()
                result = await analyzer.analyze_bag_async(
                    bag_path=bag_path,
                    analysis_type=AnalysisType.FULL_ANALYSIS
                )
                
                assert isinstance(result, AnalysisResult)
                assert result.analysis_type == AnalysisType.FULL_ANALYSIS
                assert len(result.message_types) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_bag_async_with_progress(self, temp_dir, mock_parser):
        """Test async bag analysis with progress callback"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        progress_values = []
        
        def progress_callback(progress):
            progress_values.append(progress)
        
        with patch('roseApp.core.parser.create_best_parser', return_value=mock_parser):
            with patch.object(bag_path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = 1024000
                mock_stat.return_value.st_mtime = 1234567890
                
                analyzer = BagAnalyzer()
                result = await analyzer.analyze_bag_async(
                    bag_path=bag_path,
                    analysis_type=AnalysisType.METADATA,
                    progress_callback=progress_callback
                )
                
                assert isinstance(result, AnalysisResult)
                assert len(progress_values) > 0
                assert 100.0 in progress_values
    
    @pytest.mark.asyncio
    async def test_analyze_bag_async_with_cache(self, temp_dir, mock_parser):
        """Test async bag analysis with caching"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('roseApp.core.parser.create_best_parser', return_value=mock_parser):
            with patch.object(bag_path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = 1024000
                mock_stat.return_value.st_mtime = 1234567890
                
                # Mock cache to return cached result
                mock_cache = Mock()
                mock_cache.get.return_value = AnalysisResult(
                    bag_info=BagInfo(
                        path=bag_path,
                        size_bytes=1024000,
                        topics={"/topic1"},
                        message_counts={"/topic1": 100}
                    ),
                    cached=True
                )
                
                analyzer = BagAnalyzer()
                analyzer.cache = mock_cache
                
                result = await analyzer.analyze_bag_async(
                    bag_path=bag_path,
                    analysis_type=AnalysisType.METADATA
                )
                
                assert isinstance(result, AnalysisResult)
                assert result.cached
    
    @pytest.mark.asyncio
    async def test_analyze_bag_async_error_handling(self, temp_dir):
        """Test error handling in async bag analysis"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('roseApp.core.parser.create_best_parser', side_effect=Exception("Parser error")):
            analyzer = BagAnalyzer()
            result = await analyzer.analyze_bag_async(
                bag_path=bag_path,
                analysis_type=AnalysisType.METADATA
            )
            
            assert isinstance(result, AnalysisResult)
            assert len(result.errors) > 0
            assert "Parser error" in result.errors[0]
    
    def test_extract_message_fields(self):
        """Test message field extraction"""
        analyzer = BagAnalyzer()
        
        # Mock message with __slots__
        class MockMessage:
            __slots__ = ['data', 'header']
            
            def __init__(self):
                self.data = "test"
                self.header = Mock()
                self.header.stamp = Mock()
                self.header.stamp.secs = 123456789
                self.header.stamp.nsecs = 0
        
        message = MockMessage()
        fields = analyzer._extract_message_fields(message)
        
        assert "data" in fields
        assert "header" in fields
        assert fields["data"]["type"] == "str"
    
    def test_analyze_field_value(self):
        """Test field value analysis"""
        analyzer = BagAnalyzer()
        
        # Test primitive types
        result = analyzer._analyze_field_value(42)
        assert result["type"] == "int"
        assert result["value_sample"] == "42"
        
        # Test list
        result = analyzer._analyze_field_value([1, 2, 3])
        assert result["type"] == "list"
        assert result["array"] is True
        assert result["length"] == 3
    
    def test_merge_fields(self):
        """Test field merging"""
        analyzer = BagAnalyzer()
        
        existing = {
            "field1": {"type": "int"},
            "field2": {"type": "str"}
        }
        
        new = {
            "field2": {"type": "str", "value": "test"},
            "field3": {"type": "float"}
        }
        
        merged = analyzer._merge_fields(existing, new)
        assert len(merged) == 3
        assert "field1" in merged
        assert "field2" in merged
        assert "field3" in merged
    
    def test_cleanup(self):
        """Test analyzer cleanup"""
        analyzer = BagAnalyzer()
        analyzer.cleanup()
        # Should not raise any exceptions


class TestGlobalFunctions:
    """Test cases for global functions"""
    
    @pytest.mark.asyncio
    async def test_analyze_bag_async_global(self, temp_dir, mock_parser):
        """Test global analyze_bag_async function"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('roseApp.core.parser.create_best_parser', return_value=mock_parser):
            with patch.object(bag_path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = 1024000
                mock_stat.return_value.st_mtime = 1234567890
                
                result = await analyze_bag_async(
                    bag_path=bag_path,
                    analysis_type=AnalysisType.METADATA
                )
                
                assert isinstance(result, AnalysisResult)
    
    def test_cleanup_analyzer(self):
        """Test global cleanup function"""
        cleanup_analyzer()
        # Should not raise any exceptions