# Data Sources Exploration & References

## Overview

This document catalogs the open-source nutrition and supplement databases evaluated for the Diet Insight Engine. Only 3 key reputable sources were selected to avoid complexity while ensuring comprehensive coverage.

---

## Selected Data Sources (3 Maximum)

### 1. USDA FoodData Central ✅ SELECTED

**Status**: Git submodule at `data/usda-fdc-data/`

| Attribute | Value |
| --- | --- |
| Repository | [mkayeterry/usda-fdc-data](https://github.com/mkayeterry/usda-fdc-data) |
| Official Source | [fdc.nal.usda.gov](https://fdc.nal.usda.gov/) |
| License | Public Domain (US Government) |
| Data Types | Foundation, SR Legacy, Branded Foods |
| Food Items | 900,000+ |
| Nutrients | 150+ per food item |
| Format | CSV (cleaned, stacked) |
| Update Frequency | Quarterly |

**Why Selected**:

- Gold standard for US nutrition data
- Comprehensive nutrient profiles (macros, vitamins, minerals)
- Public domain - no licensing restrictions
- Cleaned dataset ready for ingestion

**Key Files**:

- `usda_fdc_data/main.py` - Data download and processing
- `output/usda_food_nutrition_data.csv` - Cleaned output

---

### 2. OpenNutrition MCP ✅ SELECTED

**Status**: Git submodule at `data/mcp-opennutrition/`

| Attribute | Value |
| --- | --- |
| Repository | [deadletterq/mcp-opennutrition](https://github.com/deadletterq/mcp-opennutrition) |
| Data Source | [OpenNutrition.app](https://www.opennutrition.app/) |
| License | MIT |
| Food Items | 300,000+ |
| Features | Barcode lookup, search, browse |
| Format | SQLite + MCP Server (Node.js) |
| Integration | Model Context Protocol |

**Why Selected**:

- Native LLM integration via MCP protocol
- Runs locally (no external API calls)
- Barcode scanning capability
- Comprehensive nutritional profiles

**Key Files**:

- `build/index.js` - MCP server entry point
- `src/tools/` - Search, browse, barcode tools

---

### 3. NIH Dietary Supplement Label Database ✅ SELECTED (Reference)

**Status**: External API reference (not submodule)

| Attribute | Value |
| --- | --- |
| URL | [dsld.od.nih.gov](https://dsld.od.nih.gov/) |
| API Docs | [API Reference](https://dsld.od.nih.gov/api-guide) |
| License | Public Domain (US Government) |
| Products | 100,000+ supplement labels |
| Data | Ingredients, amounts, daily values |
| Format | REST API (JSON) |

**Why Selected**:

- Authoritative supplement ingredient data
- Validates dosage recommendations
- Required for supplement safety checks
- No data storage needed (API-based)

**Usage**:

```python
# Example NIH DSLD API call
import requests

response = requests.get(
    "https://api.ods.od.nih.gov/dsld/v8/label",
    params={"ingredient": "vitamin_d", "limit": 10}
)
```

---

## Evaluated But Not Selected

### Open Food Facts

| Attribute | Value |
| --- | --- |
| Repository | [openfoodfacts/openfoodfacts-server](https://github.com/openfoodfacts/openfoodfacts-server) |
| URL | [world.openfoodfacts.org](https://world.openfoodfacts.org/) |
| Food Items | 3,000,000+ |
| Coverage | Global (not US-focused) |

**Why Not Selected**: OpenNutrition MCP provides similar functionality with better LLM integration. USDA is more authoritative for US nutrition data.

---

### FDC-API (Go REST Server)

| Attribute | Value |
| --- | --- |
| Repository | [littlebunch/fdc-api](https://github.com/littlebunch/fdc-api) |
| Backend | Couchbase/CouchDB |
| Language | Go |

**Why Not Selected**: Requires separate database setup (Couchbase). The mkayeterry/usda-fdc-data provides the same USDA data in simpler CSV format.

---

## Future Data Source: Shopify Wellness Products

Custom Syntropy Health products will be integrated as an additional data source:

| Attribute | Value |
| --- | --- |
| Source | Shopify GraphQL API |
| Products | Custom wellness supplements |
| Integration | Health Store Agent |
| Status | Planned |

**Integration Point**: `diet_insight_engine/health_store_agent/`

---

## Data Source Comparison Matrix

| Feature | USDA FDC | OpenNutrition | NIH DSLD | Shopify |
| --- | --- | --- | --- | --- |
| Food Data | ✅ | ✅ | ❌ | ❌ |
| Supplement Data | ❌ | ❌ | ✅ | ✅ |
| Barcode Lookup | ❌ | ✅ | ❌ | ❌ |
| LLM/MCP Native | ❌ | ✅ | ❌ | ❌ |
| RAG Ready | ✅ | ✅ | ❌ | ✅ |
| Runs Locally | ✅ | ✅ | ❌ | ❌ |
| US Authoritative | ✅ | ⚠️ | ✅ | ❌ |

---

## Integration Priority

1. **Phase 1**: USDA FoodData Central → Vector store for RAG
2. **Phase 2**: OpenNutrition MCP → LLM food queries
3. **Phase 3**: Shopify Products → Custom product recommendations
4. **Phase 4**: NIH DSLD API → Supplement validation layer

---

## References

### Official Documentation

- [USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide.html)
- [OpenNutrition Dataset](https://www.opennutrition.app/)
- [NIH ODS Databases](https://ods.od.nih.gov/Research/databases.aspx)
- [Model Context Protocol Spec](https://modelcontextprotocol.io/)

### Research Papers

- Haytowitz, D.B. et al. "USDA National Nutrient Database for Standard Reference"
- NIH Office of Dietary Supplements Fact Sheets

### Related Projects

- [USDA Food Composition Databases](https://www.ars.usda.gov/northeast-area/beltsville-md-bhnrc/beltsville-human-nutrition-research-center/methods-and-application-of-food-composition-laboratory/mafcl-site-pages/database-resources/)
