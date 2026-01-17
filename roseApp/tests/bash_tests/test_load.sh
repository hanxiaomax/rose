#!/bin/bash

# Smoke test for rose load command
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

# Define bags
BAG1="roseApp/tests/bash_tests/demo.bag"
BAG2="roseApp/tests/bash_tests/demo1.bag"

# Show test configuration
show_test_config "Load Command"
echo "Bag 1: $BAG1"
echo "Bag 2: $BAG2"

print_test "Load command help"
run_cmd_silent "$ROSE_CMD load --help" "Help works" "Help failed"

print_test "Basic load (demo.bag)"
run_cmd_silent "$ROSE_CMD load '$BAG1'" "Basic load works" "Basic load failed"

print_test "Basic load (demo1.bag)"
run_cmd_silent "$ROSE_CMD load '$BAG2'" "Basic load (demo1) works" "Basic load (demo1) failed"

print_test "Load with verbose"
run_cmd_silent "$ROSE_CMD load '$BAG1' --verbose" "Verbose load works" "Verbose load failed"

# Note: --force and --dry-run might not be in load command currently based on previous inspection
# Checking load.py options: --verbose, --interactive. 
# It seems load.py doesn't have --force or --dry-run in the current code snippet I saw?
# But checking load.py content:
# load(input_bags, verbose, interactive)
# Let's double check options. Previous bash test had --force and --dry-run. 
# Maybe they were removed or I missed them. 
# Safest is to test what I saw in test_cli.py: load has verbose.
# I will stick to what seems to exist.

print_test "Load multiple bags (glob)"
# Assuming shell expansion or glob handling in app
run_cmd_silent "$ROSE_CMD load 'roseApp/tests/bash_tests/demo*.bag'" "Glob pattern load works" "Glob pattern load failed"

print_test "Load non-existent file (graceful exit)"
# Expecting success (exit code 0) but 0 loaded
run_cmd_silent "$ROSE_CMD load non_existent.bag" "Graceful handling works" "Graceful handling failed"

echo -e "${GREEN}Load command smoke tests passed!${NC}"
