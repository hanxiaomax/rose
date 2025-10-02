#!/bin/bash

# Smoke test for rose data command
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

print_test "Data command help"
run_cmd_silent "python -m roseApp.rose data --help" "Help works" "Help failed"

print_test "Data export CSV"
run_cmd_silent "python -m roseApp.rose data \"$TEST_BAG\" --format csv --output \"$OUTPUT_DIR/test_data.csv\" --topics gps" "CSV export works" "CSV export failed"

print_test "Data export JSON"
run_cmd_silent "python -m roseApp.rose data \"$TEST_BAG\" --format json --output \"$OUTPUT_DIR/test_data.json\" --topics gps" "JSON export works" "JSON export failed"

print_test "Data with time range"
run_cmd_silent "python -m roseApp.rose data \"$TEST_BAG\" --format csv --start-time 0 --end-time 10 --output \"$OUTPUT_DIR/test_time_range.csv\"" "Time range works" "Time range failed"

print_test "Data non-existent bag (error handling)"
run_cmd_expect_error "python -m roseApp.rose data \"non_existent.bag\" --format csv" "Error handling works" "Should fail with non-existent bag"

print_test "Data invalid format (error handling)"
run_cmd_expect_error "python -m roseApp.rose data \"$TEST_BAG\" --format invalid" "Error handling works" "Should fail with invalid format"

# Cleanup
rm -f $OUTPUT_DIR/test_data.*
rm -f $OUTPUT_DIR/test_time_range.*

echo -e "${GREEN}Data command smoke tests passed!${NC}"