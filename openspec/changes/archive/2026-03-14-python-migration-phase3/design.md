## Design Decisions

### D1: Jinja2 for HTML templating

**Choice**: Use Jinja2 templates instead of Python f-strings for HTML generation.

**Why**: reporter.sh has ~400 lines of inline HTML/CSS. F-strings would just move the same mess to Python. Jinja2 gives proper template inheritance, conditionals, loops, filters, and auto-escaping — purpose-built for HTML generation. The template can be edited by anyone who knows HTML without touching Python.

**Trade-off**: Adds jinja2 as a dependency. Acceptable — it's a well-established stdlib-adjacent package with no transitive deps (MarkupSafe only).

### D2: Dataclass-based report model

**Choice**: Extract all report data into typed dataclasses (`ReportData`, `DigestData`, `PlanData`, `ExecutionData`, `CoverageData`, etc.) before passing to Jinja2.

**Why**: Clean separation of data extraction (Python, testable) from presentation (Jinja2 template). Each section's data is independently testable without rendering HTML. Mirrors the 7-section structure of the current bash: digest, plan, milestone, execution, audit, coverage, footer.

### D3: Single template file with macros

**Choice**: One `report.html.j2` file using Jinja2 macros for reusable components (status badges, coverage bars, token formatting, duration formatting).

**Why**: The current bash has repeated patterns (token formatting in 4 places, status coloring in 6 places, screenshot galleries in 3 places). Jinja2 macros DRY this up. A single file keeps deployment simple — no template directory scanning needed.

### D4: CLI bridge pattern (same as Phase 2)

**Choice**: `set-orch-core report generate` subcommand, bash wrapper calls it.

**Why**: Consistent with Phase 1-2 migration pattern. Bash `generate_report()` becomes a 3-line wrapper. CLI accepts `--state`, `--plan`, `--digest-dir`, `--output` flags matching the bash globals (`STATE_FILENAME`, `PLAN_FILENAME`, `DIGEST_DIR`).

### D5: Template loading from package directory

**Choice**: Load Jinja2 templates from `lib/set_orch/templates/` using `PackageLoader` or `FileSystemLoader` relative to the module.

**Why**: Templates ship with the code. No runtime configuration needed. `Path(__file__).parent / "templates"` gives reliable path resolution.

### D6: Identical HTML output

**Choice**: The Python reporter MUST produce visually identical HTML to the bash version. Same CSS classes, same table structure, same JS toggle script for coverage.

**Why**: The report is consumed by browsers and the TUI web view. Any structural change could break consumers. The migration is a refactor, not a redesign.
