#!/usr/bin/env python3
"""
Test runner for roseApp core modules
"""

import sys
import os
import pytest
from pathlib import Path


def run_all_tests():
    """Run all tests for roseApp core modules"""
    
    # Change to tests directory
    tests_dir = Path(__file__).parent
    os.chdir(tests_dir)
    
    # Test configuration
    test_args = [
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--color=yes",  # Color output
        "--cov=../core",  # Coverage for core modules
        "--cov-report=term-missing",  # Terminal report with missing lines
        "--cov-report=html:htmlcov",  # HTML coverage report
        "--asyncio-mode=auto",  # Auto-detect async tests
    ]
    
    # Run tests
    exit_code = pytest.main(test_args)
    return exit_code


def run_specific_test(test_file):
    """Run specific test file"""
    
    tests_dir = Path(__file__).parent
    os.chdir(tests_dir)
    
    if not test_file.endswith('.py'):
        test_file += '.py'
    
    test_path = tests_dir / test_file
    if not test_path.exists():
        print(f"Test file {test_file} not found!")
        return 1
    
    test_args = [
        "-v",
        "--tb=short",
        "--color=yes",
        str(test_path)
    ]
    
    exit_code = pytest.main(test_args)
    return exit_code


def run_fast_tests():
    """Run only fast tests (unit tests)"""
    
    tests_dir = Path(__file__).parent
    os.chdir(tests_dir)
    
    test_args = [
        "-v",
        "--tb=short",
        "--color=yes",
        "-m", "not slow and not integration and not requires_ros"
    ]
    
    exit_code = pytest.main(test_args)
    return exit_code


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run roseApp tests")
    parser.add_argument("--file", help="Run specific test file")
    parser.add_argument("--fast", action="store_true", help="Run only fast tests")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    
    args = parser.parse_args()
    
    print("🧪 Running roseApp core module tests...")
    print("=" * 50)
    
    if args.file:
        print(f"Running specific test: {args.file}")
        exit_code = run_specific_test(args.file)
    elif args.fast:
        print("Running fast tests only...")
        exit_code = run_fast_tests()
    else:
        print("Running all tests...")
        exit_code = run_all_tests()
    
    print("=" * 50)
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ Tests failed with exit code {exit_code}")
    
    sys.exit(exit_code)