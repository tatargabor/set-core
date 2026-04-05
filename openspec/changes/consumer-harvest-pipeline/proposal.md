# Proposal: consumer-harvest-pipeline

## Why

Consumer project E2E runs generate ISS fixes and `.claude/` modifications that contain framework-level insights — but these never flow back to set-core. Over 5 ISS fixes and ~45 `.claude/` modifications across minishop, micro-web, and craftbrew runs have accumulated without review. Each fix is a lesson (e.g., "build gate needs DB init", "smoke_blocking should be disabled without smoke_command") that would prevent the same failure in future runs — but only if adopted into set-core templates, planning rules, or core code. The existing `/set:harvest` skill only diffs `.claude/rules/` files, and the `learnings-to-rules` change only reads review findings. Neither scans ISS fix commits or framework-level code changes.

## What Changes

- **NEW**: `bin/set-harvest` CLI — scans registered consumer projects for unadopted ISS fixes and `.claude/` changes, presents them chronologically per project, tracks adoption state
- **NEW**: `lib/set_orch/harvest.py` — core logic: git log scanning, commit classification (framework-relevant vs project-specific), adoption tracking via marker file
- **MODIFIED**: Existing `/set:harvest` skill (`.claude/skills/set/harvest/SKILL.md`) — extend to call the new CLI, not just diff rules
- **MODIFIED**: `set-project` registry — add `last_harvested_sha` field per project to track what's been reviewed
- **MODIFIED**: README.md — add Consumer Feedback Loop section documenting the harvest workflow as a critical part of the development cycle

## Capabilities

### New Capabilities
- `harvest-cli` — CLI tool that scans consumer projects for unadopted changes, classifies relevance, presents for review
- `harvest-tracker` — Per-project tracking of last harvested commit SHA so runs are not re-reviewed

### Modified Capabilities
- `harvest-skill` — Extend to use the new CLI backend instead of manual diff

## Impact

- `bin/set-harvest` — new CLI entry point
- `lib/set_orch/harvest.py` — commit scanning, classification, adoption tracking
- `.claude/skills/set/harvest/SKILL.md` — rewrite to call CLI
- `lib/set_orch/project_registry.py` or equivalent — `last_harvested_sha` field
- `README.md` — Consumer Feedback Loop section
- `CLAUDE.md` — update Consumer Project Diagnostics section
