#!/bin/bash

# Smoke test for rose compress command
# Simple and direct testing

# Note: Not using set -e to allow error testing

# Load common functions
source "$(dirname "$0")/common_functions.sh"

# Parse command line arguments
parse_test_args "$@"

# Test configuration
ROSE_CMD="python -m roseApp.rose"
PROJECT_ROOT="$(dirname "$0")/../../.."
cd "$PROJECT_ROOT" || exit 1

# Use absolute path for output
OUTPUT_DIR="$(pwd)/roseApp/tests/bash_tests/output"
mkdir -p "$OUTPUT_DIR"

# Define bags
BAG1="roseApp/tests/bash_tests/demo.bag"
BAG2="roseApp/tests/bash_tests/demo1.bag"

# Show test configuration
show_test_config "Compress Command"
echo "Output Dir: $OUTPUT_DIR"

print_test "Compress command help"
run_cmd_silent "$ROSE_CMD compress --help" "Help works" "Help failed"

print_test "Compress demo.bag with LZ4"
run_cmd_silent "$ROSE_CMD compress '$BAG1' --compression lz4 --output '$OUTPUT_DIR/compress_lz4.bag' --yes" "LZ4 compression works" "LZ4 compression failed"

print_test "Compress demo1.bag with BZ2"
# This might be slow but we test it as a valid combination
run_cmd_silent "$ROSE_CMD compress '$BAG2' --compression bz2 --output '$OUTPUT_DIR/compress_bz2.bag' --yes" "BZ2 compression works" "BZ2 compression failed"

print_test "Compress multiple bags"
# Use {input} placeholder for batch processing
run_cmd_silent "$ROSE_CMD compress '$BAG1' '$BAG2' --compression lz4 --output '$OUTPUT_DIR/{input}_compressed.bag' --yes" "Batch compression works" "Batch compression failed"

print_test "Compress non-existent bag (graceful handling)"
# Should exit with 0 (success) and just warn
run_cmd_silent "$ROSE_CMD compress non_existent.bag --compression lz4" "Graceful handling works" "Graceful handling failed"

print_test "Compress with invalid compression"
# Should exit with non-zero
run_cmd_expect_error "$ROSE_CMD compress '$BAG1' --compression invalid" "Error handling works" "Should fail with invalid compression"

# Cleanup
rm -f "$OUTPUT_DIR"/compress_*.bag
rm -f "$OUTPUT_DIR"/*_compressed.bag

echo -e "${GREEN}Compress command smoke tests passed!${NC}"
