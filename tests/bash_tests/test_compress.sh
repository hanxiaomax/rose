#!/bin/bash

# Test script for rose compress command
# Tests various options and combinations

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
TEST_BAG="roseApp/tests/demo3.bag"
ROSE_CMD="python -m roseApp.rose"
OUTPUT_DIR="tests/bash_tests/output"

# Helper functions
print_test() {
    echo -e "${YELLOW}=== Testing: $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Setup
mkdir -p $OUTPUT_DIR
cd /workspaces/rose

# Ensure bag is loaded first
echo "Ensuring test bag is loaded..."
$ROSE_CMD load $TEST_BAG > /dev/null 2>&1

print_test "Compress command help"
$ROSE_CMD compress --help > /dev/null
print_success "Help displayed successfully"

print_test "Compress dry-run"
$ROSE_CMD compress $TEST_BAG --dry-run
print_success "Dry-run completed"

print_test "Compress with default LZ4"
$ROSE_CMD compress $TEST_BAG --output "$OUTPUT_DIR/test_lz4.bag" --yes
print_success "LZ4 compression completed"

print_test "Compress with BZ2"
$ROSE_CMD compress $TEST_BAG --compression bz2 --output "$OUTPUT_DIR/test_bz2.bag" --yes
print_success "BZ2 compression completed"

print_test "Compress with explicit LZ4"
$ROSE_CMD compress $TEST_BAG --compression lz4 --output "$OUTPUT_DIR/test_lz4_explicit.bag" --yes
print_success "Explicit LZ4 compression completed"

print_test "Compress with verbose output"
$ROSE_CMD compress $TEST_BAG --compression lz4 --output "$OUTPUT_DIR/test_verbose.bag" --verbose --yes
print_success "Verbose compression completed"

print_test "Compress with validation"
$ROSE_CMD compress $TEST_BAG --compression lz4 --output "$OUTPUT_DIR/test_validated.bag" --validate --yes
print_success "Compression with validation completed"

print_test "Compress with workers option"
$ROSE_CMD compress $TEST_BAG --compression lz4 --output "$OUTPUT_DIR/test_workers.bag" --workers 2 --yes
print_success "Multi-worker compression completed"

print_test "Compress with pattern in output filename"
$ROSE_CMD compress $TEST_BAG --compression bz2 --output "$OUTPUT_DIR/{input}_{compression}.bag" --yes
print_success "Pattern output filename completed"

print_test "Compress with all options combined"
$ROSE_CMD compress $TEST_BAG --compression lz4 --output "$OUTPUT_DIR/test_all_options.bag" --validate --verbose --workers 1 --yes
print_success "All options combined completed"

print_test "Compress non-existent bag (should fail gracefully)"
$ROSE_CMD compress "non_existent.bag" --compression lz4 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

print_test "Compress with invalid compression type (should fail)"
$ROSE_CMD compress $TEST_BAG --compression invalid_type 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

# Test file size comparison
if [ -f "$OUTPUT_DIR/test_lz4.bag" ] && [ -f "$OUTPUT_DIR/test_bz2.bag" ]; then
    print_test "File size comparison"
    LZ4_SIZE=$(stat -c%s "$OUTPUT_DIR/test_lz4.bag" 2>/dev/null || stat -f%z "$OUTPUT_DIR/test_lz4.bag" 2>/dev/null)
    BZ2_SIZE=$(stat -c%s "$OUTPUT_DIR/test_bz2.bag" 2>/dev/null || stat -f%z "$OUTPUT_DIR/test_bz2.bag" 2>/dev/null)
    echo "LZ4 compressed size: $LZ4_SIZE bytes"
    echo "BZ2 compressed size: $BZ2_SIZE bytes"
    print_success "File size comparison completed"
fi

# Cleanup
echo "Cleaning up test output files..."
rm -f $OUTPUT_DIR/test_*.bag

echo -e "${GREEN}All compress command tests completed successfully!${NC}"
