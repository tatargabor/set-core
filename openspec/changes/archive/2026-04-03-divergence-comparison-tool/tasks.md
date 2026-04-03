# Tasks: Divergence Comparison Tool

## 1. Core comparison library

- [x] Create `lib/set_orch/compare.py` with data collection functions
- [x] `collect_routes(project_dir)` — find page.tsx/route.ts, strip route groups, return URL set
- [x] `collect_schema(project_dir)` — regex-parse prisma/schema.prisma for model/enum names, return dict
- [x] `collect_deps(project_dir)` — read package.json, return (deps_set, devdeps_set)
- [x] `collect_categories(project_dir)` — count files by role (pages, api_routes, actions, components, ui, lib, layouts, middleware, unit_tests, e2e_tests)
- [x] `check_template_compliance(project_dir)` — diff template files vs deployed, return per-file status
- [x] `check_convention_compliance(project_dir)` — check route_groups, action_colocation, prisma_naming, component_colocation, utils_naming
- [x] `collect_e2e_results(project_dir)` — find tests/e2e/*.spec.ts names, read gate results from orchestration state
- [x] `compare_runs(dir_a, dir_b)` — collect all metrics, compute overlaps, calculate weighted score, generate verdict

## 2. Output formatting

- [x] `format_markdown(result)` — render ComparisonResult as readable markdown report with tables
- [x] `format_json(result)` — render as structured JSON
- [x] Score calculation: per-metric 0-100 normalization, weighted sum, verdict thresholds

## 3. CLI entry point

- [x] Create `bin/set-compare` bash wrapper
- [x] `lib/set_orch/compare.py` `__main__` block with argparse: positional project names, --dir, --json, --output
- [x] Project name resolution via projects.json (same as API helpers)
- [x] Make executable, test with `set-compare minishop-run12 minishop-run13`

## 4. Validation

- [x] Test: `set-compare minishop-run12 minishop-run13` produces valid markdown report (72/100)
- [x] Test: micro-web-run10 vs run11 shows 87/100 (structurally equivalent)
- [x] Test: route groups properly stripped (app/(shop)/products → /products)
- [x] Test: prisma schema comparison handles missing schema.prisma gracefully (N/A, 100%)
- [x] Test: template compliance handles not_applicable files (utils.ts deleted in non-shadcn project)

## 5. Documentation

- [x] Add `set-compare` to CLAUDE.md E2E section
- [x] Add `set-compare` to docs/reference/cli.md
