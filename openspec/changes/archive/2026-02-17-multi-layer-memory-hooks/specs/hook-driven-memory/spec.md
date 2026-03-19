## ADDED Requirements

### Requirement: Hooks replace inline memory instructions in skills and commands
All `<!-- set-memory hooks -->` blocks (including `hooks-midflow`, `hooks-remember`, `hooks-reflection`, `hooks-save` variants) SHALL be removed from OpenSpec skill SKILL.md files and opsx command .md files. The 5-layer hook system handles recall (L2 on every prompt) and save (L5 on every stop) automatically — skills SHALL NOT contain manual `set-memory recall` or `set-memory remember` instructions.

### Requirement: CLAUDE.md uses "Persistent Memory" pattern
The CLAUDE.md "Proactive Memory" section SHALL be rewritten to a "Persistent Memory" section that:
1. Explains hooks handle recall and save automatically (agent does not need to manage it)
2. Documents `set-memory remember` as an emphasis tool for HIGH IMPORTANCE items only
3. Documents `set-memory forget` for correcting wrong memories
4. Does NOT contain manual `set-memory recall` instructions
5. Does NOT contain "When to save" / "When NOT to save" rules (L5 handles this)
6. Does NOT contain "Recall before major work" instructions (L2 handles this)
7. Does NOT contain deduplication notes about skill hooks (no skill hooks exist)

### Requirement: Skills retain full functionality without memory hooks
After removing inline memory hooks, all OpenSpec skills (apply, continue, ff, explore, archive, verify, sync, new) SHALL continue to function identically for their primary purpose. Memory operations that were done by inline hooks are now handled by the automatic hook layer.
