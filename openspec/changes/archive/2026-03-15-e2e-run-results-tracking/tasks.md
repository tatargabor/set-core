## 1. E2E-GUIDE.md — Last Run Results section

- [x] 1.1 Add empty `## Last Run Results` section to E2E-GUIDE.md with per-project delimiter comments (`<!-- e2e-results:{project}:start/end -->`) for minishop and craftbrew
- [x] 1.2 Add `## Sentinel E2E Lifecycle` section to E2E-GUIDE.md describing the 4 phases: prep (subagent context collection), launch (run.sh + set-sentinel), monitor (existing), wrap-up (results + commit)

## 2. wt-e2e-report --update-guide

- [x] 2.1 Add `--update-guide <path>` argument parsing to `bin/wt-e2e-report` (following existing `--update-readme` pattern)
- [x] 2.2 Implement project name and run number detection from current directory name (e.g., `minishop-run14` → project=minishop, run=14)
- [x] 2.3 Implement previous commit hash extraction — parse the guide file for `<!-- set-core-commit: {hash} -->` inside the matching project block
- [x] 2.4 Implement set-core commit delta — run `git -C <set-core-repo> log {prev_hash}..HEAD --oneline` to get commits since last run
- [x] 2.5 Implement open regression detection — parse `tests/e2e/{project}-e2e-findings.md` in set-core repo for bugs without "Verified" status
- [x] 2.6 Implement active OpenSpec changes detection — list non-archived directories in `openspec/changes/` of set-core repo
- [x] 2.7 Implement comparison with previous run — extract metrics from the existing project block (merged, tokens, retries) and compute deltas
- [x] 2.8 Implement results block generation — format all collected data as markdown matching the spec format (commit range, metrics, regressions, applied changes, vs previous)
- [x] 2.9 Implement block replacement — find `<!-- e2e-results:{project}:start -->` / `<!-- e2e-results:{project}:end -->` delimiters and replace content; if no delimiters found, append new block inside `## Last Run Results` section
- [x] 2.10 Add set-core repo path resolution — derive from the script's own location (`$SCRIPT_DIR/..`) since wt-e2e-report lives in `bin/` of set-core

## 3. Guide section — Sentinel E2E Lifecycle content

- [x] 3.1 Write prep phase instructions: spawn subagent to read guide + `git log` + findings.md + `openspec/changes/`, return compact summary under 30 lines with "Watch for" list
- [x] 3.2 Write launch phase instructions: run `tests/e2e/run.sh` (minishop) or `tests/e2e/run-complex.sh` (craftbrew), parse output for project dir, cd, start `set-sentinel --spec <file>`
- [x] 3.3 Write monitor phase instructions: reference existing guide sections, add note about using prep context for regression pattern matching
- [x] 3.4 Write wrap-up phase instructions: run `wt-e2e-report --update-guide`, update findings.md, commit results to set-core repo with `e2e: {project} run #{N} results`
- [x] 3.5 Write parallel runs note: two sentinel sessions for two projects, independent subsections, no conflict

## 4. Testing

- [x] 4.1 Test `--update-guide` with a mock guide file and state.json — verify block is created on first run and replaced on second run
- [x] 4.2 Test project name detection from various directory patterns (`minishop-run14`, `craftbrew-run5`, `/tmp/minishop-run14`)
- [x] 4.3 Test parallel safety — update minishop block then craftbrew block, verify both survive independently
- [x] 4.4 Verify existing `wt-e2e-report` flags (`--project-dir`, `--no-screenshots`, `--update-readme`) still work after changes
