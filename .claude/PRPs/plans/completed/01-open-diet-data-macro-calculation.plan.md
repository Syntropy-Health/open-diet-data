# Feature: Open Diet Data - Full Macro Calculation Engine

## Summary

Extend the mcp-opennutrition MCP server with 4 new tools for macro calculation: single food macro lookup, multi-ingredient meal aggregation, nutrient gap analysis against RDA targets, and full nutrition profile retrieval. All tools read from the existing OpenNutrition SQLite database, with the USDA CSV as a secondary enrichment source. This covers all 4 phases of PRD-01.

## User Story

As an internal service (DIET API, Chrome Shrine, Syntropy-Journal)
I want to query structured macronutrient data via MCP tools
So that I can provide quantified nutritional recommendations instead of LLM approximations

## Problem Statement

The MCP server has 4 lookup tools but zero calculation tools. Downstream services cannot get macro breakdowns, meal totals, or nutrient gap analysis without independently solving nutrition math.

## Solution Statement

Add 4 new MCP tools to `src/index.ts` with supporting query methods in `SQLiteDBAdapter.ts`. Implement a data audit script, RDA reference data, and basic test infrastructure.

## Metadata

| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | MEDIUM |
| Systems Affected | mcp-opennutrition (Node.js MCP server) |
| Dependencies | @modelcontextprotocol/sdk ^1.12.1, better-sqlite3 ^11.8.1, zod ^3.24.1 |
| Estimated Tasks | 12 |

---

## UX Design

### Before State

```
Service calls search-food-by-name("chicken breast")
  -> Returns: { id, name, nutrition_100g: { energy: 165, protein: 31, fat: 3.6, ... } }
  -> Service must: manually parse JSON, do its own math for meals, guess at RDA gaps
  -> No meal aggregation, no portion normalization, no gap analysis
```

### After State

```
Service calls calculate-macros("chicken breast", 200)
  -> Returns: { food_name, portion_g: 200, macros: { calories: 330, protein_g: 62, ... } }

Service calls calculate-meal-macros([{food: "chicken breast", grams: 200}, {food: "rice", grams: 150}])
  -> Returns: { total_macros: { calories: 525, protein_g: 68, ... }, per_ingredient: [...] }

Service calls nutrient-gap-analysis({consumed: [...], target: "adult_male"})
  -> Returns: { gaps: [{ nutrient: "fiber", consumed_g: 12, target_g: 30, deficit_pct: 60 }], ... }

Service calls get-full-nutrition-profile("chicken breast")
  -> Returns: { macros: {...}, micros: { calcium_mg: 15, iron_mg: 1.0, ... }, data_completeness: 0.92 }
```

### Interaction Changes

| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| MCP tool list | 4 tools (search, browse, get, barcode) | 8 tools (+calculate-macros, calculate-meal-macros, nutrient-gap-analysis, get-full-nutrition-profile) | Services get structured calculations |
| DIET service | LLM approximates nutrition | Calls MCP for ground truth | Accurate recommendations |
| Chrome Shrine | GPT-4 Vision guesses macros | Calls MCP for real data | Trustworthy popup data |

---

## Mandatory Reading

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `mcp-opennutrition/src/index.ts` | 1-214 | ALL tool registration patterns -- MIRROR exactly |
| P0 | `mcp-opennutrition/src/SQLiteDBAdapter.ts` | 1-110 | ALL query patterns -- MIRROR exactly |
| P1 | `mcp-opennutrition/scripts/tsv-to-sqlite.ts` | 60-113 | Understand table schema creation |
| P1 | `mcp-opennutrition/package.json` | all | Build scripts and dependencies |
| P2 | `mcp-opennutrition/tsconfig.json` | all | TypeScript compilation config |

**External Documentation:**

