## Why

`set-orchestrate` currently requires a rigid `project-brief.md` with a `### Next` section parsed by bash regex (`parse_next_items()`). Real projects have specification documents (roadmaps, feature specs) that don't follow this format. Users must manually create and maintain a separate brief artifact that duplicates information from their spec — and keep it in sync as the spec evolves. Industry standard (Kiro, GitHub Spec-Kit, Devin) treats the spec as the direct input with LLM-based extraction, not regex parsing.

## What Changes

- Add `--spec <path>` flag to `set-orchestrate` as the primary input method
- Replace bash `parse_next_items()` regex with LLM-based "what's next" extraction in the `generate_plan()` Claude prompt
- Add optional `--phase <hint>` flag for explicit phase selection (e.g., `--phase 1`, `--phase "Security fixes"`)
- Implement hierarchical spec summarization: for large specs (>8k tokens), LLM creates a focused summary + relevant section extraction before decomposition
- Separate orchestrator directives into optional `.claude/orchestration.yaml` config file (project-level, not embedded in spec)
- Keep full backward compatibility: `project-brief.md` with `### Next` still works unchanged
- Update `generate_plan()` Claude prompt to handle arbitrary spec formats, status markers (checkboxes, emoji), and multi-language content

## Capabilities

### New Capabilities
- `spec-input`: Accept arbitrary specification documents as orchestration input via `--spec` flag, with LLM-based extraction of actionable items
- `orchestration-config`: Standalone `.claude/orchestration.yaml` for directives (max_parallel, merge_policy, test_command, etc.), decoupled from the spec document

### Modified Capabilities
- `project-brief`: Relax the rigid `### Next` requirement — brief format still supported but no longer the only input path. `parse_next_items()` becomes a fast-path optimization, not a hard requirement.
- `orchestration-engine`: `generate_plan()` prompt updated to handle both brief and spec inputs, with phase detection and hierarchical summarization for large documents.

## Impact

- **Code**: `bin/set-orchestrate` — `find_brief()` → `find_input()`, `generate_plan()` prompt rewrite, new `--spec`/`--phase` CLI args, config file loader
- **Config**: New optional `.claude/orchestration.yaml` file format
- **Template**: `openspec/project-brief.md.template` updated to mention `--spec` alternative
- **Tests**: `tests/orchestrator/` — new test cases for spec input, phase detection, config file
- **Docs**: Usage documentation for the new flags
- **Backward compat**: All existing `project-brief.md` workflows continue working without changes
