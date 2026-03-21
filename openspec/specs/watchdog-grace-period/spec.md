## ADDED Requirements

### R1: Checkpoint Auto-Approve Directive
- New directive `checkpoint_auto_approve` (default: `false`)
- When `true`, checkpoint events are emitted but orchestration continues immediately without waiting for `set-orchestrate approve`
- Intended for unattended/CI/E2E runs where human approval is not available
- The checkpoint event is still logged so the run can be audited after completion

### R2: E2E Runner Unattended Config
- `tests/e2e/scaffolds/minishop/wt/orchestration/config.yaml` sets `checkpoint_auto_approve: true`
- E2E runs should complete without manual intervention

### R3: Install Script Completeness
- `install.sh` scripts list must include all executables from `bin/` that are intended for user invocation
- Currently missing: `set-sentinel`
