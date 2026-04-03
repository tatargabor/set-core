# Design: Divergence Comparison Tool

## Architecture

```
bin/set-compare (CLI entry point)
    │
    ▼
lib/set_orch/compare.py (core logic)
    ├── collect_routes(project_dir) → set of URL strings
    ├── collect_schema(project_dir) → dict of models/enums/relations
    ├── collect_deps(project_dir) → set of package names
    ├── collect_categories(project_dir) → dict of category→count
    ├── check_template_compliance(project_dir, template_dir) → list of results
    ├── check_convention_compliance(project_dir) → list of results
    └── compare_runs(dir_a, dir_b) → ComparisonResult
```

## Metric Collection

### Routes
```python
def collect_routes(project_dir: Path) -> set[str]:
    """Find all page.tsx and route.ts, convert to URL paths."""
    # src/app/(shop)/products/[id]/page.tsx → /products/[id]
    # src/app/api/cart/route.ts → /api/cart
    # Strip route groups: (shop)/, (auth)/, (dashboard)/
```

### Schema
```python
def collect_schema(project_dir: Path) -> dict:
    """Parse prisma/schema.prisma for model/enum names and relations."""
    # Regex-based: model X { ... }, enum Y { ... }
    # Extract field names and @relation references
    # Ignore whitespace, ordering
    # Returns: {"models": {"Product": ["id","name",...], ...}, "enums": ["OrderStatus",...]}
```

### Dependencies
```python
def collect_deps(project_dir: Path) -> tuple[set, set]:
    """Read package.json deps and devDeps."""
    # Returns (deps_set, devdeps_set)
```

### Functional Categories
```python
def collect_categories(project_dir: Path) -> dict[str, int]:
    """Count files by functional role."""
    # pages: **/page.tsx count
    # api_routes: **/route.ts count
    # actions: **/actions.ts count
    # components: *.tsx not page/layout/ui/* count
    # ui_primitives: components/ui/*.tsx count
    # lib: lib/**/*.ts count
    # layouts: **/layout.tsx count
    # middleware: middleware.ts exists? 1/0
    # unit_tests: **/*.test.* count
    # e2e_tests: tests/e2e/*.spec.ts count
```

### Template Compliance
```python
def check_template_compliance(project_dir: Path, template_dir: Path) -> list[dict]:
    """Diff each template file against the deployed version."""
    # For each file in template manifest:
    #   compare template source vs project version
    #   status: "unchanged" | "modified" | "deleted" | "not_deployed"
```

### Convention Compliance
```python
def check_convention_compliance(project_dir: Path) -> list[dict]:
    """Check structural conventions."""
    checks = [
        ("route_groups", "Public pages under (shop)/ route group", ...),
        ("action_colocation", "No top-level src/actions/ directory", ...),
        ("prisma_naming", "DB client at src/lib/prisma.ts", ...),
        ("component_colocation", "No src/components/admin/ directory", ...),
        ("utils_naming", "Utility file at src/lib/utils.ts", ...),
    ]
```

## Comparison Logic

```python
def compare_runs(dir_a: Path, dir_b: Path) -> ComparisonResult:
    """Compare two project directories across all metrics."""
    # 1. Collect metrics from both
    # 2. Compute overlap/diff for each
    # 3. Calculate weighted score
    # 4. Generate summary text
```

### Scoring

```python
weights = {
    "route_coverage": 0.25,      # Most important — same URLs = same app
    "schema_equivalence": 0.20,  # Same data model = same domain
    "dependency_set": 0.15,      # Same packages = same tech stack
    "functional_categories": 0.15, # Same architecture shape
    "template_compliance": 0.15, # Templates survived = conventions held
    "convention_compliance": 0.10, # Structural patterns followed
}

# Each metric normalized to 0-100
# Weighted sum = final score (0-100)
```

### Verdict Thresholds
```
90-100: "Structurally identical" — only content/styling differs
75-89:  "Structurally equivalent" — minor architectural differences
50-74:  "Partially divergent" — some structural decisions differ
0-49:   "Significantly divergent" — different architectural approaches
```

## Output Formats

### Markdown (default)
```markdown
# Divergence Report: minishop-run12 vs minishop-run13

**Score: 86/100** — Structurally equivalent

## Route Coverage (85%)
| Metric | Value |
|--------|-------|
| Common routes | 17 |
| Only run12 | 0 |
| Only run13 | 3 (/api/cart/count, /api/orders/[id], /api/products) |

## Schema Equivalence (93%)
...
```

### JSON (`--json` flag)
Full structured output, machine parseable, suitable for CI comparison.

## CLI Entry Point

```bash
#!/usr/bin/env bash
# bin/set-compare
exec python3 -m set_orch.compare "$@"
```

Uses `argparse` for CLI parsing. Resolves project names to paths via `projects.json` or `--dir` flags.
