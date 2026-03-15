# CraftBrew E2E Test Findings

Multi-file spec orchestration test using the [CraftBrew spec repo](https://github.com/tatargabor/craftbrew).

## Run Summary

| Run | Date | Status | Merged | Bugs | Notes |
|-----|------|--------|--------|------|-------|
| [#1](run-1.md) | 2026-03-15 | IN PROGRESS | 0/15 | 6 | First CraftBrew run; Figma MCP + directives + heartbeat + verify autocommit |

## Bug Index

| # | Description | Severity | Fixed | Run |
|---|-------------|----------|-------|-----|
| 1 | PyYAML not in linuxbrew Python 3.14 | noise | N/A | #1 |
| 2 | Stall detection during initial dispatch | noise | by design | #1 |
| 3 | Figma MCP blocks claude -p mode | blocking | ee85293 | #1 |
| 4 | Monitor JSONDecodeError on restart (temp directives file) | blocking | 58f63af | #1 |
| 5 | Sentinel kills monitor during stall cooldown (heartbeat too slow) | blocking | b1b5d1a | #1 |
| 6 | Verify gate fails on untracked files without auto-commit | blocking | 06e3cce | #1 |
