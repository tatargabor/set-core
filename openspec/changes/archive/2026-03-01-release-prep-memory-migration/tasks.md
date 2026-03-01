## 1. Migration Guide

- [ ] 1.1 Create `MIGRATION.md` at repo root with numbered migration steps (detect → remove → deploy → verify)
- [ ] 1.2 Add before/after comparison section (old inline SKILL.md patching vs new settings.json hooks)
- [ ] 1.3 Add troubleshooting section (hooks not firing, stale inline hooks, memory not recalled)
- [ ] 1.4 Add link to MIGRATION.md from README.md (in Developer Memory section)

## 2. install.sh Legacy Detection

- [ ] 2.1 Add legacy hook detection after install completes: run `wt-memory-hooks check` and warn if inline hooks found
- [ ] 2.2 Warning message includes `wt-memory-hooks remove` command and MIGRATION.md reference

## 3. Documentation Updates

- [ ] 3.1 Update README.md "Latest update" date to 2026-02-19
- [ ] 3.2 Add "Migration from Legacy Hooks" section to `docs/developer-memory.md` linking to MIGRATION.md
- [ ] 3.3 Add architecture summary with SYN-06 benchmark data (+34% quality, -20% tokens) to `docs/developer-memory.md`

## 4. Deprecated Specs Sunset

- [ ] 4.1 Add sunset notice to `openspec/specs/memory-hooks-cli/spec.md`: `install` removed next release, `check`/`remove` retained
- [ ] 4.2 Add sunset notice to `openspec/specs/memory-hooks-gui/spec.md`: same timeline as CLI

## 5. CLI Consistency Audit

- [ ] 5.1 Verify `wt-memory --help` output is current and consistent
- [ ] 5.2 Verify `wt-deploy-hooks --help` output is current and consistent
- [ ] 5.3 Verify `wt-project --help` output is current and consistent
- [ ] 5.4 Fix any inconsistencies found in --help text

## 6. Skill Audit

- [ ] 6.1 Grep all `.claude/skills/*/SKILL.md` for stale `wt-memory recall` or `wt-memory remember` instructions
- [ ] 6.2 Remove any found stale manual memory instructions (hooks handle this now)
