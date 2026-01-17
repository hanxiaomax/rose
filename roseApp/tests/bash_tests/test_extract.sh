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
PROJECT_ROOT="$(dirname "$0")/../../.."
cd "$PROJECT_ROOT" || exit 1

# Use absolute path for output to avoid issues with relative path concatenation
OUTPUT_DIR="$(pwd)/roseApp/tests/bash_tests/output"
mkdir -p "$OUTPUT_DIR"

# Define bags (relative paths are fine for input)
BAG1="roseApp/tests/bash_tests/demo.bag"
BAG2="roseApp/tests/bash_tests/demo1.bag"

# Show test configuration
show_test_config "Extract Command"
echo "Output Dir: $OUTPUT_DIR"

print_test "Extract command help"
run_cmd_silent "$ROSE_CMD extract --help" "Help works" "Help failed"

# Topic to extract (using 'gps' as verified to exist/fuzzy-match)
TOPIC="gps"

print_test "Extract with topics from demo.bag"
# Use {input} placeholder to ensure correct naming
run_cmd "$ROSE_CMD extract '$BAG1' --topics $TOPIC --output '$OUTPUT_DIR/{input}_extract.bag' --yes"

print_test "Extract with compression (lz4)"
run_cmd "$ROSE_CMD extract '$BAG1' --topics $TOPIC --compression lz4 --output '$OUTPUT_DIR/{input}_extract_lz4.bag' --yes"

print_test "Extract multiple bags (demo + demo1)"
run_cmd "$ROSE_CMD extract '$BAG1' '$BAG2' --topics $TOPIC --output '$OUTPUT_DIR/{input}_extract_multi.bag' --yes"

print_test "Extract reverse selection (exclude topic)"
run_cmd "$ROSE_CMD extract '$BAG1' --topics $TOPIC --reverse --output '$OUTPUT_DIR/{input}_extract_reverse.bag' --yes"

print_test "Extract non-existent bag (graceful handling)"
# Should exit with 0 (success) and just warn
run_cmd_silent "$ROSE_CMD extract non_existent.bag --topics $TOPIC --yes" "Graceful handling works" "Graceful handling failed"

# Cleanup
rm -f "$OUTPUT_DIR"/*extract*.bag

echo -e "${GREEN}Extract command smoke tests passed!${NC}"
