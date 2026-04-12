# Tasks: set-recovery skill

## 1. Core recovery module

- [x] 1.1 Create `lib/set_orch/recovery.py` with `RecoveryError` exception, `RecoveryPlan` dataclass, and `recover_to_change()` entry point.
- [x] 1.2 Implement `_validate_project(project_path, target_change)` — checks no running orchestrator/sentinel, target change exists and is merged, state.json loadable.
- [x] 1.3 Implement `_find_target_commit(project_path, target_change) -> str` — searches git log for the archive commit, falls back to merge commit, last resort `--grep` search.
- [x] 1.4 Implement `_build_recovery_plan(state, target_change, target_commit, project_path) -> RecoveryPlan` — collects all changes after target, branches, worktrees, archive dirs.
- [x] 1.5 Implement `_render_preview(plan) -> str` — markdown preview of the recovery plan.
- [x] 1.6 Implement `_execute_plan(project_path, plan, state)` — atomic execution with backup + try/except rollback.
- [x] 1.7 Add INFO/WARNING logging for every destructive step.

## 2. CLI tool

- [x] 2.1 Create `bin/set-recovery` bash wrapper that resolves project path from name (via projects.json), then exec's `python3 -m set_orch.recovery_cli`.
- [x] 2.2 Create `lib/set_orch/recovery_cli.py` with argparse — `<project> <target>`, flags: `--dry-run`, `--yes`, `--json`, `--keep-archive`.
- [x] 2.3 CLI calls `recover_to_change()`, handles `RecoveryError` with non-zero exit, prints preview, asks for confirmation unless `--yes`.

## 3. Skill + slash command

- [x] 3.1 Create `.claude/skills/set-recovery/SKILL.md` documenting the recovery flow, when to use it, what it does, what it doesn't touch, and how to undo.
- [x] 3.2 Create `.claude/commands/set/recovery.md` slash command — `/set:recovery <change-name>` invokes the skill in the active project.
- [x] 3.3 Skill prompt: lists active project + asks for confirmation, then calls `set-recovery <project> <change>`.

## 4. Edge case tests (manual)

- [x] 4.1 Test: target is the only merged change → should refuse
- [x] 4.2 Test: target has non-merged changes after (status=running) → kill agent + continue
- [x] 4.3 Test: archived dir naming mismatch → fallback search by suffix
- [x] 4.4 Test: --dry-run shows preview without executing
- [x] 4.5 Test: failure mid-execution → state.json restored from backup, git tag preserved

## 5. Use it on minishop-run1

- [x] 5.1 Run `set-recovery minishop-run1 shopping-cart --dry-run` and verify the plan
- [x] 5.2 Run `set-recovery minishop-run1 shopping-cart` to actually rollback
- [x] 5.3 Restart sentinel and let admin-products + checkout-orders re-run with the resume preamble fix
