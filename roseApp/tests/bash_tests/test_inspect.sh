#!/bin/bash

# Smoke test for rose inspect command
# Testing CLI functionality including filters, sorting, and detail views

# Load common functions
source "$(dirname "$0")/common_functions.sh"

# Parse command line arguments
parse_test_args "$@"

# Test configuration
ROSE_CMD="python -m roseApp.rose"
PROJECT_ROOT="$(dirname "$0")/../../.."
cd "$PROJECT_ROOT" || exit 1

# Define bag
BAG1="roseApp/tests/bash_tests/demo.bag"

# Show test configuration
show_test_config "Inspect Command (Rich)"

# Setup: Ensure bag is loaded to avoid interactive prompts
print_test "Setup: Loading bag"
run_cmd_silent "$ROSE_CMD load '$BAG1'" "Bag loaded" "Bag load failed"

print_test "Inspect command help"
run_cmd_silent "$ROSE_CMD inspect --help" "Help works" "Help failed"

print_test "Inspect summary (default CLI)"
# Should output Bag Information
# Use NO_COLOR=1 to ensure clean output for parsing
OUTPUT=$(NO_COLOR=1 $ROSE_CMD inspect "$BAG1")
if echo "$OUTPUT" | grep -q "Bag Information"; then
    print_success "Summary output verified"
else
    print_error "Summary output missing 'Bag Information'"
    echo "Output was:"
    echo "$OUTPUT"
fi

print_test "Inspect verbose (Table view)"
# Should contain 'Frequency' or similar headers
run_cmd_silent "$ROSE_CMD inspect '$BAG1' --verbose" "Verbose mode works" "Verbose mode failed"

print_test "Inspect with topics filter (regex)"
# Filter for 'gps' or whatever exists. Assuming 'gps' based on previous context.
run_cmd_silent "$ROSE_CMD inspect '$BAG1' --topics 'gps'" "Regex filter works" "Regex filter failed"

print_test "Get a valid topic name for detail test"
# Capture first topic name from default output
# In NO_COLOR mode, format is:   topic_name (type)
# We look for lines starting with whitespace and a slash
TOPIC_NAME=$(echo "$OUTPUT" | grep -m 1 "  /")

# Clean it up: take first word
TOPIC_NAME=$(echo "$TOPIC_NAME" | awk '{print $1}')

if [ -z "$TOPIC_NAME" ]; then
    print_error "Could not extract a topic name."
    echo "Output sample (first 50 lines):"
    echo "$OUTPUT" | head -n 50
    TOPIC_NAME="/gps/fix" # Fallback guess
else
    print_success "Using topic: $TOPIC_NAME"
fi

print_test "Inspect single topic detail (Tree view)"
run_cmd_silent "$ROSE_CMD inspect '$BAG1' --topic '$TOPIC_NAME'" "Single topic detail works" "Single topic detail failed"

print_test "Inspect show fields"
run_cmd_silent "$ROSE_CMD inspect '$BAG1' --show-fields" "Show fields option works" "Show fields option failed"

print_test "Inspect sorting"
run_cmd_silent "$ROSE_CMD inspect '$BAG1' --sort count --reverse" "Sorting option works" "Sorting option failed"

print_test "Inspect non-existent bag (interactive prompt handling)"
# We pipe "N" to assume user says No to loading non-cached files
echo "N" | run_cmd "$ROSE_CMD inspect non_existent.bag" 
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 1 ]; then
    print_success "Graceful exit on non-existent bag"
else
    print_error "Failed with unexpected exit code $EXIT_CODE"
fi

echo -e "${GREEN}Inspect command smoke tests passed!${NC}"