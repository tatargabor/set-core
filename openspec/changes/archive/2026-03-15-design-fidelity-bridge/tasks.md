**Dependencies:** Groups 1-2 (bridge.sh) must precede groups 3-4 (Python integration) and 7.2-7.5 (tests). Group 6 (set-project-web) is independent. Task 7.1 (fixture creation) can precede groups 1-2.

## 1. Source File Discovery & Matching (bridge.sh)

- [x] 1.1 Add `design_sources_for_dispatch()` function to `lib/design/bridge.sh` — discovers `docs/figma-raw/*/sources/` directories, lists all source files
- [x] 1.2 Exclude UI primitives — filter out files with `/ui/` in decoded path (e.g., `src__components__ui__button.tsx`) to avoid injecting shadcn internals
- [x] 1.3 Implement keyword extraction from scope text — split scope into meaningful words, normalize case
- [x] 1.4 Implement filename matching — decode `__`-separated paths, match against scope keywords; always include `*mockData*`, `*data*`, `*types*`, `*models*` files when at least one non-data file matches
- [x] 1.5 Implement relevance scoring — count keyword matches per file, sort by score then by file size (smaller first)
- [x] 1.6 Implement 300-line budget enforcement — include full content for top files, list remaining as "Also relevant: <name>" when budget exceeded
- [x] 1.7 Format output as markdown — `## Figma Source: <decoded-path>` header + fenced code block per file
- [x] 1.8 Update `design_context_for_dispatch()` — change `max_lines` from 150 to 100 to accommodate source file budget in the 500-line total

## 2. Data Model Extraction for Planner (bridge.sh)

- [x] 2.1 Add `design_data_model_section()` function to `lib/design/bridge.sh` — finds data/model/types source files, extracts TypeScript interface blocks and `export const` array names
- [x] 2.2 Extract entity names from array literals (e.g., product names from `const products = [{ name: "..." }]`) — output as "Seed data names: ..." list
- [x] 2.3 Integrate into `design_prompt_section()` — append "## Design Data Model" section after snapshot content when data model files exist

## 3. Dispatcher Integration (dispatcher.py)

- [x] 3.1 In `dispatcher.py` dispatch context building, call `design_sources_for_dispatch` after existing `design_context_for_dispatch` call — pass scope text and snapshot dir; use 10-second timeout (source file reading is slower than token extraction)
- [x] 3.2 Append matched source file content to `ctx.design_context` — concatenate tokens + hierarchy + sources
- [x] 3.3 Enforce 500-line total budget — tokens ~100, hierarchy max 100 (unconditional, task 1.8), sources max 300

## 4. Planner Integration (planner.py)

- [x] 4.1 In `planner.py` `run_planning_loop()`, after `_fetch_design_context()` call, run `design_data_model_section()` via bridge.sh subprocess and append result to `design_context` variable (NOT inside `_fetch_design_context()` — keep that function as snapshot-only reader)
- [x] 4.2 Add planner instruction text in `templates.py` `render_planning_prompt()`: "When Design Data Model section is present, embed entity field names and seed data names from design interfaces into each change scope description. The implementing agent will NOT see this section — only your scope text."

## 5. Enhanced Design Review (bridge.sh + verifier.py)

- [x] 5.1 Add icon extraction logic to `build_design_review_section()` — parse source files for `import { ... } from 'lucide-react'`, build "Icon Usage" checklist mapping `<icon> (<source-filename>)` per entry
- [x] 5.2 Add image/thumbnail pattern extraction — find `w-N h-N` classes on `img` elements, report as "Image Patterns" checklist
- [x] 5.3 Add layout pattern extraction — find grid/flex container patterns with specific classes, report key layout structures
- [x] 5.4 Append "Component Structure" subsection to review output — all items reported as [WARNING] severity

## 6. set-project-web Rule Updates

- [x] 6.1 Update `set-project-web/templates/nextjs/rules/design-integration.md` — add "## Figma Source Files" section: when `docs/figma-raw/*/sources/` exists, agents MUST read matched source files before implementing; source files are ground-truth for component structure, icon usage, data model fields, and layout patterns
- [x] 6.2 Update `set-project-web/templates/nextjs/rules/ui-conventions.md` — add note under Icons section: when design source files specify particular icons (e.g., `ShoppingBag` for cart), use those exact icons; design source files override generic conventions

## 7. Testing

- [x] 7.1 Create test fixture: minimal `docs/figma-raw/TEST/sources/` with sample files (ProductCard.tsx, mockData.ts, Cart.tsx, button.tsx under ui/) — representative of real Figma output including shadcn primitives
- [x] 7.2 Test `design_sources_for_dispatch` — scope "product catalog" matches ProductCard.tsx + mockData.ts; scope "cart feature" matches Cart.tsx + mockData.ts; scope "prisma config" matches nothing; ui/button.tsx never included
- [x] 7.3 Test `design_data_model_section` — extracts interfaces and entity names from mockData.ts fixture
- [x] 7.4 Test budget enforcement — create fixture with 10 large files, verify output stays within 300 lines
- [x] 7.5 Test icon extraction in `build_design_review_section` — verify lucide-react imports are parsed into checklist format with source file attribution
