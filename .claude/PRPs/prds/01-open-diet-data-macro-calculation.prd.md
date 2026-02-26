# Open Diet Data - Full Macro Calculation Engine

## Problem Statement

The Open Diet Data repository aggregates 1.3M+ food items from USDA FoodData Central, OpenNutrition, and NIH DSLD, but the existing MCP interface (mcp-opennutrition) only supports basic food search and lookup. It cannot calculate full macronutrient profiles, combine multi-ingredient meals, or provide the structured nutritional data that downstream services (DIET, Chrome Shrine) need to generate personalized recommendations. Without this, every downstream service must independently solve nutrition math — or ship without it.

## Evidence

- Current MCP tools: search_foods, browse_foods, get_food, barcode_lookup — no calculation endpoints
- Diet Insight Engine TODOs explicitly list "Macro calculation missing in nutritional data"
- Chrome Shrine analyzes food images via GPT-4 Vision but has no structured nutrition data pipeline to validate against
- Assumption - needs validation: volume of queries expected from Chrome Shrine + DIET in beta

## Proposed Solution

Extend the mcp-opennutrition MCP server with macro calculation capabilities: per-food macro breakdown, multi-ingredient meal composition, daily intake aggregation, and nutrient gap analysis against standard RDAs. Expose these as new MCP tools that any service in the monorepo can call.

## Key Hypothesis

We believe adding macro calculation tools to the Open Diet Data MCP will enable downstream services (DIET, Chrome Shrine) to provide quantified nutritional recommendations instead of qualitative guesses.
We'll know we're right when DIET can return specific macro breakdowns in API responses and Chrome Shrine can show per-food nutritional scores.

## What We're NOT Building

- Custom meal planning algorithms — that's DIET's job
- User-facing UI for nutrition data — consumers are other services
- New data source integrations (Shopify products) — separate PRD
- Proprietary nutrition scoring system — use standard RDA/DRI

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| MCP tools available | 4+ new calculation tools | Tool count in MCP manifest |
| Query response time | <200ms p95 for single food macro lookup | Logging |
| Data coverage | 90%+ of USDA foods return complete macros | Automated audit script |
| Downstream adoption | DIET + Chrome Shrine both consuming | Integration tests |

## Open Questions

- [ ] How to handle foods with incomplete nutritional data across sources? Fallback strategy?
- [ ] Should we pre-compute and cache macro profiles or calculate on-the-fly?
- [ ] What's the merge strategy when USDA and OpenNutrition disagree on values for the same food?
- [ ] Do we need portion size normalization across data sources?

---

## Users & Context

**Primary User**
- **Who**: Internal services (DIET API, Chrome Shrine, Syntropy-Journal)
- **Current behavior**: DIET uses LLM to approximate nutrition; Chrome Shrine uses GPT-4 Vision with no nutrition ground truth
- **Trigger**: Any food analysis, diet recommendation, or shopping insight request
- **Success state**: Structured JSON response with complete macro/micronutrient profile per food item

**Job to Be Done**
When a service needs nutritional data for a food item or meal, I want to query a single MCP endpoint, so I can get accurate, structured macros without LLM approximation.

**Non-Users**
End users do not interact with this directly. This is infrastructure.

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | Single food macro lookup (protein, carbs, fat, calories, fiber) | Foundation for all downstream |
| Must | Multi-ingredient meal macro aggregation | Users eat meals, not isolated foods |
| Must | Nutrient gap analysis against RDA/DRI targets | Core to actionable insight generation |
| Should | Portion size normalization (grams, oz, cups, servings) | Real-world usability |
| Should | Cross-source data reconciliation (USDA vs OpenNutrition) | Data accuracy |
| Could | Micronutrient lookup (vitamins, minerals) | Biohacker audience wants depth |
| Could | Supplement-food interaction flags via NIH DSLD | Safety layer |
| Won't | Meal planning or recommendation logic — DIET's domain | Separation of concerns |

### MVP Scope

