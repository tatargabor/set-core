## ADDED Requirements

### Requirement: Last Run Results section in E2E-GUIDE.md
The E2E-GUIDE.md SHALL contain a `## Last Run Results` section with per-project subsections. Each subsection SHALL display the latest run's metrics, set-core commit delta, open regressions, and comparison to the previous run.

#### Scenario: First run for a project with no previous results
- **WHEN** `wt-e2e-report --update-guide <path>` runs for project "minishop" and no minishop subsection exists in the guide
- **THEN** a new `### minishop — Run #N (date)` subsection SHALL be appended inside the `## Last Run Results` section with metrics from state.json and no "vs previous" line

#### Scenario: Subsequent run updates existing project subsection
- **WHEN** `wt-e2e-report --update-guide <path>` runs for project "minishop" and a minishop subsection already exists
- **THEN** the existing minishop subsection SHALL be replaced with updated metrics, and a "vs previous" line SHALL show the delta (merged diff, tokens diff, retries diff)

#### Scenario: Two projects have independent subsections
- **WHEN** both minishop and craftbrew subsections exist under `## Last Run Results`
- **THEN** updating minishop SHALL NOT modify the craftbrew subsection and vice versa

### Requirement: Per-project block delimiters
Each project subsection SHALL be wrapped in HTML comment delimiters: `<!-- e2e-results:{project}:start -->` and `<!-- e2e-results:{project}:end -->`. The report tool SHALL use these delimiters to locate and replace the correct block.

#### Scenario: Block delimiter format
- **WHEN** the report tool writes a minishop results block
- **THEN** the output SHALL be wrapped as:
  ```
  <!-- e2e-results:minishop:start -->
  ### minishop — Run #14 (2026-03-15)
  <!-- set-core-commit: abc1234 -->
  - **set-core range**: ...
  ...
  <!-- e2e-results:minishop:end -->
  ```

#### Scenario: Commit hash preserved for next run delta
- **WHEN** the report tool writes results
- **THEN** a `<!-- set-core-commit: {hash} -->` comment SHALL be included inside the block containing the current HEAD commit of the set-core repo at time of writing

### Requirement: wt-e2e-report --update-guide flag
The `wt-e2e-report` script SHALL accept a `--update-guide <path>` argument that writes the current run's results into the specified E2E-GUIDE.md file.

#### Scenario: Update guide from completed run
- **WHEN** `wt-e2e-report --update-guide /path/to/E2E-GUIDE.md` is called in a project directory containing orchestration-state.json with status "done"
- **THEN** the tool SHALL parse state.json for metrics (status, merged/total, duration, tokens, retries), detect project name and run number from the directory name, and write/replace the corresponding project subsection in the guide

#### Scenario: Guide file does not contain Last Run Results section
- **WHEN** the guide file exists but has no `## Last Run Results` section
- **THEN** the tool SHALL append the section at the end of the file

#### Scenario: Previous set-core commit available for delta
- **WHEN** the guide contains a previous results block with `<!-- set-core-commit: {hash} -->` for the same project
- **THEN** the tool SHALL run `git log {prev_hash}..HEAD --oneline` in the set-core repo to generate the commit delta and include it in the "set-core range" line

### Requirement: Results content includes run metrics and context
Each project results block SHALL include: set-core commit range (with commit count), merged/total changes with duration and tokens, total verify retries, open regressions from findings.md, active OpenSpec changes in set-core, and comparison to previous run.

#### Scenario: Metrics extracted from state.json
- **WHEN** state.json contains 6 changes with 5 merged and 1 failed, total tokens 2.7M, and duration 105 minutes
- **THEN** the results line SHALL read: `5/6 merged | 105 min | 2.7M tokens | N retries`

#### Scenario: Open regressions listed from findings
- **WHEN** the findings file contains bugs without a "Verified" annotation or marked as "regressed"
- **THEN** the results block SHALL include an "Open regressions" line listing those bug numbers and short titles

#### Scenario: No open regressions
- **WHEN** all bugs in findings are verified or the findings file is empty
- **THEN** the "Open regressions" line SHALL read "none"

#### Scenario: Active OpenSpec changes listed
- **WHEN** the set-core repo has active changes in `openspec/changes/` (non-archived)
- **THEN** the results block SHALL include an "Applied changes" line listing change names
