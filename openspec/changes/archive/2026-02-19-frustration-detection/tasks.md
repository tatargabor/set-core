## 1. Core Detection Module

- [x] 1.1 Create `lib/frustration.py` with strong trigger patterns: agent-correction (~10 patterns EN+HU), expletives (~10 patterns EN+HU), giving-up (~8 patterns EN+HU) — all accent-tolerant for Hungarian
- [x] 1.2 Add medium trigger patterns: repetition+negation combo (~5), temporal frustration (~5), escalation/absolutes (~4), intensifiers (ALL CAPS, excessive punctuation)
- [x] 1.3 Implement `detect(prompt, session_history=None)` function with simple trigger logic: 1 strong→high, 2+ medium→moderate, 1 medium+session≥3→moderate, 1 medium→mild, 0→none
- [x] 1.4 Implement session history tracking: accept optional dict, increment count on any detection, escalate single medium to moderate when count≥3

## 2. Hook Integration

- [x] 2.1 Add emotion detection call to `handle_user_prompt()` in `bin/wt-hook-memory`: call `lib/frustration.py` detect with prompt text and session history from dedup cache
- [x] 2.2 Extend session dedup cache with `frustration_history` key (count, last_level)
- [x] 2.3 On moderate/high: save entire prompt as memory via `set-memory remember --type Learning --tags frustration,recurring[,high-priority]` with level prefix
- [x] 2.4 On any detection (mild+): inject warning into `additionalContext` output for the current agent
- [x] 2.5 Add debug logging for emotion detection results (`_dbg` calls with level, triggers)

## 3. Testing

- [x] 3.1 Create `tests/test_frustration.py` with unit tests: strong triggers (agent-correction EN+HU, expletives EN+HU, giving-up EN+HU), medium triggers, neutral prompts returning none
- [x] 3.2 Add trigger logic tests: single strong→high, 2 medium→moderate, 1 medium→mild, session boost, no triggers→none
- [x] 3.3 Add accent-tolerance tests: Hungarian patterns match with and without accents
- [x] 3.4 Integration test: end-to-end hook call with mock set-memory, verify save on moderate+, inject on mild+, no action on none
