"""
Test cases for BagManager module
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from roseApp.core.BagManager import (
    BagManager, BagStatus, Bag, BagInfo, FilterConfig, CompressionType
)


class TestBagInfo:
    """Test cases for BagInfo class"""
    
    def test_bag_info_creation(self):
        """Test basic BagInfo creation"""
        info = BagInfo(
            time_range=((123456789, 0), (123456790, 0)),
            init_time_range=((123456789, 0), (123456790, 0)),
            size=1024000,
            topics={"/topic1", "/topic2"},
            size_after_filter=1024000
        )
        
        assert info.size == 1024000
        assert len(info.topics) == 2
        assert info.size_str == "976.56KB"
    
    def test_time_range_str(self):
        """Test time range string formatting"""
        info = BagInfo(
            time_range=((123456789, 0), (123456790, 0)),
            init_time_range=((123456789, 0), (123456790, 0)),
            size=1000,
            topics={"/topic1"},
            size_after_filter=1000
        )
        
        start_str, end_str = info.time_range_str
        assert "09/02/73 03:46:29" in start_str
        assert "09/02/73 03:46:30" in end_str
    
    def test_size_formatting(self):
        """Test size formatting in different units"""
        info = BagInfo(
            time_range=((0, 0), (1, 0)),
            init_time_range=((0, 0), (1, 0)),
            size=500,
            topics=set(),
            size_after_filter=500
        )
        assert info.size_str == "500.00B"
        
        info.size = 1024 * 1024
        assert info.size_str == "1.00MB"


class TestBag:
    """Test cases for Bag class"""
    
    def test_bag_creation(self):
        """Test basic Bag creation"""
        path = Path("/tmp/test.bag")
        info = BagInfo(
            time_range=((0, 0), (1, 0)),
            init_time_range=((0, 0), (1, 0)),
            size=1000,
            topics={"/topic1"},
            size_after_filter=1000
        )
        
        bag = Bag(path, info)
        assert bag.path == path
        assert bag.status == BagStatus.IDLE
        assert len(bag.selected_topics) == 0
    
    def test_bag_topic_selection(self):
        """Test topic selection functionality"""
        path = Path("/tmp/test.bag")
        info = BagInfo(
            time_range=((0, 0), (1, 0)),
            init_time_range=((0, 0), (1, 0)),
            size=1000,
            topics={"/topic1", "/topic2"},
            size_after_filter=1000
        )
        
        bag = Bag(path, info)
        bag.set_selected_topics({"/topic1"})
        assert len(bag.selected_topics) == 1
        assert "/topic1" in bag.selected_topics
    
    def test_filter_config_generation(self):
        """Test filter config generation"""
        path = Path("/tmp/test.bag")
        info = BagInfo(
            time_range=((0, 0), (1, 0)),
            init_time_range=((0, 0), (1, 0)),
            size=1000,
            topics={"/topic1", "/topic2"},
            size_after_filter=1000
        )
        
        bag = Bag(path, info)
        bag.set_selected_topics({"/topic1"})
        
        config = bag.get_filter_config()
        assert config.compression == "none"
        assert len(config.topic_list) == 1
        assert "/topic1" in config.topic_list
    
    def test_bag_status_management(self):
        """Test bag status management"""
        path = Path("/tmp/test.bag")
        info = BagInfo(
            time_range=((0, 0), (1, 0)),
            init_time_range=((0, 0), (1, 0)),
            size=1000,
            topics=set(),
            size_after_filter=1000
        )
        
        bag = Bag(path, info)
        assert bag.status == BagStatus.IDLE
        
        bag.set_status(BagStatus.SUCCESS)
        assert bag.status == BagStatus.SUCCESS
        
        bag.set_status(BagStatus.ERROR)
        assert bag.status == BagStatus.ERROR


class TestBagManager:
    """Test cases for BagManager class"""
    
    def test_bag_manager_initialization(self):
        """Test basic BagManager initialization"""
        manager = BagManager()
        assert len(manager.bags) == 0
        assert len(manager.selected_topics) == 0
        assert manager.compression == CompressionType.NONE.value
    
    def test_bag_manager_with_parser(self, mock_parser):
        """Test BagManager initialization with custom parser"""
        manager = BagManager(parser=mock_parser)
        assert manager._parser == mock_parser
    
    def test_load_bag(self, temp_dir, mock_parser):
        """Test loading a bag file"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(bag_path)
            
            assert len(manager.bags) == 1
            assert bag_path in manager.bags
            assert len(manager.selected_topics) == 0
    
    def test_load_duplicate_bag(self, temp_dir, mock_parser):
        """Test loading duplicate bag file raises error"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(bag_path)
            
            with pytest.raises(ValueError, match="already exists"):
                manager.load_bag(bag_path)
    
    def test_unload_bag(self, temp_dir, mock_parser):
        """Test unloading a bag file"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(bag_path)
            assert len(manager.bags) == 1
            
            manager.unload_bag(bag_path)
            assert len(manager.bags) == 0
    
    def test_unload_nonexistent_bag(self, temp_dir):
        """Test unloading nonexistent bag raises error"""
        bag_path = temp_dir / "nonexistent.bag"
        manager = BagManager()
        
        with pytest.raises(KeyError, match="not found"):
            manager.unload_bag(bag_path)
    
    def test_clear_bags(self, temp_dir, mock_parser):
        """Test clearing all bags"""
        bag1_path = temp_dir / "test1.bag"
        bag2_path = temp_dir / "test2.bag"
        bag1_path.touch()
        bag2_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(bag1_path)
            manager.load_bag(bag2_path)
            assert len(manager.bags) == 2
            
            manager.clear_bags()
            assert len(manager.bags) == 0
    
    def test_topic_selection(self, temp_dir, mock_parser):
        """Test topic selection functionality"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(bag_path)
            
            # Test topic selection
            manager.select_topic("/topic1")
            assert "/topic1" in manager.selected_topics
            
            # Test topic deselection
            manager.deselect_topic("/topic1")
            assert "/topic1" not in manager.selected_topics
            
            # Test clear all topics
            manager.select_topic("/topic1")
            manager.select_topic("/topic2")
            assert len(manager.selected_topics) == 2
            
            manager.clear_selected_topics()
            assert len(manager.selected_topics) == 0
    
    def test_get_common_topics(self, temp_dir, mock_parser):
        """Test getting common topics across bags"""
        bag1_path = temp_dir / "test1.bag"
        bag2_path = temp_dir / "test2.bag"
        bag1_path.touch()
        bag2_path.touch()
        
        def mock_load_bag(path):
            if "test1" in str(path):
                return ["/topic1", "/topic2"], {}, ((0, 0), (1, 0))
            else:
                return ["/topic2", "/topic3"], {}, ((0, 0), (1, 0))
        
        mock_parser.load_bag.side_effect = mock_load_bag
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(bag1_path)
            manager.load_bag(bag2_path)
            
            common_topics = manager.get_common_topics()
            assert "/topic2" in common_topics
            assert len(common_topics) == 1
    
    def test_get_topic_summary(self, temp_dir, mock_parser):
        """Test getting topic summary"""
        bag1_path = temp_dir / "test1.bag"
        bag2_path = temp_dir / "test2.bag"
        bag1_path.touch()
        bag2_path.touch()
        
        def mock_load_bag(path):
            if "test1" in str(path):
                return ["/topic1", "/topic2"], {}, ((0, 0), (1, 0))
            else:
                return ["/topic2", "/topic3"], {}, ((0, 0), (1, 0))
        
        mock_parser.load_bag.side_effect = mock_load_bag
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(bag1_path)
            manager.load_bag(bag2_path)
            
            summary = manager.get_topic_summary()
            assert summary["/topic1"] == 1
            assert summary["/topic2"] == 2
            assert summary["/topic3"] == 1
    
    def test_compression_type_management(self):
        """Test compression type management"""
        manager = BagManager()
        
        # Test valid compression types
        manager.set_compression_type("bz2")
        assert manager.get_compression_type() == "bz2"
        
        manager.set_compression_type("lz4")
        assert manager.get_compression_type() == "lz4"
        
        manager.set_compression_type("none")
        assert manager.get_compression_type() == "none"
        
        # Test invalid compression type
        with pytest.raises(ValueError):
            manager.set_compression_type("invalid")
    
    def test_callbacks(self, temp_dir, mock_parser):
        """Test callback functionality"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        callback_called = False
        
        def bag_mutate_callback():
            nonlocal callback_called
            callback_called = True
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.set_bag_mutate_callback(bag_mutate_callback)
            
            manager.load_bag(bag_path)
            assert callback_called
    
    def test_get_single_bag(self, temp_dir, mock_parser):
        """Test getting single bag"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            assert manager.get_single_bag() is None
            
            manager.load_bag(bag_path)
            single_bag = manager.get_single_bag()
            assert single_bag is not None
            assert single_bag.path == bag_path
    
    def test_is_bag_loaded(self, temp_dir, mock_parser):
        """Test checking if bag is loaded"""
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            assert not manager.is_bag_loaded(bag_path)
            
            manager.load_bag(bag_path)
            assert manager.is_bag_loaded(bag_path)
    
    def test_filter_bag(self, temp_dir, mock_parser):
        """Test filtering a bag"""
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        output_path.touch()
        
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1024000
            
            manager = BagManager(parser=mock_parser)
            manager.load_bag(input_path)
            
            config = FilterConfig(
                time_range=((0, 0), (1, 0)),
                topic_list=["/topic1"],
                compression="bz2"
            )
            
            manager.filter_bag(input_path, config, output_path)
            
            assert manager.bags[input_path].status == BagStatus.SUCCESS
    
    def test_parser_type_detection(self, mock_parser):
        """Test parser type detection"""
        with patch.object(mock_parser, '__class__') as mock_class:
            mock_class.__name__ = 'RosbagsBagParser'
            manager = BagManager(parser=mock_parser)
            assert manager.get_parser_type() == 'rosbags'