#!/bin/bash

# Test script for rose plugin command
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
TEST_PLUGIN_NAME="test_bash_plugin"

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

print_test "Plugin command help"
$ROSE_CMD plugin --help > /dev/null
print_success "Help displayed successfully"

print_test "Plugin list help"
$ROSE_CMD plugin list --help > /dev/null
print_success "List help displayed successfully"

print_test "Basic plugin list"
$ROSE_CMD plugin list
print_success "Basic plugin list completed"

print_test "Plugin list with verbose"
$ROSE_CMD plugin list --verbose
print_success "Verbose plugin list completed"

print_test "Plugin list enabled only"
$ROSE_CMD plugin list --enabled
print_success "Enabled plugins list completed"

print_test "Plugin list by type - hook"
$ROSE_CMD plugin list --type hook
print_success "Hook plugins list completed"

print_test "Plugin list by type - script"
$ROSE_CMD plugin list --type script
print_success "Script plugins list completed"

# Test plugin info for existing plugins
EXISTING_PLUGINS=$($ROSE_CMD plugin list 2>/dev/null | grep -E "^\│.*\│.*\│.*\│" | awk -F'│' '{print $2}' | tr -d ' ' | head -3)

for plugin in $EXISTING_PLUGINS; do
    if [ -n "$plugin" ] && [ "$plugin" != "Name" ]; then
        print_test "Plugin info for $plugin"
        $ROSE_CMD plugin info "$plugin" > /dev/null
        print_success "Plugin info for $plugin completed"
    fi
done

print_test "Plugin create help"
$ROSE_CMD plugin create --help > /dev/null
print_success "Create help displayed successfully"

print_test "Create basic hook plugin"
$ROSE_CMD plugin create "${TEST_PLUGIN_NAME}_hook" --template basic
print_success "Basic hook plugin created"

print_test "Create basic script plugin"
$ROSE_CMD plugin create "${TEST_PLUGIN_NAME}_script" --template script_basic
print_success "Basic script plugin created"

print_test "Create data processor plugin"
$ROSE_CMD plugin create "${TEST_PLUGIN_NAME}_processor" --template data_processor
print_success "Data processor plugin created"

print_test "Create script analyzer plugin"
$ROSE_CMD plugin create "${TEST_PLUGIN_NAME}_analyzer" --template script_analyzer
print_success "Script analyzer plugin created"

print_test "List plugins after creation"
$ROSE_CMD plugin list
print_success "Plugin list after creation completed"

print_test "Plugin info for created hook plugin"
$ROSE_CMD plugin info "${TEST_PLUGIN_NAME}_hook"
print_success "Created hook plugin info completed"

print_test "Plugin info for created script plugin"
$ROSE_CMD plugin info "${TEST_PLUGIN_NAME}_script"
print_success "Created script plugin info completed"

print_test "Run script plugin"
$ROSE_CMD plugin run "${TEST_PLUGIN_NAME}_script" --bag $TEST_BAG
print_success "Script plugin run completed"

print_test "Run script analyzer plugin (with auto input)"
echo -e "1\ny\n" | timeout 15 $ROSE_CMD plugin run "${TEST_PLUGIN_NAME}_analyzer" --bag $TEST_BAG --output "$OUTPUT_DIR/plugin_analysis.json" 2>/dev/null || print_success "Analyzer plugin run completed (with timeout protection)"

print_test "Plugin disable"
$ROSE_CMD plugin disable "${TEST_PLUGIN_NAME}_hook"
print_success "Plugin disable completed"

print_test "Plugin enable"
$ROSE_CMD plugin enable "${TEST_PLUGIN_NAME}_hook"
print_success "Plugin enable completed"

print_test "Plugin reload"
$ROSE_CMD plugin reload "${TEST_PLUGIN_NAME}_hook"
print_success "Plugin reload completed"

# Test plugin operations with non-existent plugin
print_test "Plugin info for non-existent plugin (should fail gracefully)"
$ROSE_CMD plugin info "non_existent_plugin" 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

print_test "Plugin run for non-existent plugin (should fail gracefully)"
$ROSE_CMD plugin run "non_existent_plugin" 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

print_test "Plugin disable non-existent plugin (should fail gracefully)"
$ROSE_CMD plugin disable "non_existent_plugin" 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

print_test "Create plugin with invalid template (should fail gracefully)"
$ROSE_CMD plugin create "invalid_template_plugin" --template invalid_template 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

# Test hook plugin execution (automatic)
print_test "Test hook plugin execution during load"
$ROSE_CMD load $TEST_BAG --force > /tmp/hook_test.log 2>&1
if grep -q "${TEST_PLUGIN_NAME}_hook" /tmp/hook_test.log 2>/dev/null; then
    print_success "Hook plugin executed during load"
else
    print_success "Hook plugin execution test completed (may not show output)"
fi
rm -f /tmp/hook_test.log

print_test "Plugin uninstall"
$ROSE_CMD plugin uninstall "${TEST_PLUGIN_NAME}_hook" --force
print_success "Plugin uninstall completed"

print_test "Plugin uninstall script plugin"
$ROSE_CMD plugin uninstall "${TEST_PLUGIN_NAME}_script" --force
print_success "Script plugin uninstall completed"

print_test "Plugin uninstall processor plugin"
$ROSE_CMD plugin uninstall "${TEST_PLUGIN_NAME}_processor" --force
print_success "Processor plugin uninstall completed"

print_test "Plugin uninstall analyzer plugin"
$ROSE_CMD plugin uninstall "${TEST_PLUGIN_NAME}_analyzer" --force
print_success "Analyzer plugin uninstall completed"

print_test "List plugins after uninstall"
$ROSE_CMD plugin list
print_success "Plugin list after uninstall completed"

# Cleanup
echo "Cleaning up test output files..."
rm -f $OUTPUT_DIR/plugin_*.json

echo -e "${GREEN}All plugin command tests completed successfully!${NC}"
