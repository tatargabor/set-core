## Tasks

### Group 1: Explore memory hooks

- [x] 1.1 Add recall block to `openspec-explore/SKILL.md`: after "Check for context" step, add recall step gated on `set-memory health`
- [x] 1.2 Add mid-exploration remember instruction to `openspec-explore/SKILL.md`: describe the recognition pattern (negative experience, decision, technical learning) with language-independent wording
- [x] 1.3 Add explore hook templates to `bin/set-memory-hooks` so `install` patches explore skill too
- [x] 1.4 Update `HOOK_SKILLS` array in `set-memory-hooks` if explore is not already included

### Group 2: Mid-flow memory hooks

- [x] 2.1 Add mid-flow remember instruction to `openspec-apply-change/SKILL.md`: between step 4b and step 5, add instruction for recognizing user-shared knowledge during task implementation
- [x] 2.2 Add mid-flow remember instruction to `openspec-continue-change/SKILL.md`: after step 2b, add instruction for recognizing user-shared knowledge during artifact creation
- [x] 2.3 Add mid-flow remember instruction to `openspec-ff-change/SKILL.md`: after step 3b, add instruction for recognizing user-shared knowledge during artifact creation
- [x] 2.4 Update hook templates in `bin/set-memory-hooks` for the new mid-flow blocks in apply/continue/ff

### Group 3: Ambient memory (CLAUDE.md)

- [x] 3.1 Add "Proactive Memory" section to `CLAUDE.md` with: recognition patterns, save threshold, confirmation format, deduplication rule (defer to active skill hooks)
- [x] 3.2 Include recall suggestion: "before starting major work, consider running set-memory recall to check for relevant past experience"

### Group 4: Tests and verification

- [x] 4.1 Verify `set-memory-hooks check` correctly detects new explore hooks
- [x] 4.2 Verify `set-memory-hooks install` patches explore skill correctly
- [x] 4.3 Verify `set-memory-hooks remove` cleans all hooks including new ones
