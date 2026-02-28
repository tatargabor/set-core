## Context

`wt-orchestrate` currently has a two-stage input pipeline:
1. **Bash parsing** — `parse_next_items()` extracts bullets from `### Next` via regex; `parse_directives()` extracts key-value config from `## Orchestrator Directives`
2. **Claude decomposition** — `generate_plan()` passes the entire brief + a fixed prompt to `claude -p`, which outputs a plan JSON

The problem: stage 1 enforces a rigid format that real project specs don't follow. The bash regex is the bottleneck — Claude in stage 2 can already understand arbitrary documents. The fix is to let the LLM handle extraction (stage 1) instead of bash regex.

Current code flow in `generate_plan()` (lines ~530-680):
```
find_brief() → parse_next_items() → parse_directives() → claude -p prompt → plan.json
```

## Goals / Non-Goals

**Goals:**
- Accept any markdown spec document via `--spec <path>`
- Let LLM determine "what's next" from status markers, phases, priorities
- Support explicit phase hints (`--phase`)
- Handle large specs (>8k tokens) via summarization
- Separate operational config from content
- Keep `project-brief.md` working unchanged

**Non-Goals:**
- Auto-updating the spec after changes complete (user responsibility)
- Supporting non-markdown input formats (PDF, Google Docs)
- Multi-spec orchestration (reading multiple spec files in one run)
- Removing `parse_next_items()` entirely — it stays as fast-path for briefs

## Decisions

### D1: Single Claude call for extraction + decomposition

**Choice:** Merge "what's next" extraction and change decomposition into one Claude call.

**Why not two calls:**
- Extra latency (~15-30s per call)
- The decomposition needs context from the extraction (which items, why those)
- One well-structured prompt handles both

**Implementation:** The prompt has two sections:
1. "Analyze this document — determine what should be implemented next"
2. "Decompose that batch into OpenSpec changes"

The prompt explicitly tells Claude to output its phase reasoning in a `phase_detected` field.

### D2: Brief fast-path preserved

**Choice:** When `project-brief.md` is detected (has `### Next` section), use the current bash-parsed flow. Only fall through to LLM extraction when bash parsing returns empty or `--spec` is used.

**Why:** Zero regression risk for existing users. The bash path is instant (no API call needed for extraction). LLM path only activates for spec input.

```
find_input()
  ├── --spec given? → LLM extraction path
  ├── --brief given? → bash parse path (existing)
  └── auto-detect:
      ├── project-brief.md exists + has ### Next → bash path
      └── otherwise → error with helpful message
```

### D3: Hierarchical spec summarization for large documents

**Choice:** When spec content exceeds ~8000 tokens (~32KB), do a pre-pass: extract a structured summary (TOC + status + relevant section) before the decomposition prompt.

**Implementation:** Two-step for large specs:
1. First `claude -p` call: "Summarize this spec. Output: section headers with status, and the full content of the next actionable phase." (~2k token output)
2. Second `claude -p` call: Normal decomposition using the summary + extracted section

**Why threshold at 8k tokens:** Below 8k, the full spec fits comfortably in the decomposition prompt alongside the system instructions and context. Above 8k, quality degrades as the model loses focus.

**Token estimation:** `wc -w` × 1.3 (rough word-to-token ratio for mixed content). No need for a tokenizer dependency.

### D4: Config file for directives

**Choice:** `.claude/orchestration.yaml` as optional config, with CLI flags as overrides, with in-document `## Orchestrator Directives` as fallback.

**Precedence (highest wins):**
1. CLI flags (`--max-parallel 3`)
2. `.claude/orchestration.yaml`
3. `## Orchestrator Directives` section in spec/brief
4. Built-in defaults

**YAML format:**
```yaml
max_parallel: 3
merge_policy: checkpoint
checkpoint_every: 3
test_command: "pnpm lint && pnpm build"
notification: desktop
token_budget: 0
pause_on_exit: false
```

**Why YAML not JSON:** Easier to comment, human-edit, and it's already the convention in `.claude/` for config files.

### D5: --phase flag semantics

**Choice:** `--phase` accepts either a number or a string. It's a hint to Claude, not a rigid filter.

- `--phase 1` → "Implement phase/priority 1"
- `--phase "Security fixes"` → "Implement the section about security fixes"
- No `--phase` → Claude auto-detects the first incomplete phase

The hint is injected into the decomposition prompt: `"The user requested phase: <hint>. Focus on this phase."`. Claude still has latitude to interpret what that means in context.

## Risks / Trade-offs

**[LLM non-determinism]** → The same spec may produce slightly different plans on re-run. Mitigation: the plan approval step already exists — user reviews before dispatch. Also, `plan.json` is persisted so re-runs don't overwrite an approved plan.

**[Large spec cost]** → Summarization adds an extra API call (~$0.02-0.05). Mitigation: only triggered above 8k token threshold. Most specs are under this.

**[YAML parser in bash]** → Bash has no native YAML parser. Mitigation: use `python3 -c 'import yaml; ...'` (python3 is already a dependency for topological sort) or a simple `grep`-based parser for the flat key-value format (no nested YAML needed).

**[Spec language]** → Specs may be in Hungarian, English, or mixed. Mitigation: Claude handles multilingual content natively. The prompt doesn't assume English.

## Migration Plan

1. Add `--spec` and `--phase` flags to CLI arg parsing
2. Add `find_input()` replacing `find_brief()` (backward compat wrapper)
3. Add config file loading (`.claude/orchestration.yaml`)
4. Rewrite `generate_plan()` prompt for dual-mode (brief vs spec)
5. Add summarization pre-pass for large specs
6. Update template and docs
7. Add tests for spec input path

**Rollback:** Since brief path is preserved unchanged, rollback = don't use `--spec`. No breaking changes.

## Open Questions

- Should `wt-orchestrate init` be added as a subcommand to interactively generate `.claude/orchestration.yaml`? (Deferred — not needed for MVP.)
- Should the spec summarization cache the summary to avoid re-summarizing on re-runs? (Nice-to-have, not MVP.)
