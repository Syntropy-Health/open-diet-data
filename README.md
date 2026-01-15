# Open Diet Data

Open-source nutrition and dietary supplement data sources for RAG-powered health applications.

## Overview

This repository aggregates authoritative open-source nutrition databases for use in AI-powered dietary recommendation systems. It serves as the data foundation for the [Diet Insight Engine](https://github.com/Syntropy-Health/diet-insight-engine) and related Syntropy Health applications.

## Data Sources

| Source | Description | Items |
| --- | --- | --- |
| **USDA FoodData Central** | Gold-standard US nutrition database | 900k+ foods |
| **OpenNutrition MCP** | MCP server for LLM food queries | 300k+ foods |
| **NIH DSLD** | Dietary supplement label database (API reference) | 100k+ products |

## Repository Structure

```
open-diet-data/
├── README.md           # This file
├── PRD.md              # Product requirements document
├── AGENT.md            # Data agent specification
├── DATA_SOURCES.md     # Exploration references
├── usda-fdc-data/      # Submodule: USDA FoodData Central pipeline
└── mcp-opennutrition/  # Submodule: OpenNutrition MCP server
```

## Quick Start

### Clone with Submodules

```bash
git clone --recurse-submodules git@github.com:Syntropy-Health/open-diet-data.git
```

### Initialize Submodules (if already cloned)

```bash
git submodule update --init --recursive
```

### Generate USDA Dataset

```bash
cd usda-fdc-data
python usda_fdc_data/main.py --output_dir ../output
```

### Build MCP Server

```bash
cd mcp-opennutrition
npm install
npm run build
```

## Use Cases

- **RAG-powered dietary recommendations**: Query foods by nutrient content
- **Symptom-deficiency correlation**: Map symptoms to nutritional deficiencies
- **LLM food queries**: Enable Claude/GPT to look up nutrition data via MCP
- **Supplement validation**: Cross-reference dosages with NIH data

## Integration

This data is consumed by:

- `diet-insight-engine` - Symptom-Diet Optimizer (SDO)
- `health-store-agent` - Product recommendations
- Custom Shopify wellness products (future)

## Documentation

- [PRD.md](./PRD.md) - Product requirements and architecture
- [AGENT.md](./AGENT.md) - NutritionDataAgent specification
- [DATA_SOURCES.md](./DATA_SOURCES.md) - Source evaluation and references

## License

- **USDA FoodData Central**: Public Domain (US Government)
- **OpenNutrition**: MIT License
- **Documentation**: MIT License

## Contributing

1. Fork the repository
2. Add data sources as submodules
3. Update documentation
4. Submit a pull request

---

Part of the [Syntropy Health](https://github.com/Syntropy-Health) ecosystem.
