## ADDED Requirements

### Requirement: Gitignore covers orchestration runtime journal files

The nextjs template `.gitignore` SHALL include patterns for the runtime journal files that the set-core dispatcher and merger write at the consumer project root, so that `git status` is clean across orchestration cycles.

#### Scenario: Per-change journal directory is gitignored

- **WHEN** the dispatcher writes `journals/<change>.jsonl` at the project root
- **THEN** `git status` does NOT list `journals/` as untracked or modified

#### Scenario: Rotated orchestration event logs are gitignored

- **WHEN** the event bus rotates to a new cycle file (`orchestration-events-cycle<N>.jsonl` / `orchestration-events-<N>.jsonl` at the project root)
- **THEN** `git status` does NOT list the rotated file as untracked or modified

#### Scenario: Activity-detail cache files are gitignored

- **WHEN** the activity-detail API writes `set/orchestration/activity-detail-*.jsonl` (including `activity-detail-v2-<change>.jsonl` cache siblings) at the project root
- **THEN** `git status` does NOT list those files as untracked or modified

#### Scenario: Coverage and e2e manifest history are gitignored

- **WHEN** the dispatcher appends to `set/orchestration/spec-coverage-history.jsonl` or `set/orchestration/e2e-manifest-history.jsonl`
- **THEN** `git status` does NOT list those files as untracked or modified

#### Scenario: Other files under set/orchestration/ remain tracked

- **WHEN** the consumer authors a hand-written file under `set/orchestration/` (e.g. config notes)
- **THEN** that file is NOT automatically gitignored
- **AND** only the specific journal / cache / history patterns above are matched by `.gitignore`

#### Scenario: Additions ship via set-project init

- **WHEN** a user runs `set-project init --project-type web --template nextjs` after the template update
- **THEN** the deployed `.gitignore` contains the four new runtime-journal patterns alongside the existing entries
