#!/bin/bash

# Test script for rose inspect command
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

print_test "Inspect command help"
$ROSE_CMD inspect --help > /dev/null
print_success "Help displayed successfully"

print_test "Basic inspect"
$ROSE_CMD inspect $TEST_BAG
print_success "Basic inspect completed"

print_test "Inspect with verbose output"
$ROSE_CMD inspect $TEST_BAG --verbose
print_success "Verbose inspect completed"

print_test "Inspect with debug output"
$ROSE_CMD inspect $TEST_BAG --debug
print_success "Debug inspect completed"

print_test "Inspect specific topic"
$ROSE_CMD inspect $TEST_BAG --topics gps
print_success "Specific topic inspect completed"

print_test "Inspect multiple topics"
$ROSE_CMD inspect $TEST_BAG --topics gps --topics tf
print_success "Multiple topics inspect completed"

print_test "Inspect with field analysis"
$ROSE_CMD inspect $TEST_BAG --show-fields
print_success "Field analysis completed"

print_test "Inspect with sorting by name"
$ROSE_CMD inspect $TEST_BAG --sort name
print_success "Sort by name completed"

print_test "Inspect with sorting by count"
$ROSE_CMD inspect $TEST_BAG --sort count
print_success "Sort by count completed"

print_test "Inspect with sorting by frequency"
$ROSE_CMD inspect $TEST_BAG --sort frequency
print_success "Sort by frequency completed"

print_test "Inspect with sorting by size"
$ROSE_CMD inspect $TEST_BAG --sort size
print_success "Sort by size completed"

print_test "Inspect with reverse sort"
$ROSE_CMD inspect $TEST_BAG --sort name --reverse
print_success "Reverse sort completed"

print_test "Inspect with output to file"
$ROSE_CMD inspect $TEST_BAG --output "$OUTPUT_DIR/inspect_output.txt"
print_success "Output to file completed"

print_test "Inspect with all options combined"
$ROSE_CMD inspect $TEST_BAG --topics gps --show-fields --sort frequency --reverse --verbose --output "$OUTPUT_DIR/inspect_all_options.txt"
print_success "All options combined completed"

print_test "Inspect non-existent topic (should show no results)"
$ROSE_CMD inspect $TEST_BAG --topics "non_existent_topic"
print_success "Non-existent topic handled gracefully"

print_test "Inspect non-existent bag (should fail gracefully)"
$ROSE_CMD inspect "non_existent.bag" 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

print_test "Inspect with invalid sort option (should fail)"
$ROSE_CMD inspect $TEST_BAG --sort invalid_sort 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

# Verify output files were created
if [ -f "$OUTPUT_DIR/inspect_output.txt" ]; then
    print_test "Output file verification"
    if [ -s "$OUTPUT_DIR/inspect_output.txt" ]; then
        print_success "Output file created and contains data"
    else
        print_error "Output file is empty"
    fi
fi

# Cleanup
echo "Cleaning up test output files..."
rm -f $OUTPUT_DIR/inspect_*.txt

echo -e "${GREEN}All inspect command tests completed successfully!${NC}"

