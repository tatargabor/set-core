## ADDED Requirements

### Requirement: Sentinel E2E Lifecycle section in guide
The E2E-GUIDE.md SHALL contain a `## Sentinel E2E Lifecycle` section describing the four phases: prep, launch, monitor, wrap-up. This section SHALL be read by the sentinel (Claude agent mode) at startup to determine its workflow.

#### Scenario: Guide contains lifecycle instructions
- **WHEN** the sentinel reads E2E-GUIDE.md
- **THEN** the `## Sentinel E2E Lifecycle` section SHALL describe the prep, launch, monitor, and wrap-up phases with specific instructions for each

### Requirement: Prep phase collects context via subagent
During the prep phase, the sentinel SHALL spawn a subagent to collect run context without consuming the sentinel's own context window. The subagent SHALL return a compact summary (target: under 30 lines).

#### Scenario: Subagent collects delta from previous run
- **WHEN** the sentinel starts and the guide contains a previous results block with a set-core commit hash
- **THEN** the prep subagent SHALL run `git log {prev_commit}..HEAD --oneline` in the set-core repo and include the commit list in the summary

#### Scenario: Subagent identifies open regressions
- **WHEN** the findings file for the target project contains bugs without "Verified" status
- **THEN** the prep subagent SHALL list those bugs in a "Watch for" section of the summary

#### Scenario: Subagent reports active set-core changes
- **WHEN** `openspec/changes/` contains non-archived change directories
- **THEN** the prep subagent SHALL list the change names and their task completion status

#### Scenario: No previous run exists
- **WHEN** the guide has no previous results for the target project
- **THEN** the prep subagent SHALL report "First run — no baseline" and skip delta/regression sections

### Requirement: Launch phase runs the E2E test scaffold and starts orchestration
The sentinel SHALL execute the test scaffold script (`tests/e2e/run.sh` or `tests/e2e/run-complex.sh`), change to the created project directory, and start `set-sentinel --spec <spec-file>`.

#### Scenario: Sentinel launches minishop E2E
- **WHEN** the user requests a minishop E2E run
- **THEN** the sentinel SHALL run `tests/e2e/run.sh`, parse its output for the project directory path, cd to that directory, and start `set-sentinel --spec docs/v1-minishop.md`

#### Scenario: Sentinel launches craftbrew E2E
- **WHEN** the user requests a craftbrew E2E run
- **THEN** the sentinel SHALL run `tests/e2e/run-complex.sh`, parse its output for the project directory path, cd to that directory, and start `set-sentinel --spec` with the appropriate spec file

#### Scenario: Sentinel reports project directory to user
- **WHEN** the scaffold script completes and the sentinel cds to the project directory
- **THEN** the sentinel SHALL report the project directory path to the user before starting monitoring

### Requirement: Monitor phase uses prep context
During monitoring, the sentinel SHALL use the prep summary to inform its decisions. The prep summary provides "Watch for" items that the sentinel SHALL check against observed failures and patterns.

#### Scenario: Known regression pattern observed
- **WHEN** a failure matches a pattern listed in the prep summary's "Watch for" section
- **THEN** the sentinel SHALL reference the known bug number and determine if the fix was applied or if this is a recurrence

#### Scenario: Monitor phase follows existing guide sections
- **WHEN** the sentinel enters monitor phase
- **THEN** it SHALL follow the existing E2E-GUIDE.md sections (Monitoring, Framework Bug vs App Bug, When You Fix a set-core Bug, State Reset) as before

### Requirement: Wrap-up phase records results and commits
After orchestration completes (status "done", "stopped", or "time_limit"), the sentinel SHALL run the report tool with `--update-guide`, update findings if needed, and commit the changes to the set-core repo.

#### Scenario: Successful run wrap-up
- **WHEN** orchestration finishes with status "done"
- **THEN** the sentinel SHALL:
  1. Run `wt-e2e-report --update-guide <set-core-guide-path>` in the project directory
  2. Update findings.md with any new bugs discovered during monitoring
  3. Commit the guide and findings changes with message `e2e: {project} run #{N} results`

#### Scenario: Failed or interrupted run wrap-up
- **WHEN** orchestration finishes with status "stopped" or "time_limit"
- **THEN** the sentinel SHALL still run the wrap-up phase to record partial results, noting the incomplete status in the results block

#### Scenario: Wrap-up commits to set-core repo
- **WHEN** the sentinel runs wrap-up
- **THEN** changes SHALL be committed to the set-core repo (where E2E-GUIDE.md and findings files live), NOT to the consumer project repo in /tmp
