# MCP Server Setup for CyberBro Guard

## Current Status

⚠️ **MCP servers are currently disabled in configuration** due to package availability.

The MCP ecosystem is rapidly evolving, and official package names may change. Current configuration includes placeholder package names that will be updated when official packages are available.

## Configuration

The `.cursor/mcp.json` file is prepared with the expected configuration structure:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["mcp-server-context7@latest"],
      "disabled": true
    },
    "playwright": {
      "command": "npx", 
      "args": ["mcp-server-playwright@latest"],
      "disabled": true
    }
  }
}
```

## Setup Instructions

### 1. Check MCP Server Availability

Before enabling MCP servers, verify the correct package names:

```bash
# Check available MCP packages
npm search mcp-server

# Or check specific packages
npm info @modelcontextprotocol/server-playwright
npm info @context7/mcp-server
```

### 2. Update Package Names

Once correct package names are identified, update `.cursor/mcp.json`:

```bash
# Enable servers by setting disabled: false
# Update package names in args array
```

### 3. Install Dependencies

```bash
# Install Playwright browsers (for Playwright MCP)
npx playwright install chromium

# Verify Node.js version (requires Node 16+)
node --version
```

### 4. Environment Setup

Set required environment variables:

```bash
# For Context7 (optional)
export CONTEXT7_API_KEY="your-api-key"

# For Playwright
export PLAYWRIGHT_BROWSER="chromium"
```

### 5. Enable MCP Servers

Edit `.cursor/mcp.json` and set `"disabled": false` for available servers.

## Testing MCP Setup

### Context7 Testing
```bash
# Test Context7 server availability
npx [correct-package-name] --help
```

### Playwright Testing  
```bash
# Test Playwright server
npx [correct-package-name] --help

# Test browser automation
npx playwright --version
```

## E2E Testing Without MCP

While MCP servers are being set up, E2E testing can proceed using direct Playwright:

```bash
# Install Playwright directly
npm install -D playwright

# Run E2E tests
python -m pytest tests/e2e/ -v
```

## Troubleshooting

### Common Issues

#### Package Not Found
```
npm error 404 Not Found - GET package-name
```
**Solution**: Check official MCP documentation for correct package names.

#### Node Version Compatibility
```
Error: Requires Node.js 16 or higher
```
**Solution**: Update Node.js to version 16 or higher.

#### Browser Installation
```
Executable doesn't exist at path
```
**Solution**: Run `npx playwright install chromium`

### Getting Help

1. Check [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
2. Review [Cursor MCP Integration Guide](https://docs.cursor.com/mcp)
3. Check project documentation in `docs/e2e.md`

## Future Updates

This configuration will be updated as:
- Official MCP server packages become available
- Package names are stabilized
- Additional MCP servers are added to the ecosystem

Monitor the following repositories for updates:
- Model Context Protocol: https://github.com/modelcontextprotocol
- Context7 MCP: (check official documentation)
- Playwright MCP: (check official documentation)


