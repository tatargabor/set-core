## Why

OpenSpec skill prompts (SKILL.md) contain "soft hooks" — instructions telling the agent to run `set-memory recall` at start and `set-memory remember` at end. But these are just prompt instructions that the agent can skip, forget, or short-circuit when the task seems simple. This was observed in practice: the agent skipped memory recall and save during an `/opsx:explore` session because it jumped straight to editing a file. The memory save hooks need reinforcement at the hard hook level (Claude Code `Stop` event) to achieve near-100% compliance.

## What Changes

- **`wt-hook-stop` gains a memory reminder**: When the Stop hook fires and an active skill is detected (from the `.skill` file), the hook checks if the skill's SKILL.md contains `set-memory` instructions. If so, it outputs a reminder message to stdout that Claude Code injects back into the conversation, prompting the agent to run its memory saves.
- **Skills gain a `.memory` marker**: A lightweight sidecar file (`.memory`) next to `.skill` files indicates whether the active skill has memory hooks. This avoids re-parsing SKILL.md on every Stop event.

## Capabilities

### New Capabilities
- `stop-hook-memory-reminder`: The Stop hook detects active skills with memory steps and outputs a reminder for the agent to execute its memory recall/save protocol

### Modified Capabilities
- `skill-hook-automation`: The skill registration hook (`wt-hook-skill` / UserPromptSubmit) also writes a `.memory` marker when the matched skill's SKILL.md contains `set-memory` instructions

## Impact

- **Files**: `bin/wt-hook-stop` (add reminder logic), `bin/wt-hook-skill` (add .memory marker), `install.sh` (symlinks unchanged)
- **Dependencies**: None — uses existing `.set-core/agents/` infrastructure
- **APIs**: No external API changes. The Stop hook's stdout message is the interface — Claude Code shows it to the agent as a system reminder.
