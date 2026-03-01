## Context

The memory system has transitioned from `wt-memory-hooks install` (inline SKILL.md patching) to `wt-deploy-hooks` (settings.json 5-layer hooks). SYN-06 benchmark confirms this works: +34% quality, -20% tokens. All core documentation (README, CLAUDE.md, docs/developer-memory.md, install.sh) has already been updated. However:

1. No migration guide exists for users upgrading from the old system
2. No CHANGELOG tracks breaking changes
3. Deprecated specs lack a sunset timeline
4. install.sh doesn't warn about legacy inline hooks
5. README date is stale (2026-02-17)
6. CLI `--help` text hasn't been audited for consistency

## Goals / Non-Goals

**Goals:**
- Create MIGRATION.md that walks users from legacy to hook-driven memory in <5 minutes
- Audit and update all user-facing docs for consistency
- Add legacy hook detection + warning to install.sh
- Set sunset timeline on deprecated specs
- Update README date and verify sections

**Non-Goals:**
- Removing `wt-memory-hooks` binary (keep `check`/`remove` for cleanup)
- Changing any runtime behavior of hooks or memory system
- Adding new features — this is purely docs/consistency work
- Versioning/tagging the release itself (separate task)

## Decisions

### D1: MIGRATION.md as standalone file (not section in developer-memory.md)
**Why**: Migration is a one-time activity. Embedding it in the main guide adds permanent clutter for a temporary need. A standalone file can be referenced from README and eventually archived.
**Alternative**: Section in developer-memory.md — rejected because it mixes reference docs with transition docs.

### D2: install.sh detects legacy hooks and warns (not auto-removes)
**Why**: Auto-removal is destructive. Users might have custom modifications in their SKILL.md files. A warning with `wt-memory-hooks remove` command is safer.
**Alternative**: Auto-remove during install — rejected, too aggressive.

### D3: Sunset timeline = next release after this one
**Why**: Users need at least one release cycle to migrate. The `check`/`remove` subcommands stay; only `install` is deprecated.

## Risks / Trade-offs

- **[Risk] Users ignore migration guide** → Mitigation: install.sh warning is hard to miss, runs on every install
- **[Risk] SKILL.md files have custom user modifications** → Mitigation: warn-only, never auto-remove
- **[Risk] Docs go stale again** → Mitigation: README date check can be part of release checklist (add to run-guide.md)

## Migration Plan

1. User runs `bash install.sh` → sees warning if legacy hooks detected
2. Warning points to `MIGRATION.md` and `wt-memory-hooks remove`
3. User runs `wt-memory-hooks remove` to clean inline hooks
4. User runs `wt-deploy-hooks .` (or it's already deployed) to ensure new hooks are active
5. Verify with `wt-memory health` and `wt-deploy-hooks --check .`
