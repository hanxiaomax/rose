#!/usr/bin/env python3
"""
Test script to verify rosbags migration functionality
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import (
    check_compression_availability, 
    get_available_compression_types,
    validate_compression_type,
    check_rosbags_availability,
    get_preferred_parser_type
)
from roseApp.core.BagManager import BagManager


def test_compression_availability():
    """Test compression availability detection"""
    print("=" * 60)
    print("Testing compression availability...")
    print("=" * 60)
    
    available = check_compression_availability()
    print(f"Available compressions: {available}")
    
    available_types = get_available_compression_types()
    print(f"Available compression types: {available_types}")
    
    # Test validation
    for compression in ['none', 'bz2', 'lz4']:
        is_valid, error_msg = validate_compression_type(compression)
        print(f"Compression '{compression}': {'✓' if is_valid else '✗'} {error_msg}")
    
    return available_types


def test_rosbags_availability():
    """Test rosbags library availability"""
    print("\n" + "=" * 60)
    print("Testing rosbags availability...")
    print("=" * 60)
    
    rosbags_available = check_rosbags_availability()
    print(f"rosbags available: {'✓' if rosbags_available else '✗'}")
    
    preferred_parser = get_preferred_parser_type()
    print(f"Preferred parser type: {preferred_parser}")
    
    return rosbags_available, preferred_parser


def test_parser_creation():
    """Test parser creation and functionality"""
    print("\n" + "=" * 60)
    print("Testing parser creation...")
    print("=" * 60)
    
    # Test creating different parser types
    parsers = {}
    
    try:
        parsers['python'] = create_parser(ParserType.PYTHON)
        print("✓ Python parser created successfully")
    except Exception as e:
        print(f"✗ Python parser creation failed: {e}")
    
    try:
        parsers['rosbags'] = create_parser(ParserType.ROSBAGS)
        print("✓ rosbags parser created successfully")
    except Exception as e:
        print(f"✗ rosbags parser creation failed: {e}")
    
    return parsers


def test_bag_manager():
    """Test BagManager auto-selection"""
    print("\n" + "=" * 60)
    print("Testing BagManager auto-selection...")
    print("=" * 60)
    
    try:
        # Test default constructor (should auto-select best parser)
        bag_manager = BagManager()
        parser_type = bag_manager.get_parser_type()
        print(f"✓ BagManager created with parser type: {parser_type}")
        
        # Test compression validation
        try:
            bag_manager.set_compression_type('none')
            print("✓ Compression 'none' accepted")
        except Exception as e:
            print(f"✗ Compression 'none' rejected: {e}")
        
        try:
            bag_manager.set_compression_type('bz2')
            print("✓ Compression 'bz2' accepted")
        except Exception as e:
            print(f"✗ Compression 'bz2' rejected: {e}")
        
        try:
            bag_manager.set_compression_type('lz4')
            print("✓ Compression 'lz4' accepted")
        except Exception as e:
            print(f"✗ Compression 'lz4' rejected: {e}")
        
        return bag_manager
        
    except Exception as e:
        print(f"✗ BagManager creation failed: {e}")
        return None


def test_with_sample_bag():
    """Test functionality with a sample bag file if available"""
    print("\n" + "=" * 60)
    print("Testing with sample bag file...")
    print("=" * 60)
    
    # Look for sample bag files
    sample_bags = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.bag'):
                sample_bags.append(os.path.join(root, file))
    
    if not sample_bags:
        print("⚠ No sample bag files found for testing")
        return
    
    sample_bag = sample_bags[0]
    print(f"Using sample bag: {sample_bag}")
    
    # Test with rosbags parser if available
    try:
        parser = create_parser(ParserType.ROSBAGS)
        print("Testing with rosbags parser...")
        
        # Test load_bag
        topics, connections, time_range = parser.load_bag(sample_bag)
        print(f"✓ Loaded bag: {len(topics)} topics, time range: {time_range}")
        
        # Test inspect_bag
        inspection = parser.inspect_bag(sample_bag)
        print(f"✓ Inspection complete (first 200 chars): {inspection[:200]}...")
        
        # Test get_message_counts
        counts = parser.get_message_counts(sample_bag)
        print(f"✓ Message counts: {sum(counts.values())} total messages")
        
    except Exception as e:
        print(f"✗ rosbags parser test failed: {e}")
        
    # Test with python parser as fallback
    try:
        parser = create_parser(ParserType.PYTHON)
        print("Testing with python parser...")
        
        # Test load_bag
        topics, connections, time_range = parser.load_bag(sample_bag)
        print(f"✓ Loaded bag: {len(topics)} topics, time range: {time_range}")
        
    except Exception as e:
        print(f"✗ python parser test failed: {e}")


def test_compression_with_rosbags():
    """Test compression functionality with rosbags"""
    print("\n" + "=" * 60)
    print("Testing compression with rosbags...")
    print("=" * 60)
    
    if not check_rosbags_availability():
        print("⚠ rosbags not available, skipping compression test")
        return
    
    try:
        from rosbags.rosbag1 import Writer as Rosbag1Writer
        from pathlib import Path
        
        # Test creating writers with different compression types
        with tempfile.TemporaryDirectory() as temp_dir:
            for compression in ['none', 'bz2', 'lz4']:
                try:
                    test_path = Path(temp_dir) / f"test_{compression}.bag"
                    writer = Rosbag1Writer(test_path)
                    
                    # Set compression if not none
                    if compression != 'none':
                        if compression == 'bz2':
                            writer.set_compression(writer.CompressionFormat.BZ2)
                        elif compression == 'lz4':
                            writer.set_compression(writer.CompressionFormat.LZ4)
                    
                    # Test opening and closing
                    writer.open()
                    writer.close()
                    
                    print(f"✓ Successfully created writer with {compression} compression")
                except Exception as e:
                    print(f"✗ Failed to create writer with {compression} compression: {e}")
    
    except Exception as e:
        print(f"✗ rosbags compression test failed: {e}")


def main():
    """Run all tests"""
    print("🌹 Rose ROS Bag Tool - rosbags Migration Test")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    available_compressions = test_compression_availability()
    rosbags_available, preferred_parser = test_rosbags_availability()
    parsers = test_parser_creation()
    bag_manager = test_bag_manager()
    
    test_with_sample_bag()
    test_compression_with_rosbags()
    
    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION TEST SUMMARY")
    print("=" * 60)
    print(f"rosbags available: {'✓' if rosbags_available else '✗'}")
    print(f"Preferred parser: {preferred_parser}")
    print(f"Available compressions: {available_compressions}")
    print(f"LZ4 support: {'✓' if 'lz4' in available_compressions else '✗'}")
    print(f"BagManager working: {'✓' if bag_manager else '✗'}")
    
    if rosbags_available and 'lz4' in available_compressions:
        print("\n🎉 Migration SUCCESS: Full rosbags support with LZ4 compression!")
    elif rosbags_available:
        print("\n✅ Migration PARTIAL: rosbags support available, but LZ4 not working")
    else:
        print("\n⚠️ Migration FALLBACK: Using legacy rosbag parser")
    
    print("\nTo test the full system:")
    print("1. Use the CLI tool: python -m roseApp.cli.cli_tool")
    print("2. Use the filter command: python -m roseApp.cli.filter --help")
    print("3. Use the TUI: python -m roseApp.tui.main")


if __name__ == "__main__":
    main() 