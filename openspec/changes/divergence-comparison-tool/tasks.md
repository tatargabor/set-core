# Tasks: Divergence Comparison Tool

## 1. Core comparison library

- [ ] Create `lib/set_orch/compare.py` with data collection functions
- [ ] `collect_routes(project_dir)` — find page.tsx/route.ts, strip route groups, return URL set
- [ ] `collect_schema(project_dir)` — regex-parse prisma/schema.prisma for model/enum names, return dict
- [ ] `collect_deps(project_dir)` — read package.json, return (deps_set, devdeps_set)
- [ ] `collect_categories(project_dir)` — count files by role (pages, api_routes, actions, components, ui, lib, layouts, middleware, unit_tests, e2e_tests)
- [ ] `check_template_compliance(project_dir)` — diff template files vs deployed, return per-file status
- [ ] `check_convention_compliance(project_dir)` — check route_groups, action_colocation, prisma_naming, component_colocation, utils_naming
- [ ] `collect_e2e_results(project_dir)` — find tests/e2e/*.spec.ts names, read gate results from orchestration state (test_result, build_result, smoke_result per change), check for playwright-report/ dir
- [ ] `compare_runs(dir_a, dir_b)` — collect all metrics, compute overlaps, calculate weighted score, generate verdict

## 2. Output formatting

- [ ] `format_markdown(result)` — render ComparisonResult as readable markdown report with tables
- [ ] `format_json(result)` — render as structured JSON
- [ ] Score calculation: per-metric 0-100 normalization, weighted sum, verdict thresholds

## 3. CLI entry point

- [ ] Create `bin/set-compare` bash wrapper
- [ ] `lib/set_orch/compare.py` `__main__` block with argparse: positional project names, --dir, --json, --output
- [ ] Project name resolution via projects.json (same as API helpers)
- [ ] Make executable, test with `set-compare minishop-run12 minishop-run13`

## 4. Validation

- [ ] Test: `set-compare minishop-run12 minishop-run13` produces valid markdown report
- [ ] Test: `set-compare minishop-run12 minishop-run13 --json` produces valid JSON
- [ ] Test: `set-compare micro-web-run10 micro-web-run11` shows 90+ score
- [ ] Test: route groups properly stripped (app/(shop)/products → /products)
- [ ] Test: prisma schema comparison handles missing schema.prisma gracefully

## 5. Documentation

- [ ] Add `set-compare` to CLAUDE.md E2E section
- [ ] Add `set-compare` to docs/cli-reference.md
