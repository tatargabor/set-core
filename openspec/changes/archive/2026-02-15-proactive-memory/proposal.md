## Why

Memory hooks currently only save at workflow endpoints (apply completion, archive). When a user shares valuable knowledge mid-conversation — "we tried Redis caching, it was too slow", "always use --force with openspec update", "this API returns 500 on empty arrays" — it's lost unless the user explicitly calls `/wt:memory remember`. Most real-world knowledge transfer happens conversationally, not at ceremony points. The system should capture these insights as they arise, regardless of language.

## What Changes

- Add recall + remember hooks to `/opsx:explore` SKILL.md — the most natural place for sharing learnings and past experience
- Extend `/opsx:apply`, `/opsx:continue`, `/opsx:ff` hooks to save mid-flow, not just at completion — when the user provides corrections, warnings, or context
- Add a "Proactive Memory" section to CLAUDE.md instructing the agent to recognize and save valuable knowledge during any conversation (not just inside skills)
- Update `set-memory-hooks` install script to patch the new hook content into all affected SKILL.md files

## Capabilities

### New Capabilities
- `explore-memory`: Recall + remember hooks in the `/opsx:explore` skill — recall at start, remember when user shares insights during exploration
- `midflow-memory`: Extended hooks in apply/continue/ff skills that save user-provided learnings mid-workflow (not only at step 7)
- `ambient-memory`: CLAUDE.md instruction block for proactive memory capture in any conversation context

### Modified Capabilities

## Impact

- Modified: `.claude/skills/openspec-explore/SKILL.md` — add recall + remember steps
- Modified: `.claude/skills/openspec-apply-change/SKILL.md` — add mid-flow remember
- Modified: `.claude/skills/openspec-continue-change/SKILL.md` — add mid-flow remember
- Modified: `.claude/skills/openspec-ff-change/SKILL.md` — add mid-flow remember
- Modified: `bin/set-memory-hooks` — new hook templates for explore, updated templates for apply/continue/ff
- Modified: `CLAUDE.md` — new "Proactive Memory" section
- Modified: tests for new hook patterns
