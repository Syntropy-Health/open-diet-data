# Data Sources PRD - Diet Insight Engine

## Overview

This document defines the Product Requirements for integrating external nutrition and supplement data sources into the Diet Insight Engine (DIET) ecosystem. These data sources power the RAG (Retrieval-Augmented Generation) capabilities of the Symptom-Diet Optimizer (SDO) and related agents.

## Problem Statement

The current diet-insight-engine relies on hardcoded nutritional mappings in `recommender.py` and fallback rules in `analyzer.py`. This limits:
- **Accuracy**: Limited nutrient-symptom correlations
- **Coverage**: Only covers ~8 common nutrients
- **Scalability**: Cannot easily add new foods, supplements, or symptom patterns
- **Evidence basis**: No citations or confidence scoring from authoritative sources

## Solution: RAG-Powered Nutrition Intelligence

Integrate authoritative open-source nutrition databases as RAG data sources to provide:
1. **Comprehensive food nutrition data** (USDA FoodData Central)
2. **Real-time LLM food queries** (OpenNutrition MCP)
3. **Supplement ingredient validation** (NIH DSLD reference)

## Data Sources (Max 3 - Key & Reputable)

### 1. USDA FoodData Central (Primary)
- **Source**: `data/usda-fdc-data/` (git submodule)
- **Repository**: https://github.com/mkayeterry/usda-fdc-data
- **Content**:
  - Foundation foods with full nutrient profiles
  - Branded food products (900k+ items)
  - SR Legacy database (historical reference)
- **Use Cases**:
  - Nutrient lookup for dietary recommendations
  - RDA/DV calculations for deficiency detection
  - Food-to-nutrient mapping for meal analysis
- **Format**: CSV (cleaned, stacked dataset)
- **Update Frequency**: Quarterly from USDA

### 2. OpenNutrition MCP (LLM Integration)
- **Source**: `data/mcp-opennutrition/` (git submodule)
- **Repository**: https://github.com/deadletterq/mcp-opennutrition
- **Content**:
  - 300,000+ food items with nutritional profiles
  - Barcode (EAN-13) lookup capability
  - Macronutrients, vitamins, minerals
- **Use Cases**:
  - Real-time LLM food queries via MCP protocol
  - Recipe nutrition analysis
  - Barcode-based food identification
- **Format**: SQLite database + MCP server (Node.js)
- **Integration**: MCP protocol for Claude/LLM agents

### 3. NIH Dietary Supplement Label Database (Reference)
- **Source**: API reference (not submodule - external API)
- **URL**: https://dsld.od.nih.gov/
- **Content**:
  - 100,000+ supplement product labels
  - Ingredient amounts and daily values
  - Health claims and warnings
- **Use Cases**:
  - Validate supplement recommendations
  - Cross-reference ingredient dosages
  - Check for contraindications
- **Format**: REST API (JSON)
- **Note**: Used as reference/validation layer, not primary RAG source

## Future Data Source: Custom Shopify Wellness Products

In addition to open-source databases, the system will integrate:
- **Syntropy Health Shopify Store**: Custom wellness products
- **Purpose**: Product recommendations aligned with business offerings
- **Integration**: Shopify GraphQL API → Health Store Agent

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Load USDA nutrition data into vector store for RAG queries | P0 |
| FR-2 | Enable MCP-based food lookups from OpenNutrition | P0 |
| FR-3 | Map nutrient deficiencies to food/supplement recommendations | P0 |
| FR-4 | Support barcode-based food identification | P1 |
| FR-5 | Validate supplement dosages against NIH DSLD | P1 |
| FR-6 | Integrate Shopify product catalog as recommendation source | P1 |

### Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | RAG query latency | < 500ms |
| NFR-2 | Data freshness | Updated quarterly |
| NFR-3 | Nutrient coverage | 40+ nutrients |
| NFR-4 | Food item coverage | 300k+ items |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Diet Insight Engine                          │
├─────────────────────────────────────────────────────────────────┤
│  SDO Engine (Symptom-Diet Optimizer)                            │
│  ├── SymptomAnalyzer (LLM-powered)                              │
│  ├── DietRecommender ◄──────────────────────────────────────┐   │
│  └── PatternCorrelator                                      │   │
├─────────────────────────────────────────────────────────────┼───┤
│  RAG Layer                                                  │   │
│  ├── USDA Vector Store (ChromaDB/Pinecone)                  │   │
│  ├── OpenNutrition MCP Client ──────────────────────────────┤   │
│  └── NIH DSLD API Client                                    │   │
├─────────────────────────────────────────────────────────────────┤
│  Data Sources                                                   │
│  ├── data/usda-fdc-data/ (submodule)                            │
│  ├── data/mcp-opennutrition/ (submodule)                        │
│  └── data/shopify/ (future - custom products)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Nutrient-symptom mappings | 8 | 40+ |
| Food recommendations per query | 6 | 20+ |
| Recommendation confidence | 0.6 (fallback) | 0.85+ |
| Data source citations | None | 100% |

## Timeline

| Phase | Deliverable | Duration |
|-------|-------------|----------|
| Phase 1 | USDA data ingestion + vector store | 1 week |
| Phase 2 | MCP integration for LLM queries | 1 week |
| Phase 3 | Shopify product catalog integration | 1 week |
| Phase 4 | NIH DSLD validation layer | 2 weeks |

## Dependencies

- ChromaDB or Pinecone for vector storage
- Node.js 20+ for MCP server
- Shopify API credentials (for Phase 3)
