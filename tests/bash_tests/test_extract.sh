#!/bin/bash

# Smoke test for rose extract command
# Simple and direct testing

# Note: Not using set -e to allow error testing

# Load common functions
source "$(dirname "$0")/common_functions.sh"

# Parse command line arguments
parse_test_args "$@"

# Test configuration
ROSE_CMD="python -m roseApp.rose"
OUTPUT_DIR="tests/bash_tests/output"

# Setup
mkdir -p $OUTPUT_DIR
cd /workspaces/rose

# Show test configuration
show_test_config "Extract Command"

print_test "Extract command help"
run_cmd_silent $ROSE_CMD extract --help
print_success "Help works"

print_test "Extract dry-run"
run_cmd_silent $ROSE_CMD extract $TEST_BAG --dry-run
print_success "Dry-run works"

print_test "Extract with topics"
run_cmd_silent $ROSE_CMD extract $TEST_BAG --topics gps --output "$OUTPUT_DIR/test_extract.bag" --yes
print_success "Topic extraction works"

print_test "Extract with compression"
run_cmd_silent $ROSE_CMD extract $TEST_BAG --topics gps --compression lz4 --output "$OUTPUT_DIR/test_compressed.bag" --yes
print_success "Compression works"

print_test "Extract non-existent bag (error handling)"
run_cmd_expect_error $ROSE_CMD extract "non_existent.bag" --topics gps

# Cleanup
rm -f $OUTPUT_DIR/test_*.bag

echo -e "${GREEN}Extract command smoke tests passed!${NC}"

