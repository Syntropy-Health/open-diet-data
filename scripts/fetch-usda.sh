#!/bin/bash
# =============================================================================
# USDA FoodData Central - Data Fetching Script
# =============================================================================
# Downloads and processes the latest USDA FoodData Central datasets.
# No API key required - data is public domain.
#
# Source: https://fdc.nal.usda.gov/download-datasets/
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
USDA_DIR="$ROOT_DIR/usda-fdc-data"
OUTPUT_DIR="$ROOT_DIR/output/usda"

echo "=============================================="
echo "  USDA FoodData Central - Data Fetch"
echo "=============================================="
echo ""
echo "Source: https://fdc.nal.usda.gov/download-datasets/"
echo "License: Public Domain (US Government)"
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

if [ ! -d "$USDA_DIR" ]; then
    echo -e "${RED}✗ USDA submodule not found. Run: git submodule update --init${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is required${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# -----------------------------------------------------------------------------
# Setup Python environment
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Setting up Python environment...${NC}"
cd "$USDA_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# -----------------------------------------------------------------------------
# Download and process USDA data
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Downloading USDA FoodData Central datasets...${NC}"
echo "This process will:"
echo "  1. Download Foundation Foods (~50MB)"
echo "  2. Download SR Legacy Foods (~30MB)"
echo "  3. Download Branded Foods (~2GB compressed)"
echo "  4. Process and merge all datasets"
echo ""
echo "Estimated time: 10-30 minutes depending on connection speed"
echo ""

mkdir -p "$OUTPUT_DIR"

# Parse arguments
KEEP_FILES=""
FILENAME="usda_food_nutrition_data.csv"

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-files)
            KEEP_FILES="--keep_files"
            shift
            ;;
        --filename)
            FILENAME="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

python3 main.py --output_dir "$OUTPUT_DIR" --filename "$FILENAME" $KEEP_FILES

deactivate

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}  USDA Data Fetch Complete!${NC}"
echo "=============================================="
echo ""
echo "Output file:"
echo "  $OUTPUT_DIR/$FILENAME"
echo ""

# Show file size
if [ -f "$OUTPUT_DIR/$FILENAME" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_DIR/$FILENAME" | cut -f1)
    LINE_COUNT=$(wc -l < "$OUTPUT_DIR/$FILENAME")
    echo "File size: $FILE_SIZE"
    echo "Food items: $((LINE_COUNT - 1))"
fi
echo ""
echo "Data includes:"
echo "  • Foundation Foods (whole foods with detailed nutrients)"
echo "  • SR Legacy Foods (historical USDA reference data)"
echo "  • Branded Foods (commercial products with labels)"
echo ""
