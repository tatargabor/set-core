## Context

`wt-loop` has a `detect_next_change_action()` function (line 452) that scans `openspec/changes/*/` alphabetically to find the next incomplete change. This is used by `build_prompt()` (line 542) to inject OpenSpec-specific instructions into the agent's prompt — overriding the generic task description.

When the orchestrator dispatches a change to a worktree, the worktree branches from main and inherits ALL existing OpenSpec changes. The detect function picks up unrelated incomplete changes (e.g., proposal-only stubs) that sort alphabetically before the assigned change, causing the agent to work on the wrong task.

Current flow:
```
orchestrator → wt-loop start "Implement X" --done openspec
  → build_prompt() calls detect_next_change_action(wt_path)
  → detect scans ALL changes alphabetically
  → finds "A-unrelated-change" (no tasks.md) → returns "ff:A-unrelated-change"
  → prompt becomes "Run /opsx:ff A-unrelated-change" — assigned task X ignored
```

## Goals / Non-Goals

**Goals:**
- Orchestrated worktrees work on their assigned change only
- Solo Ralph loops don't auto-select changes via alphabetical scanning — the OpenSpec skills handle selection interactively
- Minimal change surface — this is a bugfix, not a redesign

**Non-Goals:**
- Cleaning up existing zombie changes on main (separate manual task)
- Changing how OpenSpec skills (opsx:apply, opsx:ff) select changes
- Adding change isolation to worktrees (e.g., deleting unrelated changes)

## Decisions

### 1. `--change` flag on wt-loop start

**Decision:** Add `--change <name>` CLI flag to `wt-loop start`, stored in `loop-state.json`.

**Rationale:** The loop state already persists task, done_criteria, model, etc. Adding `change` follows the same pattern. The orchestrator already knows the change name at dispatch time.

**Alternative considered:** Inject change name into CLAUDE.md in the worktree. Rejected — CLAUDE.md is shared/versioned, and this would be a fragile side-channel.

### 2. Scoped vs disabled detection

**Decision:** When `--change` is set, `detect_next_change_action()` only inspects that one change directory. When `--change` is NOT set, detection is **skipped entirely** — `build_prompt()` uses the generic task as `effective_task`.

**Rationale:** The alphabetical scan was a heuristic for "find something to do" — useful for benchmarks with numbered files (01-*.md, 02-*.md) but harmful in real projects with many changes. Without `--change`, the agent should rely on its task prompt and the OpenSpec skill's own AskUserQuestion-based selection.

**Alternative considered:** Keep alphabetical detection as fallback. Rejected — it's the root cause of the bug and provides no value when the task prompt already tells the agent what to do.

### 3. Orchestrator passes `--change` explicitly

**Decision:** `dispatch_change()` in `set-orchestrate` adds `--change "$change_name"` to the `wt-loop start` invocation.

**Rationale:** One-line change. The orchestrator already knows the change name — it created the proposal.md for it.

### 4. Benchmark mode preserved via `--change`

**Decision:** The benchmark numbered-file detection (`docs/benchmark/NN-*.md`) is kept but only activates when `--change` is NOT set AND those files exist. This preserves backward compatibility for benchmark runs that rely on ordered change processing.

**Wait — actually:** The benchmark mode also has the same problem. It should use explicit `--change` too. But that's a separate concern. For now, we keep the benchmark path as-is.

## Risks / Trade-offs

- **[Risk] Solo loops lose auto-detection** → Users must either pass `--change` or rely on the OpenSpec skill's interactive selection. This is intentional — the alphabetical heuristic was more harmful than helpful.
- **[Risk] Benchmark mode may need updating** → Old benchmark scripts that rely on auto-detection still work (benchmark path checked first), but new benchmarks should use explicit `--change`. Low risk — benchmarks are controlled environments.
