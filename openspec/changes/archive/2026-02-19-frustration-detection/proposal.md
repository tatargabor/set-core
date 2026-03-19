## Why

When users express frustration ("this doesn't work again", "sokadjára rontod el", "nem ezt kértem"), these are high-signal moments — the emotion is a natural priority amplifier. Currently, frustration signals are only processed at session end (Stop hook transcript extraction) — if the session crashes or the user gives up, those insights are lost. The UserPromptSubmit hook fires on every user message and is the ideal place to detect emotional charge in real-time, save the prompt as a high-priority memory, and inject a warning to the current agent.

The goal is simple: **detect if a prompt is emotionally charged, save it immediately, and alert the current agent.** The lesson itself is drawn by the semantic search system (surfacing the saved memory when relevant) and by future agents interpreting the context.

## What Changes

- Add an **emotion detection module** (`lib/frustration.py`) with bilingual (English + Hungarian) pattern matching using ~30-35 regexes organized in 3 trigger groups (strong, medium, session boost)
- Integrate into the **UserPromptSubmit** handler in `wt-hook-memory`:
  - **Save**: moderate+ detection → save entire prompt as high-priority `Learning` memory via `set-memory remember`
  - **Inject**: any detection → add warning to `additionalContext` output so the current agent is immediately aware
- Track **session frustration history** in the existing dedup cache to detect escalation patterns (3+ mild triggers → next mild triggers save)
- Add **agent-correction** as a primary detection pattern ("nem ezt kértem", "wrong file", "that's not what I asked") — the most valuable signal in a developer-agent context

## Capabilities

### New Capabilities
- `frustration-detection`: Bilingual (EN/HU) emotional charge detection with simple trigger logic (strong/medium/session-boost), integrated into UserPromptSubmit for immediate memory save and agent context injection

### Modified Capabilities
- `hook-driven-memory`: Add emotion detection call in UserPromptSubmit handler, extend additionalContext output with agent warning, extend session dedup cache with frustration history

## Impact

- **Modified**: `bin/wt-hook-memory` — UserPromptSubmit handler gains emotion detection + injection + save
- **New**: `lib/frustration.py` — Python module (~30-35 regex patterns, simple trigger logic, no scoring/multipliers)
- **Modified**: Session dedup cache (`/tmp/set-memory-session-*.json`) — extended with `frustration_history` key
- **Dependencies**: None new — uses existing `set-memory remember` CLI and Python stdlib
- **Performance**: Pattern matching adds ~5-10ms per prompt (pure regex, no ML inference)