| Source | Section | Why Needed |
|--------|---------|------------|
| [MCP SDK Tool Registration](https://modelcontextprotocol.io/docs/concepts/tools) | Tool definition | Confirm tool() API signature |
| [better-sqlite3 API](https://github.com/WiseLibs/better-sqlite3/blob/master/docs/api.md) | prepare, all, get | SQLite query patterns |
| [Zod v3.24 docs](https://zod.dev) | Object schemas | Input validation |

---

## Patterns to Mirror

**TOOL_REGISTRATION:**
```typescript
// SOURCE: mcp-opennutrition/src/index.ts:40-73
this.server.tool(
  "search-food-by-name",
  `MANDATORY: Use this tool when...`,
  SearchFoodByNameRequestSchema.shape,
  { title: "Search food by name", readOnlyHint: true },
  async (args, extra) => {
    const foods = await this.db.searchByName(args.query, args.page, args.pageSize);
    return {
      content: [{ type: "text", text: JSON.stringify(foods, null, 2) }],
      structuredContent: { foods },
    };
  }
);
```

**ZOD_SCHEMA:**
```typescript
// SOURCE: mcp-opennutrition/src/index.ts:7-14
const SearchFoodByNameRequestSchema = z.object({
  query: z.string().min(1, 'Search query must not be empty'),
  page: z.number().min(1).optional().default(1),
  pageSize: z.number().optional().default(5),
});
```

**DB_QUERY:**
```typescript
// SOURCE: mcp-opennutrition/src/SQLiteDBAdapter.ts:43-65
async searchByName(query: string, page: number, pageSize: number): Promise<FoodItem[]> {
  const offset = (page - 1) * pageSize;
  const selectClause = this.getFoodItemSelectClause();
  const terms = query.trim().split(/\s+/);
  // ... build WHERE clause with LIKE per term
  const rows = this.db.prepare(`SELECT DISTINCT ${selectClause} FROM foods ... LIMIT ? OFFSET ?`).all(...params);
  return rows.map(this.deserializeRow);
}
```

**RETURN_SHAPE:**
```typescript
// SOURCE: mcp-opennutrition/src/index.ts:67-71
return {
  content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
  structuredContent: { result },
};
```

---

## Files to Change

| File | Action | Justification |
|------|--------|---------------|
| `mcp-opennutrition/src/index.ts` | UPDATE | Add 4 new Zod schemas + 4 new tool registrations |
| `mcp-opennutrition/src/SQLiteDBAdapter.ts` | UPDATE | Add 4 new query/calculation methods |
| `mcp-opennutrition/src/rda.ts` | CREATE | RDA/DRI reference data (static constants) |
| `mcp-opennutrition/src/types.ts` | CREATE | Shared TypeScript interfaces for macro results |
| `scripts/audit-data-completeness.ts` | CREATE | Data audit script (Phase 1) |
| `mcp-opennutrition/src/__tests__/calculation.test.ts` | CREATE | Unit tests for calculation methods |
| `mcp-opennutrition/package.json` | UPDATE | Add test script if vitest/jest needed |

---

## NOT Building (Scope Limits)

- Meal planning or recommendation algorithms -- DIET service's domain
- User-facing UI -- consumers are internal services only
- USDA data loading into SQLite -- USDA stays as CSV; OpenNutrition DB is primary
- Proprietary nutrition scoring -- use standard RDA/DRI
- Supplement-food interaction checking -- future scope
- Portion size database (cups, tablespoons) -- use grams only for MVP; portion conversion is future

---

## Step-by-Step Tasks

### Phase 1: Data Audit

#### Task 1: CREATE `scripts/audit-data-completeness.ts`

- **ACTION**: Create a TypeScript script that audits the OpenNutrition SQLite database for macro nutrient completeness
- **IMPLEMENT**:
  - Open `data_local/opennutrition_foods.db` (same path pattern as SQLiteDBAdapter)
  - Count total foods
  - For each key nutrient (`energy`, `protein`, `carbohydrates`, `fat`, `fiber`, `sugars`, `salt`, `saturated-fat`), count how many foods have a non-null, non-zero value in `nutrition_100g` JSON
  - Output: table showing nutrient -> count -> percentage coverage
  - Also audit: how many foods have `serving` data (for future portion normalization)
- **MIRROR**: Use `better-sqlite3` same as `SQLiteDBAdapter.ts` -- `new Database(dbPath, {readonly: true})`
- **IMPORTS**: `import Database from 'better-sqlite3'`, `import path from 'path'`, `import { fileURLToPath } from 'url'`
- **VALIDATE**: `npx tsx scripts/audit-data-completeness.ts` runs and outputs a coverage report

#### Task 2: Analyze audit results and document

- **ACTION**: Run the audit script, capture output
- **IMPLEMENT**: Save results to `docs/data-audit-results.md` with coverage percentages
- **VALIDATE**: File exists with actual data

### Phase 2: Core Calculation Tools

#### Task 3: CREATE `mcp-opennutrition/src/types.ts`

- **ACTION**: Create shared TypeScript interfaces for macro calculation results
- **IMPLEMENT**:
  ```typescript
  export interface MacroResult {
    food_id: string;
    food_name: string;
    portion_g: number;
    macros: {
      calories: number;
      protein_g: number;
      carbs_g: number;
      fat_g: number;
      fiber_g: number;
      sugar_g: number;
    };
    data_completeness: number; // 0-1, fraction of fields that had data
    source: 'opennutrition' | 'usda';
  }

  export interface MealMacroResult {
    total_macros: MacroResult['macros'];
    per_ingredient: MacroResult[];
    total_portion_g: number;
    ingredient_count: number;
  }

  export interface NutrientGap {
    nutrient: string;
    consumed: number;
    target: number;
    unit: string;
    deficit_pct: number; // positive = deficit, negative = surplus
    status: 'deficient' | 'adequate' | 'excess';
  }

  export interface NutrientGapResult {
    target_profile: string;
    gaps: NutrientGap[];
    overall_score: number; // 0-1, fraction of nutrients meeting target
  }

  export interface FullNutritionProfile {
    food_id: string;
    food_name: string;
    per_100g: Record<string, number>;
    macros: MacroResult['macros'];
    micros: Record<string, { value: number; unit: string }>;
    data_completeness: number;
    source: string;
  }
  ```
- **VALIDATE**: `npx tsc --noEmit`

#### Task 4: ADD calculation methods to `mcp-opennutrition/src/SQLiteDBAdapter.ts`

- **ACTION**: Add 4 new methods to SQLiteDBAdapter class
- **IMPLEMENT**:
  - `async calculateMacros(query: string, portionGrams: number): Promise<MacroResult | null>` -- search food by name (reuse searchByName logic), extract `nutrition_100g`, scale by `portionGrams / 100`, return structured MacroResult
  - `async calculateMealMacros(ingredients: Array<{food: string, grams: number}>): Promise<MealMacroResult>` -- call calculateMacros per ingredient, sum totals
  - `async getFullNutritionProfile(query: string): Promise<FullNutritionProfile | null>` -- search food, return ALL nutrition_100g fields categorized into macros + micros
- **MIRROR**: Follow existing method patterns -- use `this.getFoodItemSelectClause()`, `this.deserializeRow()`, same SQL patterns
- **GOTCHA**: `nutrition_100g` values are per 100g in OpenNutrition. Scale: `value * portionGrams / 100`
- **GOTCHA**: Handle null/missing nutrition data gracefully -- return `data_completeness` score
- **IMPORTS**: `import { MacroResult, MealMacroResult, FullNutritionProfile } from './types'`
- **VALIDATE**: `npx tsc --noEmit`

#### Task 5: CREATE `mcp-opennutrition/src/rda.ts`

- **ACTION**: Create RDA/DRI reference data
- **IMPLEMENT**: Static object with daily recommended values for adult males and adult females:
  ```typescript
  export const RDA_TARGETS: Record<string, Record<string, { value: number; unit: string }>> = {
    adult_male: {
      calories: { value: 2500, unit: 'kcal' },
      protein_g: { value: 56, unit: 'g' },
      carbs_g: { value: 130, unit: 'g' },
      fat_g: { value: 78, unit: 'g' },
      fiber_g: { value: 30, unit: 'g' },
      // ... vitamins and minerals from standard RDA tables
    },
    adult_female: { ... }
  };
  ```
- **VALIDATE**: `npx tsc --noEmit`

#### Task 6: ADD `calculate-macros` tool to `mcp-opennutrition/src/index.ts`

- **ACTION**: Register `calculate-macros` MCP tool
- **IMPLEMENT**:
  - Zod schema: `{ query: z.string().min(1), portion_grams: z.number().positive().optional().default(100) }`
  - Handler: calls `this.db.calculateMacros(args.query, args.portion_grams)`
  - Return: `{ content: [...], structuredContent: { result } }`
  - Description: `MANDATORY: Use this tool when the user wants to know the macronutrient breakdown (calories, protein, carbs, fat, fiber) of a specific food item. Optionally specify portion size in grams (default 100g).`
- **MIRROR**: Exact same registration pattern as `search-food-by-name`
- **VALIDATE**: `npm run build` succeeds

#### Task 7: ADD `calculate-meal-macros` tool to `mcp-opennutrition/src/index.ts`

- **ACTION**: Register `calculate-meal-macros` MCP tool
- **IMPLEMENT**:
  - Zod schema: `{ ingredients: z.array(z.object({ food: z.string().min(1), grams: z.number().positive() })).min(1) }`
  - Handler: calls `this.db.calculateMealMacros(args.ingredients)`
  - Description: `MANDATORY: Use this tool when the user wants to calculate total macronutrients for a meal consisting of multiple ingredients with specific portion sizes in grams.`
- **MIRROR**: Same registration pattern
- **VALIDATE**: `npm run build`

### Phase 3: Nutrient Analysis Tools

#### Task 8: ADD `nutrientGapAnalysis` method to `SQLiteDBAdapter.ts`

- **ACTION**: Add nutrient gap analysis method
- **IMPLEMENT**: `async nutrientGapAnalysis(consumed: Array<{nutrient: string, amount: number}>, targetProfile: string): Promise<NutrientGapResult>` -- compare consumed nutrients against RDA targets, calculate deficit percentages, classify as deficient/adequate/excess
- **IMPORTS**: `import { RDA_TARGETS } from './rda'`, `import { NutrientGapResult } from './types'`
- **VALIDATE**: `npx tsc --noEmit`

#### Task 9: ADD `nutrient-gap-analysis` tool to `index.ts`

- **ACTION**: Register `nutrient-gap-analysis` MCP tool
- **IMPLEMENT**:
  - Zod schema: `{ consumed: z.array(z.object({ nutrient: z.string(), amount: z.number() })).min(1), target_profile: z.enum(['adult_male', 'adult_female']).optional().default('adult_male') }`
  - Handler: calls `this.db.nutrientGapAnalysis(args.consumed, args.target_profile)`
  - Description: `MANDATORY: Use this tool to compare a user's consumed nutrients against recommended daily allowances (RDA). Identifies deficiencies and excesses.`
- **VALIDATE**: `npm run build`

#### Task 10: ADD `get-full-nutrition-profile` tool to `index.ts`

- **ACTION**: Register `get-full-nutrition-profile` MCP tool
- **IMPLEMENT**:
  - Zod schema: `{ query: z.string().min(1) }`
  - Handler: calls `this.db.getFullNutritionProfile(args.query)`
  - Description: `MANDATORY: Use this tool to get the complete nutritional profile of a food including all macronutrients and available micronutrients (vitamins, minerals).`
- **VALIDATE**: `npm run build`

### Phase 4: Testing

#### Task 11: CREATE test infrastructure

- **ACTION**: Add vitest or basic test runner
- **IMPLEMENT**:
  - Add `vitest` to devDependencies in `package.json`
  - Add `"test": "vitest run"` to scripts
  - Create `src/__tests__/calculation.test.ts` with tests for:
    - `calculateMacros` with known food (e.g., search "chicken" -> verify macros are positive numbers)
    - `calculateMealMacros` with 2 ingredients -> verify totals equal sum of parts
    - `nutrientGapAnalysis` with known consumed values -> verify gap calculations
    - `getFullNutritionProfile` -> verify returns macros + micros
    - Edge case: food not found -> returns null
    - Edge case: food with missing nutrition data -> data_completeness < 1
- **VALIDATE**: `npm test` passes

#### Task 12: Integration verification

- **ACTION**: Test the MCP server with the inspector
- **IMPLEMENT**: Run `npm run inspector`, test each of the 4 new tools manually
- **VALIDATE**: All 8 tools (4 existing + 4 new) respond correctly via MCP inspector

---

## Testing Strategy

### Unit Tests to Write

| Test File | Test Cases | Validates |
|-----------|------------|-----------|
| `src/__tests__/calculation.test.ts` | calculateMacros happy path, not found, missing data | Macro calculation logic |
| `src/__tests__/calculation.test.ts` | calculateMealMacros with multiple ingredients | Meal aggregation math |
| `src/__tests__/calculation.test.ts` | nutrientGapAnalysis with known values | RDA comparison logic |
| `src/__tests__/calculation.test.ts` | getFullNutritionProfile completeness | Full profile assembly |

### Edge Cases Checklist

- [ ] Food with no `nutrition_100g` field -> return null/error with helpful message
- [ ] Food with partial nutrition data (e.g., has protein but no fiber) -> return available data + data_completeness < 1
- [ ] Zero portion grams -> Zod validation rejects (`.positive()`)
- [ ] Very large portion (10kg) -> should still calculate correctly
- [ ] Meal with one ingredient not found -> include error for that ingredient, still calculate rest
- [ ] RDA target profile not recognized -> Zod enum validation rejects
- [ ] Empty consumed array for gap analysis -> Zod min(1) rejects

---

## Validation Commands

### Level 1: STATIC_ANALYSIS

```bash
cd /home/mo/projects/SyntropyHealth/research/open-diet-data/mcp-opennutrition && npx tsc --noEmit
```

**EXPECT**: Exit 0, no type errors

### Level 2: UNIT_TESTS

```bash
cd /home/mo/projects/SyntropyHealth/research/open-diet-data/mcp-opennutrition && npm test
```

**EXPECT**: All tests pass

### Level 3: FULL_BUILD

```bash
cd /home/mo/projects/SyntropyHealth/research/open-diet-data/mcp-opennutrition && npm run build
```

**EXPECT**: Build succeeds, `build/index.js` exists

### Level 4: MCP_INSPECTOR

```bash
cd /home/mo/projects/SyntropyHealth/research/open-diet-data/mcp-opennutrition && npm run inspector
```

**EXPECT**: All 8 tools listed and callable

---

## Acceptance Criteria

- [ ] 4 new MCP tools registered and callable
- [ ] `calculate-macros` returns accurate macros for single food with portion scaling
- [ ] `calculate-meal-macros` correctly sums multi-ingredient meals
- [ ] `nutrient-gap-analysis` compares against RDA and identifies deficits
- [ ] `get-full-nutrition-profile` returns both macros and available micros
- [ ] Data completeness score accurately reflects missing fields
- [ ] `npm run build` succeeds
- [ ] Unit tests pass with >80% coverage of new code
- [ ] Data audit report exists documenting nutrient coverage

---

## Completion Checklist

- [ ] Phase 1: Data audit script created and run
- [ ] Phase 2: calculate-macros + calculate-meal-macros tools working
- [ ] Phase 3: nutrient-gap-analysis + get-full-nutrition-profile tools working
- [ ] Phase 4: Tests passing, MCP inspector verified
- [ ] Level 1: TypeScript compiles without errors
- [ ] Level 2: Unit tests pass
- [ ] Level 3: Full build succeeds
- [ ] Level 4: MCP inspector shows all 8 tools

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Many foods have incomplete nutrition_100g data | HIGH | MEDIUM | Data audit first (Task 1); return data_completeness score; graceful degradation |
| OpenNutrition nutrition_100g keys don't match expected names | MEDIUM | HIGH | Audit actual key names in Task 1; map to standard names in code |
| Performance with complex meal calculations | LOW | LOW | Each ingredient is a simple lookup + multiply; SQLite is fast for reads |
| Vitest setup in existing TypeScript project | LOW | LOW | Well-documented; tsconfig already targets ES2022 |

---

## Notes

- The OpenNutrition DB has ~300K foods with `nutrition_100g` as JSON. The USDA CSV has 900K+ foods with 70+ columns. For MVP, we use OpenNutrition DB only (it's already loaded in SQLite). USDA enrichment is future work.
- RDA values should come from standard USDA DRI tables. Start with adult male/female; add more profiles later.
- The `nutrient-gap-analysis` tool takes pre-computed consumed values (not raw food entries) -- the caller (DIET service) is responsible for tracking what the user consumed and summing before calling this tool.
- All new tools use `{ readOnlyHint: true }` options -- no writes to the DB.

---

*Generated: 2026-02-25*
*Source PRD: .claude/PRPs/prds/01-open-diet-data-macro-calculation.prd.md*
*Phases Covered: 1 (Data Audit), 2 (Core Calculation), 3 (Nutrient Analysis), 4 (Testing)*
*Confidence Score: 8/10 -- well-understood codebase with clear patterns; main risk is data completeness*
