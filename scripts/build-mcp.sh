#!/bin/bash
# =============================================================================
# OpenNutrition MCP Server - Build Script
# =============================================================================
# Builds the OpenNutrition MCP server for use with Claude/Cline.
# No API key required - data is bundled and runs locally.
#
# Source: https://www.opennutrition.app/
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MCP_DIR="$ROOT_DIR/mcp-opennutrition"

echo "=============================================="
echo "  OpenNutrition MCP Server - Build"
echo "=============================================="
echo ""
echo "Source: https://www.opennutrition.app/"
echo "License: MIT"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# Check prerequisites
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ ! -d "$MCP_DIR" ]; then
    echo -e "${RED}✗ MCP submodule not found. Run: git submodule update --init${NC}"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js is required${NC}"
    echo "Install from: https://nodejs.org/ (v18+ required)"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}✗ Node.js 18+ required, found v$NODE_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Node.js v$(node -v | cut -d'v' -f2) detected${NC}"
echo ""

# -----------------------------------------------------------------------------
# Install dependencies
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Installing npm dependencies...${NC}"
cd "$MCP_DIR"
npm install --silent
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# -----------------------------------------------------------------------------
# Build the MCP server
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Building MCP server...${NC}"
echo "This includes:"
echo "  1. Compiling TypeScript to JavaScript"
echo "  2. Decompressing OpenNutrition dataset"
echo "  3. Converting TSV data to SQLite database"
echo ""

npm run build

echo -e "${GREEN}✓ MCP server built successfully${NC}"
echo ""

# -----------------------------------------------------------------------------
# Generate MCP configuration
# -----------------------------------------------------------------------------
NODE_PATH=$(which node)
MCP_ENTRY="$MCP_DIR/build/index.js"

echo "=============================================="
echo -e "${GREEN}  Build Complete!${NC}"
echo "=============================================="
echo ""
echo "MCP Server location:"
echo "  $MCP_ENTRY"
echo ""
echo "Add this to your Claude Desktop config (~/.config/claude/claude_desktop_config.json):"
echo ""
echo '  "mcp-opennutrition": {'
echo "    \"command\": \"$NODE_PATH\","
echo '    "args": ['
echo "      \"$MCP_ENTRY\""
echo '    ]'
echo '  }'
echo ""
echo "Or for Cline/VS Code MCP settings:"
echo ""
cat << EOF
{
  "mcpServers": {
    "mcp-opennutrition": {
      "command": "$NODE_PATH",
      "args": ["$MCP_ENTRY"]
    }
  }
}
EOF
echo ""
echo "Available tools after setup:"
echo "  • search_foods - Search by name, brand, or partial match"
echo "  • browse_foods - Paginated list of all foods"
echo "  • get_food - Get detailed nutrition by food ID"
echo "  • barcode_lookup - Find food by EAN-13 barcode"
echo ""
