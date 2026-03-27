# Proposal: Remove CLI set-sentinel

## Why

The `set-sentinel` bash script (1135 lines) is redundant. The real sentinel logic lives in the Claude skill (`/set:sentinel` via `.claude/commands/set/sentinel.md`), launched through `supervisor.py` from the web UI. The bash script misleads users into thinking they're running a sentinel when they're really just running `set-orchestrate start` with crash recovery — no intelligent decision-making, no Tier 1-3 authority, no bug fixing.

## What Changes

- **Remove** `bin/set-sentinel` (1135-line bash supervisor script)
- **Keep** `bin/set-sentinel-finding` — used by the Claude skill for logging findings
- **Keep** `bin/set-sentinel-inbox` — used by the Claude skill for inbox checks
- **Keep** `bin/set-sentinel-log` — used by the Claude skill for structured event logging
- **Keep** `bin/set-sentinel-status` — used by the Claude skill for status registration
- **Remove** `bin/set-sentinel-rotate` — only used by the CLI script, not the skill
- **Update** all references: docs, E2E runners, install scripts, tests
- **Keep** `/set:sentinel` skill (`.claude/commands/set/sentinel.md`) — unchanged
- **Keep** `supervisor.py` sentinel launch — unchanged
- **Keep** web UI sentinel controls — unchanged

## Capabilities

### Modified Capabilities
- `sentinel` — removing the CLI entry point, keeping the skill/supervisor path

## Impact

- **bin/**: 6 scripts removed
- **docs/**: References updated from `set-sentinel` CLI to `/set:sentinel` skill or `set-orchestrate start`
- **tests/e2e/runners/**: Instructions updated
- **No API changes** — web UI, supervisor.py, sentinel skill all unchanged
- **BREAKING**: Users who run `set-sentinel` from CLI will get "command not found"
