# Spec: Divergence Comparison Tool

## Metrics

### REQ-CMP-ROUTES: Route coverage comparison
- Extract all page.tsx → URL paths (strip route groups, convert [param] to :param)
- Extract all route.ts → API URL paths
- Compute: common set, only-A set, only-B set, overlap percentage
- Route groups `(shop)/`, `(auth)/`, `(dashboard)/` are stripped for comparison

### REQ-CMP-SCHEMA: Prisma schema equivalence
- Parse `prisma/schema.prisma` for model names and enum names
- Compare model sets (ignore field ordering, whitespace)
- Report: matching models, only-A models, only-B models
- If no schema file exists in either project, report "N/A" (not penalized)

### REQ-CMP-DEPS: Dependency set comparison
- Read `package.json` dependencies + devDependencies keys
- Compare as sets
- Report: common, only-A, only-B, overlap percentage

### REQ-CMP-CATEGORIES: Functional category counts
- Count files by role: pages, api_routes, actions, feature_components, ui_primitives, lib_files, layouts, middleware, unit_tests, e2e_tests
- Compare counts side by side
- Report: per-category count for each run, absolute diff

### REQ-CMP-TEMPLATES: Template compliance check
- For each template file in the web module manifest, check if the deployed version matches the template source
- Report per-file: unchanged / modified / deleted
- Compliance percentage = unchanged / total

### REQ-CMP-CONVENTIONS: Convention compliance check
- Check these structural conventions in each run:
  - `route_groups`: public pages under a `(shop)/` or similar route group (not flat at `src/app/`)
  - `action_colocation`: no `src/actions/` directory exists
  - `prisma_naming`: DB client file is `src/lib/prisma.ts` (not `db.ts`, `database.ts`)
  - `component_colocation`: no `src/components/admin/` or `src/components/shop/` directory
  - `utils_naming`: utility file is `src/lib/utils.ts`
- Report per-convention: pass/fail for each run

### REQ-CMP-E2E: E2E test result comparison
- Read Playwright test results from each run: `tests/e2e/*.spec.ts` files, gate results from orchestration state
- Parse test outcomes: which spec files exist, pass/fail/skip per gate
- Compare: same test file names? same pass/fail pattern?
- If Playwright HTML report exists (`playwright-report/`), note its path for manual inspection
- Report: test file overlap, pass rate comparison, gate results match

### REQ-CMP-SCORE: Weighted score calculation
- Weights: routes 0.25, schema 0.20, deps 0.10, categories 0.10, templates 0.10, conventions 0.10, e2e_tests 0.15
- Each metric normalized to 0-100
- Final score = weighted sum
- Verdict thresholds: 90+ identical, 75-89 equivalent, 50-74 partial, <50 divergent

## CLI

### REQ-CMP-CLI: Command-line interface
- `bin/set-compare` — bash wrapper calling `python3 -m set_orch.compare`
- Positional args: two project names (resolved via projects.json)
- `--dir` flag: compare two arbitrary directories
- `--json` flag: output structured JSON instead of markdown
- `--output FILE` flag: write report to file instead of stdout
- Exit code 0 always (comparison tool, not assertion tool)

## Output

### REQ-CMP-MARKDOWN: Human-readable markdown report
- Title with run names and score
- One section per metric with table
- Summary verdict at bottom
- Suitable for pasting into docs or PR descriptions

### REQ-CMP-JSON: Machine-readable JSON output
- Complete structured data for all metrics
- Includes per-metric score, raw data, and final weighted score
- Suitable for CI pipelines or automated tracking

## Integration

### REQ-CMP-DOCS: Documentation
- Add usage instructions to `docs/research/` README or the research reports
- Reference from CLAUDE.md E2E section
