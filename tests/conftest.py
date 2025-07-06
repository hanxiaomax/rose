"""
Pytest configuration and shared fixtures for Rose ROS Bag Tool tests
"""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Test data constants
TEST_TOPICS = ["/test_topic1", "/test_topic2", "/diagnostics", "/rosout"]
TEST_MESSAGE_TYPES = {
    "/test_topic1": "std_msgs/String",
    "/test_topic2": "geometry_msgs/Twist", 
    "/diagnostics": "diagnostic_msgs/DiagnosticArray",
    "/rosout": "rosgraph_msgs/Log"
}

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir

@pytest.fixture
def mock_bag_data():
    """Mock bag data for testing"""
    return {
        'topics': TEST_TOPICS,
        'connections': TEST_MESSAGE_TYPES,
        'message_count': 1000
    }

@pytest.fixture
def test_bag_file(temp_dir):
    """Create a test bag file path"""
    bag_path = os.path.join(temp_dir, "test.bag")
    Path(bag_path).touch()
    return bag_path
