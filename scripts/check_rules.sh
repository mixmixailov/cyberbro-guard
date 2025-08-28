#!/bin/bash
# CyberBro Guard - Rules Compliance Check Script
# Проверяет соответствие проекта установленным правилам

set -e

echo "🔍 Checking CyberBro Guard rules compliance..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
    ((WARNINGS++))
}

echo ""
echo "📋 Database Guidelines Compliance"
echo "=================================="

# Check DB structure
if [ -d "app/db" ]; then
    check_pass "Database directory exists: app/db/"
else
    check_fail "Missing database directory: app/db/"
fi

if [ -f "app/db/models.py" ]; then
    check_pass "Database models file exists: app/db/models.py"
else
    check_fail "Missing database models: app/db/models.py"
fi

if [ -d "db/migrations" ]; then
    check_pass "Migrations directory exists: db/migrations/"
else
    check_warn "Migrations directory not found: db/migrations/"
fi

# Check for SQLite usage
if grep -r "sqlite" app/db/ >/dev/null 2>&1 || grep -r "SQLite" app/db/ >/dev/null 2>&1; then
    check_pass "SQLite usage detected in database code"
else
    check_warn "SQLite usage not clearly detected"
fi

echo ""
echo "🔧 Handlers Guidelines Compliance"
echo "================================="

# Check handlers structure
if [ -d "app/handlers" ]; then
    check_pass "Handlers directory exists: app/handlers/"
else
    check_fail "Missing handlers directory: app/handlers/"
fi

if [ -f "app/handlers/__init__.py" ]; then
    check_pass "Handlers package initialization exists"
else
    check_fail "Missing handlers/__init__.py"
fi

# Check for handler registration
if grep -r "register.*handlers" app/handlers/ >/dev/null 2>&1; then
    check_pass "Handler registration pattern found"
else
    check_warn "Handler registration pattern not clearly detected"
fi

echo ""
echo "🧪 Testing Standards Compliance"
echo "==============================="

# Check test structure
if [ -d "tests" ]; then
    check_pass "Tests directory exists: tests/"
else
    check_fail "Missing tests directory"
fi

if [ -d "tests/e2e" ]; then
    check_pass "E2E tests directory exists: tests/e2e/"
else
    check_fail "Missing E2E tests directory: tests/e2e/"
fi

# Check for pytest configuration
if [ -f "pyproject.toml" ] && grep -q "pytest" pyproject.toml; then
    check_pass "Pytest configuration found in pyproject.toml"
elif [ -f "pytest.ini" ]; then
    check_pass "Pytest configuration found in pytest.ini"
else
    check_warn "Pytest configuration not clearly detected"
fi

# Check for coverage configuration
if grep -r "coverage" requirements-dev.txt >/dev/null 2>&1; then
    check_pass "Coverage dependency found"
else
    check_warn "Coverage dependency not found in requirements-dev.txt"
fi

echo ""
echo "🤖 MCP Requirements Compliance"
echo "=============================="

# Check MCP configuration
if [ -f ".cursor/mcp.json" ]; then
    check_pass "MCP configuration exists: .cursor/mcp.json"
else
    check_fail "Missing MCP configuration: .cursor/mcp.json"
fi

# Check for specific MCPs
if [ -f ".cursor/mcp.json" ]; then
    if grep -q "context7" .cursor/mcp.json; then
        check_pass "Context7 MCP configured"
    else
        check_warn "Context7 MCP not found in configuration"
    fi
    
    if grep -q "brave" .cursor/mcp.json; then
        check_pass "Brave Search MCP configured"
    else
        check_warn "Brave Search MCP not found in configuration"
    fi
    
    if grep -q "playwright" .cursor/mcp.json; then
        check_pass "Playwright MCP configured"
    else
        check_warn "Playwright MCP not found in configuration"
    fi
fi

echo ""
echo "📁 Project Structure Compliance"
echo "==============================="

# Check essential files
ESSENTIAL_FILES=(
    "README.md"
    "requirements.txt"
    "requirements-dev.txt"
    "Dockerfile"
    "docker-compose.yml"
    "app/main.py"
    "app/config.py"
    "pyproject.toml"
)

for file in "${ESSENTIAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        check_pass "Essential file exists: $file"
    else
        check_fail "Missing essential file: $file"
    fi
done

# Check project metadata
if grep -q "CyberBro Guard" README.md 2>/dev/null; then
    check_pass "Project name found in README.md"
else
    check_warn "Project name not clearly identified in README.md"
fi

echo ""
echo "🔒 Security & Dependencies Compliance"
echo "====================================="

# Check for security-related files
if [ -f "constraints.txt" ]; then
    check_pass "Dependency constraints file exists: constraints.txt"
else
    check_warn "No dependency constraints file found"
fi

# Check for environment configuration
if [ -f "env.example" ]; then
    check_pass "Environment example file exists: env.example"
else
    check_warn "No environment example file found"
fi

# Check for secrets handling
if grep -r "WEBHOOK_SECRET" app/ >/dev/null 2>&1; then
    check_pass "Webhook secret configuration detected"
else
    check_warn "Webhook secret configuration not found"
fi

echo ""
echo "📊 Compliance Summary"
echo "===================="
echo -e "Passed checks: ${GREEN}$PASSED${NC}"
echo -e "Failed checks: ${RED}$FAILED${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Compliance check FAILED${NC}"
    echo "Please fix the failed checks before proceeding."
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Compliance check PASSED with warnings${NC}"
    echo "Consider addressing the warnings for better compliance."
    exit 0
else
    echo ""
    echo -e "${GREEN}✅ All compliance checks PASSED${NC}"
    echo "Project is fully compliant with established rules."
    exit 0
fi
