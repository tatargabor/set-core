## Context

The project currently stores all Claude Code instructions in a single `CLAUDE.md` (144 lines). GUI-specific rules (dialog patterns, debug log, startup instructions) load into every session context regardless of what the user is working on. There are no custom subagents — all work happens in the main conversation or via built-in agent types (Explore, Plan, general-purpose). The existing memory hook system (7 events in `.claude/settings.json`) is mature and must not be modified.

Claude Code now supports:
- `.claude/rules/*.md` with YAML frontmatter path scoping (auto-loaded, conditional on file paths)
- `.claude/agents/*.md` with tool restrictions, model selection, persistent memory
- Skill frontmatter: `context: fork`, `disable-model-invocation: true`
- `@path` imports in CLAUDE.md
- `SubagentStart` and `SessionStart[compact]` hook events

## Goals / Non-Goals

**Goals:**
- Reduce context waste by scoping GUI rules to `gui/**` paths only
- Enable specialized AI workers (reviewer, tester, verifier) as custom subagents
- Make CLAUDE.md concise (~60-70 lines) by moving reference content to rules/
- Preserve critical state through context compaction via compact instructions and hooks
- Inject project memory into spawned subagents via SubagentStart hook
- Update set-project init to deploy rules/ and agents/ to target projects

**Non-Goals:**
- Changing memory hook logic or scripts (wt-hook-memory, wt-hook-skill, etc.)
- Modifying OpenSpec skill/command file content (only frontmatter additions)
- Packaging set-core as a Claude Code plugin (future consideration)
- Agent Teams integration (experimental, separate effort)
- Creating path-scoped rules for non-set-core projects (only this project's rules)

## Decisions

### D1: Rules directory structure — flat with subdirectory for GUI

**Decision**: Use `.claude/rules/` with a `gui/` subdirectory for GUI-related rules. Other rules at top level.

```
.claude/rules/
├── gui/
│   ├── testing.md        ← paths: ["gui/**", "tests/gui/**"]
│   ├── dialogs.md        ← paths: ["gui/**"]
│   └── debug-startup.md  ← paths: ["gui/**"]
├── openspec-artifacts.md ← paths: ["openspec/**"]
└── readme-updates.md     ← paths: ["README.md", "docs/readme-guide.md"]
```

**Rationale**: The GUI rules are the biggest context savings — 3 separate sections (dialogs ~20 lines, testing ~10 lines, debug/startup ~30 lines) that only matter when editing GUI code. OpenSpec and README rules are smaller but still benefit from scoping.

**Alternative considered**: All rules at top level. Rejected because GUI has 3 related files that form a logical group.

**What stays in CLAUDE.md**: Persistent Memory (managed section), Help & Documentation, Auto-Commit After Apply (managed section), Compact Instructions (new), and quick-reference commands. These are universally needed on every prompt.

### D2: Custom subagents — three focused agents

**Decision**: Create 3 subagents:

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| `code-reviewer` | sonnet | Read, Grep, Glob | Read-only code review for quality, patterns, security |
| `gui-tester` | haiku | Bash, Read, Grep, Glob | Run GUI pytest suite, report pass/fail |
| `openspec-verifier` | sonnet | Read, Grep, Glob, Bash | Verify artifact-implementation coherence |

**Rationale**:
- `code-reviewer` is read-only by design — prevents accidental edits during review.
- `gui-tester` uses haiku (cheap/fast) since it just runs pytest and reports. Uses `Bash` for pytest execution.
- `openspec-verifier` uses sonnet for nuanced comparison between artifacts and code.

**Alternative considered**: A `memory-diagnostics` agent. Deferred because MCP tools already handle this interactively.

### D3: Skill frontmatter — selective optimization

**Decision**: Add `context: fork` to `openspec-explore` only. Add `disable-model-invocation: true` to `openspec-onboard`, `openspec-bulk-archive-change`, and `openspec-sync-specs`.

**Rationale**:
- `openspec-explore` is the heaviest context consumer (reads many files, long conversations). Forking isolates this from the main context.
- `openspec-onboard` is rarely used (one-time per user). `bulk-archive` and `sync-specs` are infrequent utility operations. Disabling model invocation means their descriptions don't consume context budget until explicitly called.
- Other skills (new, ff, apply, continue, verify, archive) are frequently used and benefit from being in the main context for continuity.

**Alternative considered**: Fork `openspec-verify-change` too. Deferred because verification results need to flow back to the main conversation for decision-making.

### D4: New hooks — compact re-injection and subagent context

**Decision**: Add two new hook entries to `.claude/settings.json`:

1. **SessionStart[compact]**: Re-inject critical state after auto-compaction
   ```json
   {
     "matcher": "compact",
     "hooks": [{
       "type": "command",
       "command": "wt-hook-memory SessionStart",
       "timeout": 10
     }]
   }
   ```
   Re-uses the existing `wt-hook-memory SessionStart` script — no new code needed.

2. **SubagentStart**: Inject project memory context into spawned subagents
   ```json
   {
     "matcher": "",
     "hooks": [{
       "type": "command",
       "command": "wt-hook-memory SubagentStart",
       "timeout": 10
     }]
   }
   ```
   Requires adding `SubagentStart` event handling to `wt-hook-memory`.

**Rationale**: The compact hook ensures memory context survives compaction (currently lost). The SubagentStart hook ensures custom subagents and Task-spawned agents have project memory context.

**Risk**: The SubagentStart hook adds latency to every subagent spawn. Mitigated by 10s timeout and the lightweight nature of `wt-hook-memory` (typically <1s).

### D5: CLAUDE.md slimming strategy — move, don't delete

**Decision**: Move content to `.claude/rules/` files, keeping only universally-needed sections in CLAUDE.md. Use `@docs/readme-guide.md` import for README update details.

Sections moving out:
- GUI Testing → `rules/gui/testing.md`
- macOS Always-On-Top Dialog Rule → `rules/gui/dialogs.md`
- GUI Debug Log + GUI Startup → `rules/gui/debug-startup.md`
- OpenSpec Artifacts rule → `rules/openspec-artifacts.md`
- README Updates → `rules/readme-updates.md`

Sections staying (modified):
- Persistent Memory (managed, unchanged)
- Help & Documentation (unchanged)
- Auto-Commit After Apply (managed, unchanged)
- Compact Instructions (new)

### D6: set-project init deployment — copy rules/ and agents/

**Decision**: Extend `deploy_set_tools()` in `bin/set-project` to also deploy `.claude/rules/` and `.claude/agents/` directories from the set-core repo to target projects.

The deploy follows the same copy pattern as commands and skills: `cp -r` with self-detection (skip if source == destination). Only set-core-owned rules are deployed (files in the set-core repo's `.claude/rules/`). Project-specific custom rules are not overwritten — use a naming convention or marker to distinguish.

**Decision on conflict avoidance**: set-core rules use a `wt-` prefix (e.g., `wt-gui-testing.md`) in target projects to avoid conflicts with project-specific rules. In the set-core repo itself, the prefix is not needed since these ARE the project rules.

## Risks / Trade-offs

**[Risk] Rules not loading as expected** → Test by checking Claude's behavior when editing `gui/` files vs `bin/` files. The `paths:` frontmatter YAML must use correct glob syntax.

**[Risk] Subagent context too sparse** → SubagentStart hook injects memory, but subagents don't have full CLAUDE.md rules. Custom agent `.md` files should include essential instructions inline.

**[Risk] Skill `disable-model-invocation` causes confusion** → Users might not see these skills in auto-complete. Document in Help & Documentation section which skills need explicit invocation.

**[Risk] `context: fork` in explore loses conversation state** → Explore results return as a summary. The user must explicitly integrate insights. This is acceptable since explore is a thinking tool, not an action tool.

**[Trade-off] Rules in target projects need wt- prefix** → Slight naming pollution, but prevents overwriting project-specific rules that might exist.
