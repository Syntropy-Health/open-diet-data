# Data Agent Specification - Diet Insight Engine

## Agent Overview

The **Nutrition Data Agent** is a specialized component of the Diet Insight Engine responsible for retrieving, processing, and serving nutrition data from multiple authoritative sources to power RAG-based dietary recommendations.

## Agent Identity

- **Name**: NutritionDataAgent
- **Type**: RAG Data Retrieval Agent
- **Parent System**: Diet Insight Engine (DIET)
- **Consumers**: SDO Engine, DietRecommender, SymptomAnalyzer

## Capabilities

### Core Functions

1. **Food Nutrition Lookup**
   - Query USDA FoodData Central for nutrient profiles
   - Return macro/micronutrient data for foods
   - Support fuzzy matching for food names

2. **MCP-Based Food Queries**
   - Connect to OpenNutrition MCP server
   - Enable Claude/LLM to query 300k+ foods
   - Support barcode-based lookups (EAN-13)

3. **Supplement Validation**
   - Cross-reference supplement recommendations with NIH DSLD
   - Validate dosage recommendations
   - Check for ingredient interactions

4. **Product Catalog Integration**
   - Query Shopify wellness products (future)
   - Map deficiencies to purchasable products
   - Support affiliate tracking

## Data Sources

| Source | Type | Location | Status |
|--------|------|----------|--------|
| USDA FoodData Central | Submodule | `data/usda-fdc-data/` | Active |
| OpenNutrition MCP | Submodule | `data/mcp-opennutrition/` | Active |
| NIH DSLD | External API | `https://dsld.od.nih.gov/` | Reference |
| Shopify Products | Future | `data/shopify/` | Planned |

## Integration Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                   NutritionDataAgent                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │ USDADataLoader  │  │ MCPFoodClient   │  │ DSLDClient  │  │
│  │                 │  │                 │  │             │  │
│  │ - load_csv()    │  │ - search()      │  │ - validate()│  │
│  │ - embed()       │  │ - get_by_id()   │  │ - lookup()  │  │
│  │ - query()       │  │ - barcode()     │  │             │  │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘  │
│           │                    │                   │        │
│           ▼                    ▼                   ▼        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Unified Nutrition Query Interface          ││
│  │                                                         ││
│  │  query_food(name) → NutrientProfile                     ││
│  │  query_nutrients(food_id) → List[Nutrient]              ││
│  │  recommend_foods(deficiency) → List[FoodRecommendation] ││
│  │  validate_supplement(product) → ValidationResult        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### NutrientProfile

```python
class NutrientProfile(BaseModel):
    food_id: str
    food_name: str
    source: Literal["usda", "opennutrition", "shopify"]
    nutrients: Dict[str, NutrientValue]
    serving_size: Optional[str]
    barcode: Optional[str]

class NutrientValue(BaseModel):
    name: str
    amount: float
    unit: str
    daily_value_pct: Optional[float]
```

### FoodRecommendation

```python
class FoodRecommendation(BaseModel):
    food_name: str
    nutrient_target: str
    nutrient_amount: float
    nutrient_unit: str
    serving_suggestion: str
    confidence: float
    source: str
    citation: Optional[str]
```

## MCP Configuration

To enable OpenNutrition MCP for LLM queries:

```json
{
  "mcp-opennutrition": {
    "command": "node",
    "args": ["data/mcp-opennutrition/build/index.js"]
  }
}
```

### MCP Tools Available

| Tool | Description | Example |
|------|-------------|---------|
| `search_foods` | Search by name/brand | "organic spinach" |
| `get_food` | Get by food ID | "food_12345" |
| `barcode_lookup` | Get by EAN-13 | "0042222850325" |
| `browse_foods` | Paginated food list | page=1, limit=20 |

## RAG Pipeline

### Vector Store Setup (USDA Data)

```python
# Pseudocode for USDA data ingestion
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

def ingest_usda_data():
    # Load cleaned USDA CSV
    df = pd.read_csv("data/usda-fdc-data/output/usda_food_nutrition_data.csv")

    # Create document chunks
    documents = []
    for _, row in df.iterrows():
        doc = Document(
            page_content=f"{row['food_name']}: {row['nutrients_summary']}",
            metadata={
                "fdc_id": row["fdc_id"],
                "category": row["category"],
                "source": "usda"
            }
        )
        documents.append(doc)

    # Embed and store
    vectorstore = Chroma.from_documents(
        documents,
        OpenAIEmbeddings(),
        collection_name="usda_foods"
    )
    return vectorstore
```

### Query Flow

1. User reports symptoms → SDO Analyzer identifies deficiencies
2. DietRecommender queries NutritionDataAgent
3. Agent searches USDA vector store for foods rich in target nutrients
4. Agent optionally queries MCP for additional foods
5. Results ranked and returned with citations

## Usage Examples

### Query Foods by Nutrient

```python
agent = NutritionDataAgent()

# Find iron-rich foods
results = await agent.recommend_foods(
    deficiency="iron",
    limit=10,
    dietary_restrictions=["vegetarian"]
)

# Returns:
[
    FoodRecommendation(
        food_name="Spinach, raw",
        nutrient_target="iron",
        nutrient_amount=2.71,
        nutrient_unit="mg",
        serving_suggestion="1 cup (30g)",
        confidence=0.92,
        source="usda",
        citation="FDC ID: 168462"
    ),
    ...
]
```

### MCP Food Search

```python
# Via MCP protocol
result = await mcp_client.call_tool(
    "search_foods",
    {"query": "salmon omega-3", "limit": 5}
)
```

## Setup Instructions

### 1. Initialize Submodules

```bash
cd diet-insight-engine
git submodule update --init --recursive
```

### 2. Generate USDA Dataset

```bash
cd data/usda-fdc-data
python usda_fdc_data/main.py --output_dir ../usda-processed
```

### 3. Build MCP Server

```bash
cd data/mcp-opennutrition
npm install
npm run build
```

### 4. Configure Vector Store

```bash
# Set up ChromaDB or Pinecone
python scripts/ingest_usda_data.py
```

## Future Enhancements

1. **Shopify Integration**: Add custom wellness products as recommendation source
2. **Symptom-Nutrient Mapping**: Build knowledge graph of symptom→deficiency→nutrient relationships
3. **Interaction Checking**: Flag supplement-drug interactions via NIH data
4. **Personalization**: User dietary preferences and restrictions filtering

## Related Components

- `diet_insight_engine/sdo/recommender.py` - Consumes nutrition data
- `diet_insight_engine/sdo/analyzer.py` - Identifies deficiencies
- `diet_insight_engine/health_store_agent/` - Product recommendations
