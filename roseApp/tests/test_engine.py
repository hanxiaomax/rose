"""
Test cases for engine module
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from roseApp.core.engine import (
    BagEngine, AsyncIOManager, ProcessingResult, FilterConfig, CompressionType,
    filter_bag_async, get_engine, cleanup_engine
)


class TestCompressionType:
    """Test cases for CompressionType enum"""
    
    def test_compression_type_values(self):
        """Test compression type enum values"""
        assert CompressionType.NONE.value == "none"
        assert CompressionType.BZ2.value == "bz2"
        assert CompressionType.LZ4.value == "lz4"


class TestFilterConfig:
    """Test cases for FilterConfig class"""
    
    def test_filter_config_creation(self):
        """Test basic FilterConfig creation"""
        config = FilterConfig(
            topics=["/topic1", "/topic2"],
            time_range=((0, 0), (1, 0)),
            compression="bz2",
            output_path=Path("/tmp/output"),
            overwrite=True
        )
        
        assert len(config.topics) == 2
        assert config.compression == "bz2"
        assert config.overwrite is True


class TestProcessingResult:
    """Test cases for ProcessingResult class"""
    
    def test_processing_result_creation(self):
        """Test basic ProcessingResult creation"""
        result = ProcessingResult(
            success=True,
            input_path=Path("/tmp/input.bag"),
            output_path=Path("/tmp/output.bag"),
            processing_time=1.5,
            output_size=1024000
        )
        
        assert result.success is True
        assert result.input_path == Path("/tmp/input.bag")
        assert result.output_size == 1024000
    
    def test_size_str_formatting(self):
        """Test size string formatting"""
        result = ProcessingResult(success=True, input_path=Path("/tmp/test.bag"))
        
        result.output_size = 500
        assert result.size_str == "500.0 B"
        
        result.output_size = 1024
        assert result.size_str == "1.0 KB"
        
        result.output_size = 1024 * 1024
        assert result.size_str == "1.0 MB"
        
        result.output_size = 1024 * 1024 * 1024
        assert result.size_str == "1.0 GB"


class TestAsyncIOManager:
    """Test cases for AsyncIOManager class"""
    
    def test_io_manager_initialization(self):
        """Test basic AsyncIOManager initialization"""
        manager = AsyncIOManager(max_workers=2)
        assert manager.max_workers == 2
    
    @pytest.mark.asyncio
    async def test_copy_file_async(self, temp_dir):
        """Test async file copying"""
        source_file = temp_dir / "source.txt"
        dest_file = temp_dir / "dest.txt"
        source_file.write_text("test content")
        
        manager = AsyncIOManager()
        success = await manager.copy_file_async(source_file, dest_file)
        
        assert success is True
        assert dest_file.exists()
        assert dest_file.read_text() == "test content"
    
    @pytest.mark.asyncio
    async def test_delete_file_async(self, temp_dir):
        """Test async file deletion"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        manager = AsyncIOManager()
        success = await manager.delete_file_async(test_file)
        
        assert success is True
        assert not test_file.exists()
    
    @pytest.mark.asyncio
    async def test_ensure_directory_async(self, temp_dir):
        """Test async directory creation"""
        new_dir = temp_dir / "new" / "nested" / "directory"
        
        manager = AsyncIOManager()
        success = await manager.ensure_directory_async(new_dir)
        
        assert success is True
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_cleanup(self):
        """Test AsyncIOManager cleanup"""
        manager = AsyncIOManager()
        manager.cleanup()
        # Should not raise any exceptions


