# Figma Source Dispatch Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Source file discovery from figma-raw directory
The design bridge SHALL discover Figma source files by searching for `docs/figma-raw/*/sources/` directories relative to the project root. When multiple figma-raw directories exist (multiple design files), all sources directories SHALL be searched.

#### Scenario: Sources directory exists with files
- **WHEN** the project contains `docs/figma-raw/<key>/sources/` with `.tsx`, `.ts`, `.css` files
- **THEN** `design_sources_for_dispatch()` SHALL return a list of available source file paths

#### Scenario: No figma-raw directory exists
- **WHEN** the project has no `docs/figma-raw/` directory
- **THEN** `design_sources_for_dispatch()` SHALL return empty string and exit code 1

### Requirement: UI primitive exclusion
Source files under `*/ui/*` paths (e.g., `src__components__ui__button.tsx`) SHALL be excluded from matching. These are shadcn/ui primitives that provide no project-specific design information and would waste context budget.

#### Scenario: shadcn button.tsx excluded
- **WHEN** source directory contains `src__components__ui__button.tsx` and scope mentions "button"
- **THEN** the file SHALL NOT be included in results (it is a UI primitive, not a project component)

#### Scenario: project-level ProductCard.tsx included
- **WHEN** source directory contains `src__components__ProductCard.tsx` and scope mentions "product"
- **THEN** the file SHALL be included (it is a project component, not under `/ui/`)

### Requirement: Scope-based source file matching
The bridge SHALL match source files against change scope text using keyword extraction. Source filenames are path-encoded (e.g., `src__app__components__ProductCard.tsx`) — the bridge SHALL decode these by splitting on `__` and matching individual path segments against scope keywords.

#### Scenario: Scope mentions "product" and "card"
- **WHEN** scope text contains "product" and source directory has `src__components__ProductCard.tsx`
- **THEN** the file SHALL be included in matched results

#### Scenario: Scope mentions "cart"
- **WHEN** scope text contains "cart" and source directory has `src__app__Cart.tsx` and `src__app__data__mockData.ts`
- **THEN** `Cart.tsx` SHALL be included; `mockData.ts` SHALL also be included (matches as shared data file)

#### Scenario: No keyword matches
- **WHEN** scope text contains only infrastructure terms ("prisma", "jest", "config") with no UI component matches
- **THEN** no source files SHALL be returned (empty output, exit code 1)

### Requirement: Source file content output format
Matched source files SHALL be output as markdown with clear file headers. Each file SHALL be prefixed with `## Figma Source: <decoded-filename>` followed by a fenced code block.

#### Scenario: Two files matched
- **WHEN** `ProductCard.tsx` and `mockData.ts` match the scope
- **THEN** output SHALL contain two sections, each with `## Figma Source: src/components/ProductCard.tsx` header (decoded from `__` to `/`) and the file content in a code block

### Requirement: Total output budget of 300 lines
The bridge SHALL enforce a 300-line maximum for source file output. Files SHALL be prioritized by relevance score (keyword match count), then by size (smaller files first). When the budget is exceeded, remaining files SHALL be listed by name only with a note to read them directly.

#### Scenario: Budget exceeded
- **WHEN** 5 files match with total 500 lines
- **THEN** the most relevant files fitting within 300 lines SHALL be included in full, remaining files SHALL be listed as "Also relevant: <filename>" without content

### Requirement: Shared data files always included
Files matching `*mockData*`, `*data*`, `*types*`, or `*models*` patterns SHALL always be included when at least one non-data source file matches the scope (i.e., when the function would return any content). These files define the data model that UI components consume.

#### Scenario: Product page scope with mockData
- **WHEN** scope mentions "product catalog" and `src__app__data__mockData.ts` exists in sources
- **THEN** `mockData.ts` SHALL be included even though "mockData" doesn't appear in scope text
