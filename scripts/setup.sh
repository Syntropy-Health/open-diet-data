#!/bin/bash
# =============================================================================
# Open Diet Data - Complete Setup Script
# =============================================================================
# This script sets up all data sources for the open-diet-data repository.
# Run from the repository root: ./scripts/setup.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=============================================="
echo "  Open Diet Data - Complete Setup"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Step 1: Initialize submodules
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/4] Initializing git submodules...${NC}"
cd "$ROOT_DIR"
git submodule update --init --recursive
echo -e "${GREEN}✓ Submodules initialized${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 2: Setup USDA FoodData Central
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/4] Setting up USDA FoodData Central...${NC}"
cd "$ROOT_DIR/usda-fdc-data"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is required but not installed${NC}"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate and install dependencies
source .venv/bin/activate
pip install -q -r requirements.txt
echo -e "${GREEN}✓ USDA dependencies installed${NC}"

# Run data processing (this downloads and processes USDA data)
echo "Downloading and processing USDA data (this may take 10-30 minutes)..."
python3 main.py --output_dir "$ROOT_DIR/output/usda"

deactivate
echo -e "${GREEN}✓ USDA FoodData Central setup complete${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 3: Setup OpenNutrition MCP Server
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/4] Setting up OpenNutrition MCP Server...${NC}"
cd "$ROOT_DIR/mcp-opennutrition"

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js is required but not installed${NC}"
    echo "Install Node.js 20+ from: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}✗ Node.js 18+ required, found v$NODE_VERSION${NC}"
    exit 1
fi

# Install dependencies and build
echo "Installing npm dependencies..."
npm install --silent

echo "Building MCP server (includes data conversion)..."
npm run build

echo -e "${GREEN}✓ OpenNutrition MCP Server setup complete${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 4: Create output directories
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/4] Creating output directories...${NC}"
mkdir -p "$ROOT_DIR/output/usda"
mkdir -p "$ROOT_DIR/output/embeddings"
echo -e "${GREEN}✓ Output directories created${NC}"
echo ""

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo "=============================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Data locations:"
echo "  • USDA CSV:        $ROOT_DIR/output/usda/usda_food_nutrition_data.csv"
echo "  • MCP Server:      $ROOT_DIR/mcp-opennutrition/build/index.js"
echo "  • MCP Database:    $ROOT_DIR/mcp-opennutrition/build/opennutrition.db"
echo ""
echo "Next steps:"
echo "  1. Run './scripts/fetch-usda.sh' to refresh USDA data"
echo "  2. Run './scripts/build-mcp.sh' to rebuild MCP server"
echo "  3. See README.md for MCP configuration with Claude"
echo ""
