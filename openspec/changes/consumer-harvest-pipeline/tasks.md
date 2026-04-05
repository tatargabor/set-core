# Tasks: consumer-harvest-pipeline

## 1. Core harvest logic — lib/set_orch/harvest.py

- [x] 1.1 Create `lib/set_orch/harvest.py` with `scan_project()` — takes project path + last_harvested_sha, returns list of `HarvestCandidate` dataclasses (commit_sha, date, message, files_changed, classification, suggested_target) [REQ: scan-registered-projects-for-unadopted-changes]
- [x] 1.2 Implement commit classification — parse `git log` output, match ISS fix patterns (`fix-iss-*`, `fix:`), `.claude/` modifications, filter out feature/chore commits [REQ: classify-commit-relevance]
- [x] 1.3 Implement framework-relevance heuristic — classify by files_changed (package.json scripts → framework, src/app/ only → project-specific, .claude/rules/set-*.md → template-divergence) [REQ: classify-commit-relevance]
- [x] 1.4 Implement adoption target mapping — map consumer file paths to set-core target locations (planning_rules.txt, templates/, modules/web/, .claude/rules/) [REQ: classify-commit-relevance]
- [x] 1.5 Add `scan_all_projects()` — iterate registered projects from `set-project list`, collect candidates, sort chronologically across all projects [REQ: scan-registered-projects-for-unadopted-changes]

## 2. Harvest tracker — project registry integration

- [x] 2.1 Add `last_harvested_sha` field to project registry — read/write via `set-project` config or dedicated harvest state file at `~/.local/share/set-core/harvest-state.json` [REQ: track-harvest-state-per-project]
- [x] 2.2 Implement `get_harvest_state(project_name)` and `set_harvest_state(project_name, sha)` — read/write SHA per project [REQ: track-harvest-state-per-project]
- [x] 2.3 Handle first harvest (no SHA) — scan from initial commit, and re-registration (SHA reset if git history changed) [REQ: track-harvest-state-per-project]

## 3. CLI — bin/set-harvest

- [x] 3.1 Create `bin/set-harvest` bash wrapper + `harvest.py` `main()` entry point with argparse — `set-harvest` (all projects), `set-harvest --project <name>` (single) [REQ: scan-registered-projects-for-unadopted-changes]
- [x] 3.2 Implement interactive presentation loop — for each candidate: show project, date, commit message, files, classification, suggested target; prompt adopt/skip/view-diff [REQ: interactive-adoption-workflow]
- [x] 3.3 Implement "adopt" action — show diff, ask target file confirmation, apply the change (append to planning_rules.txt, copy to template, etc.), update harvest SHA [REQ: interactive-adoption-workflow]
- [x] 3.4 Implement "skip" action — mark as reviewed, advance SHA [REQ: interactive-adoption-workflow]
- [x] 3.5 Implement "view diff" action — run `git show <sha>` in project dir, display, return to adopt/skip prompt [REQ: interactive-adoption-workflow]
- [x] 3.6 Add `--dry-run` flag — show what would be presented without modifying harvest state [REQ: scan-registered-projects-for-unadopted-changes]

## 4. Skill update — .claude/skills/set/harvest/SKILL.md

- [x] 4.1 Rewrite `/set:harvest` skill to use the new CLI backend — call `set-harvest` and present results interactively within Claude session [REQ: interactive-adoption-workflow]

## 5. Documentation

- [x] 5.1 Add "Consumer Feedback Loop" section to README.md — document the harvest workflow as a critical part of the development cycle, explain the bidirectional flow (set-core → consumer via init, consumer → set-core via harvest) [REQ: scan-registered-projects-for-unadopted-changes]
- [x] 5.2 Update CLAUDE.md "Consumer Project Diagnostics" section — reference `set-harvest` as the primary tool for adopting consumer fixes [REQ: scan-registered-projects-for-unadopted-changes]

## 6. Tests

- [x] 6.1 Unit test `scan_project()` — test ISS fix detection, .claude/ modification detection, commit classification, chronological ordering [REQ: scan-registered-projects-for-unadopted-changes]
- [x] 6.2 Unit test classification heuristics — test framework-relevant vs project-specific vs template-divergence classification [REQ: classify-commit-relevance]
- [x] 6.3 Unit test harvest state tracking — first harvest, incremental harvest, re-registration [REQ: track-harvest-state-per-project]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `set-harvest` is run THEN ISS fix commits after last_harvested_sha are listed chronologically [REQ: scan-registered-projects-for-unadopted-changes, scenario: scan-finds-iss-fix-commits]
- [x] AC-2: WHEN .claude/ files are modified in consumer THEN they are listed as template divergences [REQ: scan-registered-projects-for-unadopted-changes, scenario: scan-finds-claude-modifications]
- [x] AC-3: WHEN all projects are up to date THEN "No unadopted changes found" is shown [REQ: scan-registered-projects-for-unadopted-changes, scenario: no-unadopted-changes]
- [x] AC-4: WHEN ISS fix modifies package.json build scripts THEN classified as framework-relevant [REQ: classify-commit-relevance, scenario: iss-fix-classified-as-framework-relevant]
- [x] AC-5: WHEN ISS fix only modifies src/app/ business code THEN classified as project-specific [REQ: classify-commit-relevance, scenario: iss-fix-classified-as-project-specific]
- [x] AC-6: WHEN user selects "adopt" THEN the change is applied to suggested set-core file [REQ: interactive-adoption-workflow, scenario: user-adopts-a-framework-relevant-fix]
- [x] AC-7: WHEN user selects "skip" THEN commit is marked reviewed, not shown again [REQ: interactive-adoption-workflow, scenario: user-skips-a-commit]
- [x] AC-8: WHEN first harvest on project THEN all commits since init are scanned [REQ: track-harvest-state-per-project, scenario: first-harvest-on-a-project]
- [x] AC-9: WHEN incremental harvest THEN only new commits since last SHA are shown [REQ: track-harvest-state-per-project, scenario: incremental-harvest]
