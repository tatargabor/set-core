## Context

The `shodh-memory-integration` change manually added memory hooks to 5 OpenSpec SKILL.md files. These hooks enable recall (search past memories before work) and remember (save learnings after work). However, `openspec update` regenerates SKILL.md files from templates, destroying the hooks. Users need a reliable install/reinstall mechanism and a `/wt:memory` skill for direct memory interaction.

## Goals / Non-Goals

**Goals:**
- Idempotent `set-memory-hooks install/check/remove` CLI for hook lifecycle management
- `/wt:memory` slash command for agents to interact with memory
- GUI integration: "Install Memory Hooks" menu action, auto-reinstall after openspec update
- Hook status visible in FeatureWorker cache and [M] button tooltip

**Non-Goals:**
- Modifying the openspec CLI itself to support hooks natively
- Supporting custom hook content (hooks are hardcoded to match shodh-memory-integration patterns)
- Supporting non-OpenSpec skill files

## Decisions

### 1. Marker-based patching over diff/patch
Hook sections are wrapped in marker comments (`<!-- set-memory hooks start -->` / `<!-- set-memory hooks end -->`). This allows:
- Reliable detection: `grep -q "set-memory hooks start"` → instant check
- Clean removal: delete between markers
- Idempotent install: skip if markers present
- No dependency on `patch` or diff tooling

Alternative: `git apply` patches — fragile when SKILL.md content changes between openspec versions.

### 2. Hardcoded hook templates in the script
Each of the 5 SKILL.md files gets a specific hook template stored as a heredoc in `set-memory-hooks`. The templates match the exact patterns from shodh-memory-integration.

Alternative: External template files — adds complexity with no benefit since hooks rarely change.

### 3. Insertion point detection via step numbering
Each hook template specifies an anchor pattern (e.g., `"2. **Check status"` for apply-change's step 4b recall). The script finds the anchor line and inserts the hook block after it.

Strategy: Find the step N header line, then insert the hook block on the next blank line after that step's content. Each skill has a defined insertion point:
- `openspec-new-change`: after step 1 → insert 1b
- `openspec-continue-change`: after step 2 → insert 2b
- `openspec-ff-change`: after step 3 → insert 3b
- `openspec-apply-change`: after step 4 → insert 4b, extend step 7
- `openspec-archive-change`: before guardrails → insert step 7

### 4. Auto-reinstall via chained command in _run_openspec_action
After `wt-openspec update --force` completes, `_run_openspec_action` checks if memory hooks were previously installed (via `set-memory-hooks check --json`). If yes, it runs `set-memory-hooks install` automatically, showing both commands in the CommandOutputDialog.

### 5. /wt:memory as a simple command file
`.claude/commands/wt/memory.md` follows the same pattern as `wt/msg.md`, `wt/broadcast.md` — a markdown file describing what the agent should do with `$ARGUMENTS` parsing. No new infrastructure needed.

## Risks / Trade-offs

- **Hook content drift**: If openspec significantly restructures SKILL.md step numbering, insertion points may break. → Mitigation: `set-memory-hooks check` detects partial installation; step anchors use semantic patterns not just numbers.
- **Openspec version compatibility**: Future openspec versions may change SKILL.md format. → Mitigation: Marker-based detection is format-agnostic; only insertion logic depends on structure.
- **Auto-reinstall timing**: If `set-memory-hooks install` fails after `wt-openspec update`, hooks are silently lost. → Mitigation: FeatureWorker's next poll detects missing hooks and updates [M] tooltip.
