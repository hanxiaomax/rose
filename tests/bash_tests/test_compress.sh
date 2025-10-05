#!/bin/bash

# Smoke test for rose compress command
# Simple and direct testing

# Note: Not using set -e to allow error testing

# Load common functions
source "$(dirname "$0")/common_functions.sh"

# Parse command line arguments
parse_test_args "$@"

# Show test configuration
show_test_config

OUTPUT_DIR="tests/bash_tests/output"

# Setup
mkdir -p $OUTPUT_DIR
cd /workspaces/rose

print_test "Compress command help"
run_cmd_silent "python -m roseApp.rose compress --help" "Help works" "Help failed"

print_test "Compress dry-run"
run_cmd_silent "python -m roseApp.rose compress \"$TEST_BAG\" --dry-run" "Dry-run works" "Dry-run failed"

print_test "Compress with LZ4"
run_cmd_silent "python -m roseApp.rose compress \"$TEST_BAG\" --compression lz4 --output \"$OUTPUT_DIR/test_lz4.bag\" --yes" "LZ4 compression works" "LZ4 compression failed"

print_test "Compress with BZ2"
run_cmd_silent "python -m roseApp.rose compress \"$TEST_BAG\" --compression bz2 --output \"$OUTPUT_DIR/test_bz2.bag\" --yes" "BZ2 compression works" "BZ2 compression failed"

print_test "Compress non-existent bag (error handling)"
run_cmd_expect_error "python -m roseApp.rose compress \"non_existent.bag\" --compression lz4" "Error handling works" "Should fail with non-existent bag"

print_test "Compress with invalid compression (error handling)"
run_cmd_expect_error "python -m roseApp.rose compress \"$TEST_BAG\" --compression invalid" "Error handling works" "Should fail with invalid compression"

# Cleanup
rm -f $OUTPUT_DIR/test_*.bag

echo -e "${GREEN}Compress command smoke tests passed!${NC}"

