# Proposal: Divergence Comparison Tool

## Problem

When comparing two orchestration runs, we currently do manual shell one-liners. The results are inconsistent, hard to reproduce, and use the wrong metric (Jaccard file overlap) which penalizes naming differences that are functionally equivalent.

## Solution

A `set-compare` CLI tool that produces a structured, reproducible divergence report. Measures only what is **objectively verifiable** from an architect's perspective.

## Metrics

### 1. Route Coverage (weight: high)
Compare the set of URL paths each run serves. A page at `src/app/(shop)/products/[id]/page.tsx` = route `/products/[id]`. API routes similarly. Route groups stripped — we compare effective URLs, not filesystem paths.
- **Output**: common routes, only-A routes, only-B routes, overlap %

### 2. Schema Equivalence (weight: high)
Compare Prisma schema model names, enum names, and relation fields. Ignore whitespace, field ordering, and formatting. Only structural identity matters.
- **Output**: common models, only-A models, only-B models, relation diff

### 3. Dependency Set (weight: medium)
Compare `package.json` dependencies + devDependencies. Exact package name match.
- **Output**: common deps, only-A deps, only-B deps, overlap %

### 4. Functional Categories (weight: medium)
Count files by role: pages, API routes, server actions, feature components, UI primitives, lib utilities, layouts, middleware, unit tests, E2E tests. Compare counts.
- **Output**: category count table, diff per category

### 5. Template Compliance (weight: medium)
Check if template files deployed by `set-project init` are unchanged. Diff each template against the run's version.
- **Output**: per-file status (unchanged/modified/deleted), compliance %

### 6. Convention Compliance (weight: low)
Check structural conventions: route groups used? Actions collocated (no `src/actions/`)? `prisma.ts` not `db.ts`? Feature components collocated?
- **Output**: per-convention pass/fail, compliance %

## Output Format

### JSON (machine-readable)
```json
{
  "runs": ["minishop-run12", "minishop-run13"],
  "metrics": {
    "route_coverage": { "overlap_pct": 85, "common": 17, ... },
    "schema_equivalence": { "models_match": true, ... },
    ...
  },
  "weighted_score": 86,
  "summary": "Structurally equivalent with minor API route differences"
}
```

### Markdown (human-readable report)
Generated to stdout or file. Readable format with tables, suitable for pasting into docs or PR descriptions.

## CLI Interface

```bash
# Compare two runs by project name
set-compare minishop-run12 minishop-run13

# Output JSON instead of markdown
set-compare minishop-run12 minishop-run13 --json

# Save report to file
set-compare minishop-run12 minishop-run13 --output docs/comparison.md

# Compare two arbitrary directories
set-compare --dir /path/to/run-a --dir /path/to/run-b
```

## Scope

- Python CLI tool in `bin/set-compare`
- Core comparison logic in `lib/set_orch/compare.py`
- No external dependencies beyond what set-core already uses
- Works on any two Next.js project directories (not just registered projects)
