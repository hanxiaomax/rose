#!/bin/bash

# Smoke test for rose inspect command
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

print_test "Inspect command help"
run_cmd_silent "python -m roseApp.rose inspect --help" "Help works" "Help failed"

print_test "Basic inspect"
run_cmd_silent "python -m roseApp.rose inspect \"$TEST_BAG\"" "Basic inspect works" "Basic inspect failed"

print_test "Inspect with verbose"
run_cmd_silent "python -m roseApp.rose inspect \"$TEST_BAG\" --verbose" "Verbose inspect works" "Verbose inspect failed"

print_test "Inspect with topics"
run_cmd_silent "python -m roseApp.rose inspect \"$TEST_BAG\" --topics gps" "Topic filtering works" "Topic filtering failed"

print_test "Inspect with sorting"
run_cmd_silent "python -m roseApp.rose inspect \"$TEST_BAG\" --sort name" "Sorting works" "Sorting failed"

print_test "Inspect non-existent bag (error handling)"
run_cmd_expect_error "python -m roseApp.rose inspect \"non_existent.bag\"" "Error handling works" "Should fail with non-existent bag"

# Cleanup
rm -f $OUTPUT_DIR/inspect_*.txt

echo -e "${GREEN}Inspect command smoke tests passed!${NC}"