4 new MCP tools: `calculate_macros` (single food), `calculate_meal_macros` (ingredient list), `nutrient_gap_analysis` (against RDA), `get_full_nutrition_profile` (macros + micros). All reading from existing SQLite + CSV data.

### User Flow

1. Service calls `calculate_macros` with food name or ID
2. MCP resolves food across USDA/OpenNutrition sources
3. Returns structured JSON: { calories, protein_g, carbs_g, fat_g, fiber_g, ... }
4. For meals: service calls `calculate_meal_macros` with ingredient list + portions
5. MCP sums and returns aggregate profile

---

## Technical Approach

**Feasibility**: HIGH

**Architecture Notes**
- Extend existing Node.js MCP server (mcp-opennutrition/src/)
- Add calculation layer on top of existing SQLite queries
- Use USDA as primary source, OpenNutrition as fallback
- NIH DSLD for supplement-specific queries only

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Incomplete nutrition data for some foods | HIGH | Graceful degradation: return available fields, flag missing |
| Cross-source data conflicts | MEDIUM | Priority system: USDA > OpenNutrition, log conflicts |
| Performance at scale | LOW | Pre-compute popular food profiles, cache results |

---

## Implementation Phases

| # | Phase | Description | Status | Parallel | Depends | PRP Plan |
|---|-------|-------------|--------|----------|---------|----------|
| 1 | Data audit | Audit macro completeness across all 3 sources | complete | - | - | [01-open-diet-data-macro-calculation.plan.md](../plans/01-open-diet-data-macro-calculation.plan.md) |
| 2 | Core calculation tools | Implement calculate_macros + calculate_meal_macros | complete | - | 1 | [01-open-diet-data-macro-calculation.plan.md](../plans/01-open-diet-data-macro-calculation.plan.md) |
| 3 | Nutrient analysis tools | Implement nutrient_gap_analysis + get_full_nutrition_profile | complete | with 2 | 1 | [01-open-diet-data-macro-calculation.plan.md](../plans/01-open-diet-data-macro-calculation.plan.md) |
| 4 | Integration testing | Test with DIET + Chrome Shrine consumers | complete | - | 2, 3 | [01-open-diet-data-macro-calculation.plan.md](../plans/01-open-diet-data-macro-calculation.plan.md) |

### Phase Details

**Phase 1: Data Audit**
- **Goal**: Understand data completeness before building
- **Scope**: Script to audit % of foods with complete macros per source
- **Success signal**: Report showing coverage per nutrient per source

**Phase 2: Core Calculation Tools**
- **Goal**: Basic macro lookup and meal aggregation
- **Scope**: 2 new MCP tools with tests
- **Success signal**: MCP tools callable and returning correct data

**Phase 3: Nutrient Analysis Tools**
- **Goal**: RDA comparison and full profiles
- **Scope**: 2 more MCP tools
- **Success signal**: Nutrient gap analysis returns meaningful results

**Phase 4: Integration Testing**
- **Goal**: Verify downstream services can consume
- **Scope**: Integration tests from DIET and Chrome Shrine
- **Success signal**: End-to-end test passing

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Extend MCP vs new service | Extend MCP | Standalone API, embed in DIET | MCP is already the data access pattern; keeps nutrition logic centralized |
| Primary data source | USDA FDC | OpenNutrition, custom | Largest coverage (900K), public domain, most complete macro data |
| Calculation approach | On-the-fly with caching | Pre-computed database | Simpler to start; can optimize later if needed |

---

## Research Summary

**Market Context**
No competitor browser extension offers structured nutrition data at point-of-purchase. FoodHealth.co does basic scoring but not personalized macro analysis. This is the data foundation that differentiates.

**Technical Context**
- mcp-opennutrition is a working Node.js MCP server with SQLite backend
- USDA data is in CSV at `output/usda/usda_food_nutrition_data.csv`
- OpenNutrition data in `mcp-opennutrition/build/opennutrition.db`
- NIH DSLD is accessed via REST API (no local storage)

---

*Generated: 2026-02-25*
*Status: DRAFT - needs validation*
*Priority: P0 - Foundation*
*Master PRD: beta-release-master.prd.md*
