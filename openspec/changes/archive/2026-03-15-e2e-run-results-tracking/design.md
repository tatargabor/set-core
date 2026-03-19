## Context

E2E tests (minishop via `run.sh`, craftbrew via `run-complex.sh`) validate set-core orchestration end-to-end. Currently:

- The user manually runs `run.sh`, then `cd /tmp/project-runN`, then `set-sentinel`
- The sentinel (Claude agent mode via `/wt:sentinel`) monitors but has no knowledge of what changed since the last run
- Results live only in `/tmp` project dirs (state.json, e2e-report.md) — not committed to set-core
- Findings are written manually to `tests/e2e/{project}-e2e-findings.md`
- The E2E-GUIDE.md is static reference — doesn't track run state

Two projects can run in parallel (minishop + craftbrew) with independent results.

The `set-sentinel` bash script is a crash-recovery wrapper (~520 lines) that launches `set-orchestrate start` in a supervised loop. The `/wt:sentinel` skill is a Claude agent that uses this script and adds intelligent monitoring (poll, diagnose, fix, restart). The guide already has sections for monitoring, bug fixing, state reset, and performance baselines.

The `wt-e2e-report` bash script (~665 lines) generates `e2e-report.md` from state.json + logs with metrics, gantt chart, quality gates, comparison to previous report, and optional screenshots/README update.

## Goals / Non-Goals

**Goals:**
- Sentinel knows what changed in set-core since last run and what to watch for
- Run results are committed to set-core repo as MD in the guide — readable by sentinel and humans
- Per-project results (minishop/craftbrew) don't conflict when both run
- Sentinel owns the full E2E lifecycle: prep → launch → monitor → wrap-up
- The prep phase uses a subagent to avoid consuming sentinel context window

**Non-Goals:**
- Custom/consumer project result tracking (future work)
- Automated regression detection heuristics (sentinel uses judgment based on context)
- Changes to the bash `set-sentinel` script (it stays as crash-recovery wrapper)
- Changes to the orchestration engine or state format
- HTML report generation

## Decisions

### 1. Results stored as markdown section in E2E-GUIDE.md, not separate JSON files

**Decision**: Add a `## Last Run Results` section to `E2E-GUIDE.md` with per-project subsections.

**Why**: The sentinel already reads the guide for monitoring instructions. Putting results in the same file means zero extra tooling — the sentinel sees both instructions and context in a single read. Markdown is human-readable, diffable, and naturally mergeable per-project block.

**Alternatives considered**:
- `tests/e2e/results/{project}/latest.json` — requires JSON parsing, extra files, sentinel must read separately
- Separate `tests/e2e/run-results.md` — extra file that sentinel may not read

**Format**: Each project gets a subsection under `## Last Run Results` with a `<!-- -->` comment containing the set-core commit hash for the next run's delta calculation:

```markdown
## Last Run Results

### minishop — Run #14 (2026-03-15)
<!-- set-core-commit: 3df1761c0 -->
- **set-core range**: `abc1234..3df1761` (5 commits)
- **Result**: 6/6 merged | 105 min | 2.7M tokens | 5 retries
- **Open regressions**: Bug #24 (lock file merge)
- **Applied changes**: checkpoint-hardening (8/22 tasks)
- **vs previous**: merged +1, tokens -300K, retries -7
```

### 2. `wt-e2e-report --update-guide` writes the results section

**Decision**: Extend `wt-e2e-report` with a `--update-guide <path>` flag that parses state.json and updates the corresponding project subsection in E2E-GUIDE.md.

**Why**: `wt-e2e-report` already parses state.json, calculates metrics, and has the `--update-readme` pattern as precedent. Adding `--update-guide` follows the same pattern. The report tool runs in the consumer project dir but writes back to the set-core guide path.

**How it works**:
1. Detect project name from current directory (e.g., `minishop-run14` → `minishop`)
2. Detect run number from directory name
3. Parse state.json for metrics (merged/total, duration, tokens, retries)
4. Read previous results block from guide to get `set-core-commit` comment → calculate git delta
5. Check findings.md for open bugs (bugs without "Verified" or with "regressed" status)
6. Check `openspec/changes/` in set-core for active changes
7. Replace (or append) the project's subsection in the guide

### 3. Sentinel startup section in guide defines the full lifecycle

**Decision**: Add a `## Sentinel E2E Lifecycle` section to E2E-GUIDE.md that describes the 4 phases: prep, launch, monitor, wrap-up. This section is read by the `/wt:sentinel` skill (Claude agent mode) at startup.

**Why**: The guide is the sentinel's primary instruction set. Adding lifecycle phases there ensures the sentinel follows the new flow without changing the bash set-sentinel script. The bash script stays as the inner crash-recovery loop; the Claude agent wraps it with intelligence.

**Phases**:
- **Prep**: Spawn subagent → read guide + git log + findings → produce compact summary → inject into sentinel context
- **Launch**: Run `tests/e2e/run.sh` (or `run-complex.sh`) → cd to project dir → run `set-sentinel --spec ...`
- **Monitor**: Existing polling + crash recovery + bug fixing (now with prep context)
- **Wrap-up**: Run `wt-e2e-report --update-guide` → update findings.md → commit results

### 4. Prep phase uses a subagent to protect sentinel context

**Decision**: The sentinel spawns a subagent for the prep phase that returns a compact summary (~20 lines). The sentinel does NOT read the full findings file or git log itself.

**Why**: The sentinel's context window is precious — it runs for hours monitoring. Loading full findings history (hundreds of lines of bug details) would waste context. The subagent reads everything, synthesizes a summary, and returns just what the sentinel needs:
- N commits since last run (list of one-line summaries)
- Open regressions from findings.md (bug numbers + short description)
- Active OpenSpec changes in set-core
- "Watch for" list derived from the above

### 5. Per-project subsections prevent parallel run conflicts

**Decision**: Each project (minishop, craftbrew) gets its own `### {project}` subsection under `## Last Run Results`. The update tool only replaces its own project's block.

**Why**: Two E2E runs can finish at different times. If minishop writes to the minishop block and craftbrew writes to the craftbrew block, there's no git conflict even with overlapping timelines.

**Block boundaries**: Use HTML comments as delimiters:
```markdown
<!-- e2e-results:minishop:start -->
### minishop — Run #14 (2026-03-15)
...
<!-- e2e-results:minishop:end -->
```

## Risks / Trade-offs

**[Risk] Guide file grows large** → Each project block is ~8 lines. Only the latest run is stored (not history). Maximum growth: ~20 lines per project. Acceptable.

**[Risk] Report tool runs in /tmp project dir but needs set-core repo path** → The `--update-guide` flag takes an explicit path. The sentinel knows the set-core repo location (it was launched from there). Pass it as argument.

**[Risk] Parallel runs both try to commit to set-core at the same time** → Unlikely (minutes apart). If it happens, the second commit will see the first's changes (different sections) and auto-merge. Worst case: sentinel retries the commit after pull.

**[Risk] Findings.md has no structured "open bugs" field** → The prep subagent parses findings.md heuristically (bugs without "Verified:" or with "regressed"). This is fragile but acceptable — the prep summary is guidance, not automation. The sentinel can always read the full findings if needed.
