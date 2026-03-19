# CraftBrew E2E Test Findings

Multi-file spec orchestration test using the [CraftBrew spec repo](https://github.com/tatargabor/craftbrew).

## Run Summary

| Run | Date | Status | Merged | Bugs | Tokens | Notes |
|-----|------|--------|--------|------|--------|-------|
| [#1](run-1.md) | 2026-03-15/16 | COMPLETE | 15/15 | 8 | 11.0M | First CraftBrew run; 298 tests; 9h wall clock; 7 interventions |
| [#2](run-2.md) | 2026-03-17 | INTERRUPTED | 2/15 | 4 | ~1.7M | State file lost in merge cleanup; context overflow; Bug #37 fix not yet active |
| [#3](run-3.md) | 2026-03-18 | COMPLETE | 15/15 | 8 | ~888K | Verify agent death (Bug #14) affected 12/15 changes; 12 manual merges; ~5.5h wall clock |

## Bug Index

| # | Description | Severity | Fixed | Run |
|---|-------------|----------|-------|-----|
| 1 | PyYAML not in linuxbrew Python 3.14 | noise | N/A | #1 |
| 2 | Stall detection during initial dispatch | noise | by design | #1 |
| 3 | Figma MCP blocks claude -p mode | blocking | ee85293 | #1 |
| 4 | Monitor JSONDecodeError on restart (temp directives file) | blocking | 58f63af | #1 |
| 5 | Sentinel kills monitor during stall cooldown (heartbeat too slow) | blocking | b1b5d1a | #1 |
| 6 | Verify gate fails on untracked files without auto-commit | blocking | 06e3cce | #1 |
| 7 | UnicodeDecodeError on binary subprocess output (PNG in stdout) | blocking | cf07532 | #1 |
| 8 | Verify gate stuck in "verifying" (spec_verify crash orphans status) | blocking | manual | #1 |
| 9 | orchestration-state.json deleted during set-merge cleanup | blocking | fixed (`eec894bcb`) | #2 |
| 10 | Context overflow: database-schema 970K (485% of 200K window) | app-bug | open | #2 |
| 11 | Bug #37 fix cached — orchestrator must be restarted fresh | noise | fixed `606aec640` (next run) | #2 |
| 12 | Phantom review — scaffold files flagged in verify (Bug #53 regression) | blocking | open | #3 |
| 13 | `local` outside function in set-sentinel line 536 | noise | `8fb62c890` | #3 |
| 14 | **Verify agent dies, change stuck in "verifying" forever** | **critical** | open — #1 priority | #3 |
| 15 | `cc/` model prefix stale — agent can't start | blocking | config fix | #3 |
| 16 | Monitor stuck 7+ min, sentinel kills orchestrator | blocking | open | #3 |
| 17 | State extras flattening — manual edits ignored | noise | documented | #3 |
| 18 | Monitor overwrites manual state edits (stale in-memory state) | blocking | workaround: kill monitor first | #3 |
| 19 | Sentinel stops on removed worktree sync failure | blocking | open | #3 |
