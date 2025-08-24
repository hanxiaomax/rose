"""
Pytest configuration and shared fixtures for roseApp tests
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow tests"
    )
    config.addinivalue_line(
        "markers", "requires_ros: marks tests that require ROS dependencies"
    )


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_bag_file(temp_dir):
    """Create a mock bag file for testing"""
    bag_path = temp_dir / "test.bag"
    bag_path.touch()
    return bag_path


@pytest.fixture
def demo_bag_path():
    """Provide path to real demo.bag file for integration tests"""
    demo_path = Path(__file__).parent / "demo.bag"
    if not demo_path.exists():
        pytest.skip("demo.bag file not found - integration tests require demo.bag")
    return demo_path


@pytest.fixture
def sample_bag_info():
    """Sample bag info dictionary for testing"""
    return {
        "file_path": "/tmp/test.bag",
        "file_name": "test.bag",
        "file_size": 1024000,
        "topics_count": 2,
        "total_messages": 150,
        "duration_seconds": 10.5,
        "analysis_time": 0.123,
        "cached": False
    }


@pytest.fixture
def sample_topics():
    """Sample topics list for testing"""
    return [
        {
            "name": "/topic1",
            "message_type": "std_msgs/String",
            "message_count": 100,
            "frequency": 10.0,
            "field_paths": ["data"]
        },
        {
            "name": "/topic2", 
            "message_type": "geometry_msgs/Twist",
            "message_count": 50,
            "frequency": 5.0,
            "field_paths": ["linear.x", "linear.y", "linear.z", "angular.x", "angular.y", "angular.z"]
        }
    ]


@pytest.fixture
def sample_analysis_result(sample_bag_info, sample_topics):
    """Sample analysis result for testing"""
    return {
        "bag_info": sample_bag_info,
        "topics": sample_topics,
        "field_analysis": {
            "/topic1": {
                "message_type": "std_msgs/String",
                "field_paths": ["data"],
                "samples_analyzed": 3
            },
            "/topic2": {
                "message_type": "geometry_msgs/Twist", 
                "field_paths": ["linear.x", "linear.y", "linear.z", "angular.x", "angular.y", "angular.z"],
                "samples_analyzed": 3
            }
        },
        "cache_stats": {
            "total_requests": 10,
            "hit_rate": 0.8
        }
    }