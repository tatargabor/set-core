## 1. Context Builder Module

- [x] 1.1 Create `lib/wt_orch/chat_context.py` with `build_chat_context(project_path: Path) -> str` function
- [x] 1.2 Implement role description section — supervisor identity, Hungarian language instruction, Level 2 capabilities summary
- [x] 1.3 Implement state summary section — read `orchestration-state.json`, format as compact table (change, status, tokens, last activity)
- [x] 1.4 Implement config summary section — read `.claude/orchestration.yaml`, extract key directives (max_parallel, token_budget, test_command, etc.)
- [x] 1.5 Implement commands reference section — categorized list of available bash commands (query, control, worktree, comms) with examples
- [x] 1.6 Handle missing files gracefully — no state file → "Nincs aktív orchestration", no config → omit config section, parse error → "State fájl olvashatatlan"

## 2. Chat Integration

- [x] 2.1 Import `build_chat_context` in `chat.py` and call it in `_run_claude()` before building the command
- [x] 2.2 Add `--append-system-prompt` with the built context string to the claude command (both fresh and --resume paths)
- [x] 2.3 Verify context is refreshed on every message (not cached from session start)

## 3. Verification

- [x] 3.1 Start wt-orch-core serve, open chat tab, send a message — verify agent identifies as orchestration supervisor and responds in Hungarian
- [x] 3.2 Test with a project that has active orchestration — verify agent can describe current state without being told what files to read
- [x] 3.3 Test with a project without orchestration — verify agent handles gracefully
- [x] 3.4 Test follow-up messages — verify --resume works with --append-system-prompt together
