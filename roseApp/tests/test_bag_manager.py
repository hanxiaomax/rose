"""
Test cases for BagManager module using real demo.bag file
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from roseApp.core.BagManager import (
    BagManager, BagStatus, Bag, BagInfo, FilterConfig, CompressionType
)

# Path to real demo.bag file
DEMO_BAG_PATH = Path(__file__).parent / "demo.bag"


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
        assert info.size_str == "1000.00KB"
    
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
        assert "73/11/30 05:33:09" in start_str
        assert "73/11/30 05:33:10" in end_str
    
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


@pytest.fixture
def demo_bag_path():
    """Provide path to real demo.bag file"""
    if not DEMO_BAG_PATH.exists():
        pytest.skip("demo.bag file not found")
    return DEMO_BAG_PATH


class TestBagManager:
    """Test cases for BagManager class using real demo.bag file"""
    
    def test_bag_manager_initialization(self):
        """Test basic BagManager initialization"""
        manager = BagManager()
        assert len(manager.bags) == 0
        assert len(manager.selected_topics) == 0
        assert manager.compression == CompressionType.NONE.value
    
    def test_bag_manager_with_parser(self):
        """Test BagManager initialization with real parser"""
        from roseApp.core.parser import RosbagsBagParser
        parser = RosbagsBagParser()
        manager = BagManager(parser=parser)
        assert manager._parser == parser
    
    def test_load_bag(self, demo_bag_path):
        """Test loading real demo.bag file"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        assert len(manager.bags) == 1
        assert demo_bag_path in manager.bags
        assert len(manager.selected_topics) == 0
        
        # Verify bag was loaded correctly
        bag = manager.bags[demo_bag_path]
        assert bag.path == demo_bag_path
        assert bag.status == BagStatus.IDLE
        assert len(bag.info.topics) > 0  # Should have actual topics
    
    def test_load_duplicate_bag(self, demo_bag_path):
        """Test loading duplicate bag file raises error"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        with pytest.raises(ValueError, match="already exists"):
            manager.load_bag(demo_bag_path)
    
    def test_unload_bag(self, demo_bag_path):
        """Test unloading a bag file"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        assert len(manager.bags) == 1
        
        manager.unload_bag(demo_bag_path)
        assert len(manager.bags) == 0
    
    def test_unload_nonexistent_bag(self, temp_dir):
        """Test unloading nonexistent bag raises error"""
        bag_path = temp_dir / "nonexistent.bag"
        manager = BagManager()
        
        with pytest.raises(KeyError, match="not found"):
            manager.unload_bag(bag_path)
    
    def test_clear_bags(self, demo_bag_path):
        """Test clearing all bags"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        assert len(manager.bags) == 1
        
        manager.clear_bags()
        assert len(manager.bags) == 0
    
    def test_topic_selection(self, demo_bag_path):
        """Test topic selection functionality with real bag"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        # Get actual topics from the bag
        bag = manager.bags[demo_bag_path]
        actual_topics = list(bag.info.topics)
        assert len(actual_topics) > 0
        
        test_topic = actual_topics[0]
        
        # Test topic selection
        manager.select_topic(test_topic)
        assert test_topic in manager.selected_topics
        
        # Test topic deselection
        manager.deselect_topic(test_topic)
        assert test_topic not in manager.selected_topics
        
        # Test clear all topics
        manager.select_topic(test_topic)
        assert len(manager.selected_topics) == 1
        
        manager.clear_selected_topics()
        assert len(manager.selected_topics) == 0
    
    def test_get_common_topics(self, demo_bag_path):
        """Test getting common topics with single bag"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        common_topics = manager.get_common_topics()
        # With single bag, all topics are "common"
        assert len(common_topics) > 0
    
    def test_get_topic_summary(self, demo_bag_path):
        """Test getting topic summary from real bag"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        summary = manager.get_topic_summary()
        assert len(summary) > 0
        
        # Verify actual topics exist in summary
        bag = manager.bags[demo_bag_path]
        for topic in bag.info.topics:
            assert topic in summary
            assert summary[topic] == 1  # Single bag, each topic appears once
    
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
    
    def test_callbacks(self, demo_bag_path):
        """Test callback functionality with real bag"""
        callback_called = False
        
        def bag_mutate_callback():
            nonlocal callback_called
            callback_called = True
        
        manager = BagManager()
        manager.set_bag_mutate_callback(bag_mutate_callback)
        
        manager.load_bag(demo_bag_path)
        assert callback_called
    
    def test_get_single_bag(self, demo_bag_path):
        """Test getting single bag with real data"""
        manager = BagManager()
        assert manager.get_single_bag() is None
        
        manager.load_bag(demo_bag_path)
        single_bag = manager.get_single_bag()
        assert single_bag is not None
        assert single_bag.path == demo_bag_path
    
    def test_is_bag_loaded(self, demo_bag_path):
        """Test checking if bag is loaded with real data"""
        manager = BagManager()
        assert not manager.is_bag_loaded(demo_bag_path)
        
        manager.load_bag(demo_bag_path)
        assert manager.is_bag_loaded(demo_bag_path)
    
    def test_filter_bag(self, demo_bag_path, tmp_path):
        """Test filtering a real bag file"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        # Get actual topics from the bag
        bag = manager.bags[demo_bag_path]
        actual_topics = list(bag.info.topics)
        assert len(actual_topics) > 0
        
        test_topic = actual_topics[0]
        output_path = tmp_path / "filtered.bag"
        
        config = FilterConfig(
            time_range=bag.info.time_range,
            topic_list=[test_topic],
            compression="none"
        )
        
        manager.filter_bag(demo_bag_path, config, output_path)
        
        assert manager.bags[demo_bag_path].status == BagStatus.SUCCESS
        assert output_path.exists()
    
    def test_parser_type_detection(self):
        """Test parser type detection with real parser"""
        manager = BagManager()
        parser_type = manager.get_parser_type()
        assert parser_type in ['rosbags', 'legacy']

    def test_real_bag_analysis(self, demo_bag_path):
        """Test comprehensive analysis of real demo.bag file"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        # Verify bag loaded successfully
        assert len(manager.bags) == 1
        bag = manager.bags[demo_bag_path]
        
        # Check bag info is populated
        assert bag.info.size > 0
        assert len(bag.info.topics) > 0
        assert bag.info.time_range[0] != bag.info.time_range[1]  # Has time range
        
        # Test topic selection with actual topics
        topics = list(bag.info.topics)
        test_topic = topics[0]
        
        manager.select_topic(test_topic)
        assert test_topic in manager.selected_topics
        
        # Test getting common topics
        common_topics = manager.get_common_topics()
        assert len(common_topics) > 0
        
        # Test topic summary
        summary = manager.get_topic_summary()
        assert len(summary) > 0
        assert test_topic in summary

    def test_bag_info_integrity(self, demo_bag_path):
        """Test that BagInfo contains accurate data from real bag"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        bag = manager.bags[demo_bag_path]
        info = bag.info
        
        # Verify all fields are populated
        assert info.size > 0
        assert len(info.topics) > 0
        assert info.time_range[0] is not None
        assert info.time_range[1] is not None
        assert info.init_time_range[0] is not None
        assert info.init_time_range[1] is not None
        assert info.size_str.endswith(('B', 'KB', 'MB', 'GB'))
        
        # Verify topics are actual strings
        for topic in info.topics:
            assert isinstance(topic, str)
            assert topic.startswith('/')

    def test_multiple_bags_real_data(self, demo_bag_path, tmp_path):
        """Test managing multiple real bags"""
        manager = BagManager()
        
        # Load the same bag twice with different names to simulate multiple bags
        bag1_path = demo_bag_path
        bag2_path = tmp_path / "demo_copy.bag"
        
        # Copy demo.bag to create a second bag file
        import shutil
        shutil.copy2(bag1_path, bag2_path)
        
        manager.load_bag(bag1_path)
        manager.load_bag(bag2_path)
        
        assert len(manager.bags) == 2
        
        # Test common topics
        common_topics = manager.get_common_topics()
        assert len(common_topics) > 0
        
        # Test topic summary
        summary = manager.get_topic_summary()
        assert len(summary) > 0
        
        # Each topic should appear twice (once per bag)
        for topic, count in summary.items():
            assert count == 2
            
        # Clean up
        manager.clear_bags()
        assert len(manager.bags) == 0
        
        # Clean up copied file
        bag2_path.unlink(missing_ok=True)

    def test_filter_config_with_real_data(self, demo_bag_path, tmp_path):
        """Test creating filter config from real bag data"""
        manager = BagManager()
        manager.load_bag(demo_bag_path)
        
        bag = manager.bags[demo_bag_path]
        topics = list(bag.info.topics)
        
        # Test with real time range and topics
        config = FilterConfig(
            time_range=bag.info.time_range,
            topic_list=[topics[0]],
            compression="none"
        )
        
        assert config.time_range == bag.info.time_range
        assert len(config.topic_list) == 1
        assert config.topic_list[0] in topics
        assert config.compression == "none"