class TestBagEngine:
    """Test cases for BagEngine class"""
    
    def test_engine_initialization(self):
        """Test basic BagEngine initialization"""
        engine = BagEngine(max_workers=2)
        assert engine.max_workers == 2
        assert engine.io_manager.max_workers == 2
    
    @pytest.mark.asyncio
    async def test_analyze_bag_async(self, temp_dir):
        """Test async bag analysis"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        mock_result = Mock()
        mock_result.bag_info = Mock()
        
        with patch('roseApp.core.engine.analyze_bag_async', return_value=mock_result):
            engine = BagEngine()
            result = await engine.analyze_bag_async(bag_path)
            
            assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_filter_bag_async_success(self, temp_dir):
        """Test async bag filtering success"""
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        
        mock_parser = Mock()
        mock_parser.filter_bag.return_value = "Filtering completed"
        
        with patch('roseApp.core.engine.create_best_parser', return_value=mock_parser):
            engine = BagEngine()
            result = await engine.filter_bag_async(
                input_path=input_path,
                topics=["/topic1"],
                output_path=output_path,
                overwrite=True
            )
            
            assert result.success is True
            assert result.input_path == input_path
            assert result.output_path == output_path
    
    @pytest.mark.asyncio
    async def test_filter_bag_async_file_exists_error(self, temp_dir):
        """Test error when output file exists"""
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        output_path.touch()
        
        engine = BagEngine()
        result = await engine.filter_bag_async(
            input_path=input_path,
            topics=["/topic1"],
            output_path=output_path,
            overwrite=False
        )
        
        assert result.success is False
        assert "Output file exists" in result.error_message
    
    @pytest.mark.asyncio
    async def test_filter_bag_async_with_exception(self, temp_dir):
        """Test handling exceptions during filtering"""
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        
        mock_parser = Mock()
        mock_parser.filter_bag.side_effect = Exception("Filter error")
        
        with patch('roseApp.core.engine.create_best_parser', return_value=mock_parser):
            engine = BagEngine()
            result = await engine.filter_bag_async(
                input_path=input_path,
                topics=["/topic1"],
                output_path=output_path,
                overwrite=True
            )
            
            assert result.success is False
            assert "Filter error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_filter_multiple_bags_async(self, temp_dir):
        """Test filtering multiple bags concurrently"""
        bag1_path = temp_dir / "bag1.bag"
        bag2_path = temp_dir / "bag2.bag"
        bag1_path.touch()
        bag2_path.touch()
        
        mock_parser = Mock()
        mock_parser.filter_bag.return_value = "Filtering completed"
        
        config = FilterConfig(
            topics=["/topic1"],
            output_path=temp_dir,
            overwrite=True
        )
        
        with patch('roseApp.core.engine.create_best_parser', return_value=mock_parser):
            engine = BagEngine()
            results = await engine.filter_multiple_bags_async(
                input_paths=[bag1_path, bag2_path],
                config=config
            )
            
            assert len(results) == 2
            assert bag1_path in results
            assert bag2_path in results
            assert results[bag1_path].success is True
            assert results[bag2_path].success is True
    
    @pytest.mark.asyncio
    async def test_copy_bag_async(self, temp_dir):
        """Test async bag copying"""
        source_path = temp_dir / "source.bag"
        dest_path = temp_dir / "dest.bag"
        source_path.write_text("test bag content")
        
        engine = BagEngine()
        result = await engine.copy_bag_async(
            input_path=source_path,
            output_path=dest_path,
            overwrite=True
        )
        
        assert result.success is True
        assert dest_path.exists()
    
    @pytest.mark.asyncio
    async def test_validate_bag_async(self, temp_dir):
        """Test async bag validation"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        mock_parser = Mock()
        mock_parser.load_bag.return_value = (["/topic1"], {"topic1": "std_msgs/String"}, ((0, 0), (1, 0)))
        mock_parser.get_message_counts.return_value = {"topic1": 100}
        
        with patch('roseApp.core.engine.create_best_parser', return_value=mock_parser):
            engine = BagEngine()
            validation = await engine.validate_bag_async(bag_path)
            
            assert validation["valid"] is True
            assert validation["topic_count"] == 1
            assert validation["message_count"] == 100
    
    @pytest.mark.asyncio
    async def test_get_bag_statistics_async(self, temp_dir):
        """Test getting bag statistics async"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        mock_parser = Mock()
        mock_parser.load_bag.return_value = (["/topic1"], {"topic1": "std_msgs/String"}, ((0, 0), (1, 0)))
        mock_parser.get_topic_stats.return_value = {
            "/topic1": {"count": 100, "size": 1000, "avg_size": 10}
        }
        
        with patch('roseApp.core.engine.create_best_parser', return_value=mock_parser):
            engine = BagEngine()
            stats = await engine.get_bag_statistics_async(bag_path)
            
            assert "file_path" in stats
            assert "topics" in stats
            assert "/topic1" in stats["topics"]
            assert stats["topics"]["/topic1"]["message_count"] == 100
    
    def test_cleanup(self):
        """Test engine cleanup"""
        engine = BagEngine()
        engine.cleanup()
        # Should not raise any exceptions


class TestGlobalFunctions:
    """Test cases for global functions"""
    
    @pytest.mark.asyncio
    async def test_filter_bag_async_global(self, temp_dir):
        """Test global filter_bag_async function"""
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        
        mock_result = ProcessingResult(success=True, input_path=input_path)
        
        with patch('roseApp.core.engine.get_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.filter_bag_async.return_value = mock_result
            mock_get_engine.return_value = mock_engine
            
            result = await filter_bag_async(
                input_path=input_path,
                topics=["/topic1"],
                output_path=output_path
            )
            
            assert result == mock_result
    
    def test_get_engine(self):
        """Test global get_engine function"""
        engine1 = get_engine()
        engine2 = get_engine()
        
        assert engine1 is engine2  # Should return the same instance
    
    def test_cleanup_engine(self):
        """Test global cleanup function"""
        cleanup_engine()
        # Should not raise any exceptions