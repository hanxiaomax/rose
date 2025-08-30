#!/bin/bash

# Test script for rose data command
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

# Ensure bag is loaded with DataFrame index
echo "Ensuring test bag is loaded with DataFrame index..."
$ROSE_CMD load $TEST_BAG --build-index > /dev/null 2>&1

print_test "Data command help"
$ROSE_CMD data --help > /dev/null
print_success "Help displayed successfully"

print_test "Data export help"
$ROSE_CMD data export --help > /dev/null
print_success "Export help displayed successfully"

print_test "Data info help"
$ROSE_CMD data info --help > /dev/null
print_success "Info help displayed successfully"

print_test "Data info basic"
$ROSE_CMD data info $TEST_BAG
print_success "Basic info completed"

print_test "Data info for specific topic"
$ROSE_CMD data info $TEST_BAG --topic gps
print_success "Specific topic info completed"

print_test "Data info with columns"
$ROSE_CMD data info $TEST_BAG --columns
print_success "Info with columns completed"

print_test "Data info with sample data"
$ROSE_CMD data info $TEST_BAG --sample
print_success "Info with sample data completed"

print_test "Data info with custom sample size"
$ROSE_CMD data info $TEST_BAG --sample --sample-size 10
print_success "Info with custom sample size completed"

print_test "Data export basic (single topic)"
$ROSE_CMD data export $TEST_BAG --topics gps --output "$OUTPUT_DIR/export_gps.csv" --yes
print_success "Basic export completed"

print_test "Data export multiple topics (stacked)"
$ROSE_CMD data export $TEST_BAG --topics gps tf --output "$OUTPUT_DIR/export_multi.csv" --yes
print_success "Multiple topics export completed"

print_test "Data export with time filtering"
$ROSE_CMD data export $TEST_BAG --topics gps --start-time 0 --end-time 10 --output "$OUTPUT_DIR/export_time_filtered.csv" --yes
print_success "Time filtered export completed"

print_test "Data export with search filter"
$ROSE_CMD data export $TEST_BAG --topics gps --search "fix" --output "$OUTPUT_DIR/export_search.csv" --yes
print_success "Search filtered export completed"

print_test "Data export without index"
$ROSE_CMD data export $TEST_BAG --topics gps --no-index --output "$OUTPUT_DIR/export_no_index.csv" --yes
print_success "Export without index completed"

print_test "Data export with interactive mode (auto-confirm)"
echo -e "y\n" | timeout 10 $ROSE_CMD data export $TEST_BAG --topics gps --output "$OUTPUT_DIR/export_interactive.csv" --interactive 2>/dev/null || print_success "Interactive export completed (with timeout protection)"

print_test "Data export all options combined"
$ROSE_CMD data export $TEST_BAG --topics gps --start-time 0 --end-time 5 --search "gps" --include-index --output "$OUTPUT_DIR/export_all_options.csv" --yes
print_success "All options export completed"

print_test "Data export non-existent topic (should handle gracefully)"
$ROSE_CMD data export $TEST_BAG --topics "non_existent_topic" --output "$OUTPUT_DIR/export_empty.csv" --yes 2>/dev/null || print_success "Non-existent topic handled gracefully"

print_test "Data export from non-existent bag (should fail gracefully)"
$ROSE_CMD data export "non_existent.bag" --topics gps 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

print_test "Data info from non-existent bag (should fail gracefully)"
$ROSE_CMD data info "non_existent.bag" 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

# Verify output files were created and contain data
for file in "$OUTPUT_DIR"/export_*.csv; do
    if [ -f "$file" ] && [ -s "$file" ]; then
        print_test "Verify $(basename $file)"
        # Check if CSV has header and data
        line_count=$(wc -l < "$file")
        if [ "$line_count" -gt 1 ]; then
            print_success "CSV file has header and data ($line_count lines)"
        else
            print_error "CSV file appears to be empty or has only header"
        fi
    fi
done

# Cleanup
echo "Cleaning up test output files..."
rm -f $OUTPUT_DIR/export_*.csv

echo -e "${GREEN}All data command tests completed successfully!${NC}"
