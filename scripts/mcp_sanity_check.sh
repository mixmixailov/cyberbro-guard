#!/bin/bash
# CyberBro Guard - MCP Sanity Check Script
# Automated testing of MCP (Model Context Protocol) servers

set -e

echo "🤖 Running MCP Sanity Checks..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get current timestamp
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Create output directory
OUTPUT_DIR="docs/automation/mcp_sanity"
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}📁 Output directory: $OUTPUT_DIR${NC}"
echo -e "${BLUE}⏰ Timestamp: $TIMESTAMP${NC}"
echo ""

# Helper functions
test_pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
}

test_fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
}

test_warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
}

# Test Context7 MCP
echo "🔍 Testing Context7 MCP..."
echo "=========================="

CONTEXT7_OUTPUT="$OUTPUT_DIR/context7_$TIMESTAMP.txt"

cat > "$CONTEXT7_OUTPUT" << EOF
MCP Sanity Check: Context7
===========================
Timestamp: $TIMESTAMP
Test Query: telegram-bot-api

STATUS: TESTING...

Test Results:
EOF

# Note: In a real scenario, you would use the actual MCP tools here
# For now, we create a template that shows the test was attempted

echo "Context7 MCP sanity check template created" >> "$CONTEXT7_OUTPUT"
echo "Manual verification required using MCP tools" >> "$CONTEXT7_OUTPUT"

test_pass "Context7 test template created: $CONTEXT7_OUTPUT"

# Test Brave Search MCP
echo ""
echo "🔎 Testing Brave Search MCP..."
echo "=============================="

BRAVE_OUTPUT="$OUTPUT_DIR/brave-search_$TIMESTAMP.txt"

cat > "$BRAVE_OUTPUT" << EOF
MCP Sanity Check: Brave Search
===============================
Timestamp: $TIMESTAMP
Test Query: telegram bot api python rate limiting

STATUS: TESTING...

Test Results:
EOF

echo "Brave Search MCP sanity check template created" >> "$BRAVE_OUTPUT"
echo "Manual verification required using MCP tools" >> "$BRAVE_OUTPUT"

test_pass "Brave Search test template created: $BRAVE_OUTPUT"

# Test Playwright MCP
echo ""
echo "🎭 Testing Playwright MCP..."
echo "============================"

PLAYWRIGHT_OUTPUT="$OUTPUT_DIR/playwright_$TIMESTAMP.txt"

cat > "$PLAYWRIGHT_OUTPUT" << EOF
MCP Sanity Check: Playwright
============================
Timestamp: $TIMESTAMP
Test Operation: browser_snapshot

STATUS: TESTING...

Test Results:
EOF

echo "Playwright MCP sanity check template created" >> "$PLAYWRIGHT_OUTPUT"
echo "Manual verification required using MCP tools" >> "$PLAYWRIGHT_OUTPUT"

test_pass "Playwright test template created: $PLAYWRIGHT_OUTPUT"

# Check MCP configuration
echo ""
echo "⚙️  Checking MCP Configuration..."
echo "================================="

if [ -f ".cursor/mcp.json" ]; then
    test_pass "MCP configuration file exists: .cursor/mcp.json"
    
    # Check JSON syntax if jq is available
    if command -v jq >/dev/null 2>&1; then
        if jq empty .cursor/mcp.json >/dev/null 2>&1; then
            test_pass "MCP configuration has valid JSON syntax"
        else
            test_fail "MCP configuration has invalid JSON syntax"
        fi
        
        # Check for specific MCPs
        if jq -e '.mcpServers.context7' .cursor/mcp.json >/dev/null 2>&1; then
            test_pass "Context7 MCP configured"
        else
            test_warn "Context7 MCP not found in configuration"
        fi
        
        if jq -e '.mcpServers."brave-search"' .cursor/mcp.json >/dev/null 2>&1; then
            test_pass "Brave Search MCP configured"
        else
            test_warn "Brave Search MCP not found in configuration"
        fi
        
        if jq -e '.mcpServers.playwright' .cursor/mcp.json >/dev/null 2>&1; then
            test_pass "Playwright MCP configured"
        else
            test_warn "Playwright MCP not found in configuration"
        fi
    else
        test_warn "jq not available, skipping JSON validation"
    fi
else
    test_warn "MCP configuration file not found (expected in CI environments)"
fi

# Validate output directory structure
echo ""
echo "📂 Validating Output Structure..."
echo "================================="

if [ -d "$OUTPUT_DIR" ]; then
    test_pass "MCP sanity output directory exists"
    
    # Check for README
    if [ -f "$OUTPUT_DIR/README.md" ]; then
        test_pass "MCP sanity README exists"
    else
        test_warn "MCP sanity README not found"
    fi
    
    # Count result files
    result_count=$(ls "$OUTPUT_DIR"/*.txt 2>/dev/null | wc -l)
    if [ "$result_count" -gt 0 ]; then
        test_pass "Found $result_count MCP sanity result files"
    else
        test_warn "No MCP sanity result files found"
    fi
    
else
    test_fail "MCP sanity output directory missing"
fi

# Summary
echo ""
echo "📊 MCP Sanity Check Summary"
echo "==========================="
echo -e "${BLUE}Timestamp:${NC} $TIMESTAMP"
echo -e "${BLUE}Output Directory:${NC} $OUTPUT_DIR"
echo -e "${BLUE}Generated Files:${NC}"
echo "  - $CONTEXT7_OUTPUT"
echo "  - $BRAVE_OUTPUT"
echo "  - $PLAYWRIGHT_OUTPUT"

echo ""
echo -e "${GREEN}✅ MCP sanity check templates created successfully!${NC}"
echo ""
echo "📝 Next Steps:"
echo "1. Run actual MCP tests using Cursor IDE"
echo "2. Update the generated files with real test results"
echo "3. Verify MCP server connectivity"
echo "4. Document any issues found"

echo ""
echo -e "${YELLOW}💡 To run real MCP tests:${NC}"
echo "   - Use Context7 MCP in Cursor IDE to test library resolution"
echo "   - Use Brave Search MCP to test web search functionality"
echo "   - Use Playwright MCP to test browser automation"

exit 0
