# Kiro vs set-core — Feature Comparison & Adoption Analysis

**Date:** 2026-03-14
**Sources:** https://kiro.dev/docs/, https://kiro.dev/blog/ (47 blog posts, 7 doc sections)
**Purpose:** Identify Kiro innovations worth adopting into set-core

---

## 1. Spec-Driven Development

### Kiro Specs

3-file, 3-phase system:
- `requirements.md` — user stories + acceptance criteria
- `design.md` — technical architecture, sequence diagrams
- `tasks.md` — discrete implementation tasks with status tracking

Two spec types:
- **Feature Specs** — requirements-first OR design-first workflow
- **Bugfix Specs** — formalized bug condition (C), postcondition (P), preservation property (¬C→unchanged)

Key capabilities:
- IDE-integrated UI with visual task tracking (spec panel)
- Property-Based Testing (PBT) as verification gate between tasks
- "Run All Tasks" — batch execution with PBT + LSP + subagent validation per task
- Design-first workflow: start from technical design, derive requirements backward

### set-core OpenSpec

4-5 file system with richer lifecycle:
- `proposal.md` — scope, rationale, impact
- `specs/*.md` — per-capability specifications (delta format)
- `design.md` — technical architecture
- `tasks.md` — checkbox-based task tracking
- `.openspec.yaml` — metadata

Key capabilities:
- `/opsx:new` (step-by-step) and `/opsx:ff` (fast-forward) creation
- `/opsx:explore` — thinking partner mode (no implementation)
- `/opsx:sync` — delta spec → main spec evolution
- `/opsx:bulk-archive` — batch lifecycle management
- `/opsx:verify` — 3-dimensional verification (completeness/correctness/coherence)
- Multi-agent orchestration integration (DAG-based dispatch)

### Comparison

| Capability | Kiro | set-core |
|-----------|------|----------|
| Spec structure | 3 files, flat | 4-5 files, per-capability specs |
| Bugfix formalism (C, P, ¬C) | Yes | No |
| Property-Based Testing | Yes (Hypothesis) | No |
| Design-first workflow | Explicit choice | Implicit (proposal scope) |
| Run All Tasks (batch + validation) | Yes (PBT + LSP gate) | Ralph loop (no per-task PBT) |
| Multi-agent orchestration | No | Yes (DAG, parallel worktrees) |
| Spec evolution (delta sync) | No | Yes (/opsx:sync) |
| Bulk archive | No | Yes |
| Explore mode | No | Yes (/opsx:explore) |
| Visual IDE panel | Yes | CLI + GUI control center |

---

## 2. Memory & Learning Systems

### Kiro: CORAL (Continual Optimization via Reasoning and Adaptive Learning)

Fleet-level learning system:
- Samples thousands of real user sessions daily (opt-in)
- LLM-based root cause analysis on full trajectories (not just outcomes)
- Extracts generalizable lessons, checks for novelty and conflicts
- Ships fixes immediately (tool description updates, system prompt tweaks — no retraining)
- Tracks evidence confidence levels

Key discoveries:
- **Silent search failure**: `*.py` vs `**/*.py` glob patterns → 26% incorrect → fixed to 0.3% with one tool description update
- **`cd` command trap**: agents wrote `cd src && npm test` but tool requires `cwd` parameter → auto-correction layer → 100% failure → ~0%
- **Content drift**: auto-formatting causes `oldStr` not found in strReplace
- **Acknowledgment waste**: agents respond "Understood" then take no action

Philosophy: trajectory-based — 5-step success ≠ 17-step success. Efficiency matters, not just outcome.

### set-core: Shodh-Memory (5-Layer Hook System)

Per-project real-time memory:
- **L1 (SessionStart)**: warmstart cheat-sheet + hot-topics discovery (~500ms)
- **L2 (UserPromptSubmit)**: topic-based semantic search (~200ms)
- **L3 (PreToolUse)**: hot-topic pattern matching (2ms skip / 150ms match)
- **L4 (PostToolUseFailure)**: error-text parsing + auto-promote known fixes (~200ms)
- **L5 (Stop)**: haiku extraction + design choice capture (5-10s async)

Memory types: Decision, Learning, Context
Recall modes: semantic, temporal, hybrid, causal, associative
Storage: RocksDB with flock-based concurrency (per-project lock)
Sharing: git-based cross-machine sync, export/import

### Comparison

| Capability | Kiro CORAL | set-core Shodh |
|-----------|-----------|----------------|
| Scope | Fleet (thousands of users) | Per-project |
| Analysis | Batch (daily) | Real-time (per-prompt) |
| Trajectory analysis | Yes (step count, path quality) | Partial (Ralph iteration count) |
| Automatic pattern discovery | Yes (LLM root cause) | L4 (error → known fix) |
| Confidence tracking | Yes | No |
| User-accessible | No (closed system) | Yes (CLI, MCP, brain, dashboard) |
| Cross-machine sharing | N/A (cloud service) | Yes (git-based) |
| Visualization | No | Yes (brain, metrics, dashboard) |
| Fix shipping | Tool descriptions, system prompts | Memory injection via hooks |

---

## 3. Agent Orchestration

### Kiro Autonomous Agent

- Non-session-based, persistent context across repos
- Sandbox isolation per task (Docker-based)
- 3 sub-agents: planner, writer, verifier
- Max 10 concurrent tasks
- Output: opens PR with detailed explanation
- Persistent learning: applies code review feedback to future tasks
- Network access tiers: integration-only / common deps / open internet
- MCP integrations for specialized tools

### set-core Orchestration Engine

- Spec → plan (DAG with dependencies) → dispatch (parallel worktrees) → monitor → verify → merge
- Sentinel supervision: 15s poll, auto-restart, crash diagnosis, findings report
- Merge pipeline: eager / checkpoint / manual modes
- Verification gates: build, design review, code review, smoke tests
- Watchdog: stall detection, infinite loop detection (task hash comparison)
- Replan on stall: auto-replan from updated spec, preserves completed work
- Design-aware dispatch: Figma snapshot injection into proposals
- Events log: `orchestration-events.jsonl` for external tools
- Cross-machine team sync: git-based messaging, encrypted DM

### Comparison

| Capability | Kiro | set-core |
|-----------|------|----------|
| Parallelism | Max 10 tasks | Configurable (max_parallel) |
| Isolation | Docker sandbox | Git worktree |
| Dependency DAG | No | Yes |
| Merge pipeline | No (opens PR) | Yes (eager/checkpoint/manual) |
| Sentinel/supervisor | No | Yes (auto-restart, crash diagnosis) |
| Replan on stall | No | Yes |
| Smoke tests (post-merge) | No | Yes |
| Design-aware dispatch | No | Yes (Figma snapshot injection) |
| Cross-machine coordination | No | Yes (team sync, messaging) |
| GUI monitoring | No | Yes (PySide6 control center) |
| Learning from reviews | Yes (persistent) | Via memory (L5 extraction) |
| Sandbox security | Yes (Docker + network tiers) | No (worktree only) |

---

## 4. Code Editing & Quality

### Kiro Innovations

**AST-Based Code Editing**
- Semantic selectors: `ClassName.methodName`, `function:name`, `field:name`
- Operations: `insert_node`, `replace_node`, `delete_node`, `replace_in_node`
- Measured results (PolyBench50):
  - LLM calls: -34.3%
  - Output tokens: -29.95%
  - Input tokens: -20.47%
- Real-world feature request: 49.3% faster, 24.1% fewer LLM calls, tool errors: 2→0
- Formatting-resistant: tabs/spaces don't break edits

**LSP Diagnostics Integration**
- 35ms feedback loop (vs seconds/minutes for build commands)
- Catches: type mismatches, property hallucinations, import errors, lint violations, config errors
- 29% reduction in command executions
- Works across: TypeScript, Python, Rust, Java, SQL, YAML, Terraform, Kubernetes

**Semantic Refactoring**
- `vscode.prepareRename` + `vscode.executeDocumentRenameProvider` for workspace-wide symbol rename
- `vscode.WorkspaceEdit.renameFile` for smart file relocation with import updates
- Correctness by construction: delegates to battle-tested LSP infrastructure

**Checkpointing**
- Per-task state snapshots during active sessions
- Single-click rollback: reverts all file changes + conversation state
- Auto-creates checkpoints before task initiation
- Session-scoped (not persistent across restarts)
- Complements (not replaces) git version control

### set-core Current State

- Text-based editing (Claude Code's native strReplace)
- Build-time validation only (test_command, build_command in orchestration gates)
- Git-based rollback (coarser granularity than checkpointing)
- 3-dimensional verification: completeness, correctness, coherence
- Design token mismatch checking (if Figma MCP available)

### Comparison

| Capability | Kiro | set-core |
|-----------|------|----------|
| Code editing | AST-based (semantic) | Text-based (strReplace) |
| Read efficiency | 58% fewer tokens | Full file reads |
| Write efficiency | 73% fewer tokens | Full replacement blocks |
| Edit resilience | Formatting-resistant | Exact match required |
| Diagnostics feedback | 35ms (LSP) | Build-time only |
| Semantic rename | Yes (LSP-powered) | No |
| Smart file relocate | Yes (LSP-powered) | No |
| Checkpointing | Per-task snapshots | Git commits |
| Property-Based Testing | Yes (Hypothesis) | No |
| Multi-dimensional verify | No | Yes (3 dimensions) |
| Design compliance check | No | Yes |

---

## 5. Context Management & Steering

### Kiro Steering

File-based persistent context in `.kiro/steering/`:
- `product.md` — business context, target users, features
- `tech.md` — frameworks, libraries, constraints
- `structure.md` — file organization, naming, architecture

Inclusion modes:
- **Always** (default) — loaded every interaction
- **Conditional** (fileMatch) — auto-included when editing matching files (e.g., `components/**/*.tsx`)
- **Manual** — referenced via `#steering-name` syntax
- **Auto** — included when request description matches predefined criteria

Global steering: `~/.kiro/steering/` (workspace overrides global)
AGENTS.md support: always-active markdown directives
File references: `#[[file:relative_path]]` syntax for live file linking

### Kiro Powers

Dynamic MCP + steering bundles:
- Keyword-activated (mentioning "database" triggers Neon power)
- Near-zero baseline context (vs 50k+ tokens with all MCP tools loaded)
- Bundle components: POWER.md (entry point), MCP config, hooks/steering
- Task-specific context loading: "Writing RLS policies" loads only supabase-rls-policies.md
- Partner ecosystem: Datadog, Figma, Neon, Netlify, Postman, Supabase, Stripe
- Planned cross-IDE support (CLI, Cline, Cursor, Claude Code)

### set-core Context System

- `.claude/rules/` — always-on markdown rules (committed to git)
- `CLAUDE.md` — project instructions
- `orchestration.yaml` — orchestration configuration
- Skills — on-demand invocation (`/opsx:*`, `/set:*`)
- Memory hooks — automatic context injection (L1-L5)
- Hot-topics — discovered patterns for L3 optimization

### Comparison

| Capability | Kiro | set-core |
|-----------|------|----------|
| Always-on rules | .kiro/steering/ | .claude/rules/ + CLAUDE.md |
| Conditional (fileMatch) | Yes | No |
| Manual reference | #steering-name | Skills (/opsx:*, /set:*) |
| Auto-include (description) | Yes | L2 memory recall (semantic) |
| Dynamic tool loading | Powers (keyword-activated) | Skills (manually invoked) |
| Baseline context cost | Near-zero (Powers) | Skills metadata always loaded |
| File reference syntax | #[[file:path]] | No |
| Global scope | ~/.kiro/steering/ | User-level memory + config |
| Partner ecosystem | 10+ partners | Custom MCP servers |

---

## 6. Unique set-core Strengths (Not in Kiro)

1. **Multi-agent DAG orchestration** — dependency-aware parallel execution with N agents
2. **Sentinel supervision** — 15s poll, auto-restart, crash diagnosis, findings report
3. **Merge pipeline** — eager/checkpoint/manual merge with conflict resolution
4. **Cross-machine team sync** — git-based messaging, activity broadcast, encrypted DM
5. **Real-time GUI control center** — always-on-top, multi-project, API burn rate
6. **Spec evolution** — /opsx:sync delta→main spec merging
7. **Explore mode** — thinking partner with ASCII diagrams, no code
8. **User-accessible memory** — brain, dashboard, metrics, export/import, cross-machine sync
9. **Design-aware orchestration** — Figma preflight→planner→dispatch→verify pipeline
10. **Project health audit** — 6-dimension scan with interactive remediation

---

## 7. Adoption Recommendations

### High Priority (High Impact, Lower Effort)

#### 7.1 Bugfix Spec Formalism

**What:** Formalize bug fixes with explicit bug condition (C), postcondition (P), and preservation property (¬C→unchanged).

**Why:** Current bugfix handling is ad-hoc. Kiro's formalism prevents the "bug fix paradox" — agents over-engineering solutions and breaking unrelated code. The three-part structure (current behavior / expected behavior / unchanged behavior) creates testable boundaries.

**How:**
- New OpenSpec schema type: `bugfix`
- `bugfix.md` template with C/P/Preservation sections
- `/opsx:new` and `/opsx:ff` recognize bugfix schema
- `/opsx:verify` checks preservation property explicitly

**Kiro reference:** Blog "The bug fix paradox" (2026-02-19), Blog "New spec types" (2026-02-18)

#### 7.2 Conditional Context Loading (fileMatch)

**What:** Auto-include specific rules when editing files matching glob patterns.

**Why:** Reduces context waste. React conventions only loaded when editing `.tsx`, API guidelines only when editing `routes/`. Currently all rules load always.

**How:**
- `.claude/rules/*.md` frontmatter: `fileMatch: "components/**/*.tsx"`
- L2 hook or PreToolUse hook checks current file against patterns
- Only matching rules injected into context

**Kiro reference:** Docs "Steering" — inclusion modes

#### 7.3 Property-Based Testing Integration

**What:** Generate invariant-based tests from specifications using Hypothesis (Python) or fast-check (JS/TS).

**Why:** Current verification is checkbox + grep. PBT generates ~100 test cases per property, catching edge cases manual tests miss. Kiro's "Run All Tasks" uses PBT as a gate between tasks.

**How:**
- `/opsx:verify` enhanced: extract requirements → generate PBT → run
- Optional per-task PBT gate in Ralph loop
- Spec requirement → property mapping in tasks.md

**Kiro reference:** Blog "Property-Based Testing" (2025-11-17), Blog "Run all tasks" (2026-01-16)

#### 7.4 Trajectory Analysis (CORAL-lite)

**What:** Evaluate not just whether tasks succeed, but how efficiently (step count, tool errors, retries, stalls).

**Why:** A 17-step "success" is a failure pattern. Kiro's CORAL discovered that single tool description updates eliminated 26% error rates. Trajectory data reveals systemic issues.

**How:**
- Ralph loop: track per-task metrics (iteration count, tool calls, errors, duration)
- `set-memory metrics` extended: trajectory quality scoring
- L5 hook: extract "this took too many steps" patterns → memory
- Periodic analysis: which tasks/patterns cause inefficiency

**Kiro reference:** Blog "Hidden inefficiencies in AI coding" (2026-02-23)

### Medium Priority (High Impact, Higher Effort)

#### 7.5 AST-Aware Code Reading (tree-sitter)

**What:** MCP tool for symbol-level code reading instead of full file reads.

**Why:** Kiro's AST editing achieves 58% fewer read tokens. While we can't modify Claude Code's editing, we can add a `read_symbol(file, "ClassName.method")` MCP tool using tree-sitter.

**How:**
- Python MCP tool wrapping tree-sitter
- Operations: read_symbol, list_symbols, read_imports
- Used by agents when they know the target symbol

**Kiro reference:** Blog "Surgical precision with AST" (2026-02-27)

#### 7.6 Lightweight Diagnostics (tsc/eslint)

**What:** Run fast type/lint checks after edits, not just at build gate.

**Why:** Kiro's 35ms LSP feedback catches type errors, import errors, property hallucinations immediately. We can approximate with `tsc --noEmit` (~2-5s) after TypeScript edits.

**How:**
- PostToolUse hook: if file is `.ts/.tsx`, run `tsc --noEmit --pretty` on changed files
- Parse diagnostics, inject as system-reminder
- Configurable per-project in orchestration.yaml

**Kiro reference:** Blog "Empowering Kiro with IDE diagnostics" (2026-01-14)

#### 7.7 Per-Task Checkpointing

**What:** Lightweight state snapshots before each task execution.

**Why:** Finer rollback granularity than git commits. If task 5/10 fails, rollback to pre-task-5 state without losing tasks 1-4.

**How:**
- Ralph loop: `git tag wt-checkpoint-<task-id>` before each task
- On failure: `git reset --hard wt-checkpoint-<task-id>`
- Cleanup: remove checkpoint tags after successful merge

#### 7.8 Powers-like Dynamic Skill Loading

**What:** Keyword-activated skill + MCP bundles with near-zero baseline cost.

**Why:** Currently all skill metadata is loaded. Powers model: only load when topic matches keywords.

**How:**
- `SKILL.md` frontmatter: `keywords: ["database", "migration", "schema"]`
- L2 hook: if prompt keywords match, load full skill instructions
- Deactivate non-matching skills to save context

**Kiro reference:** Blog "Introducing Kiro Powers" (2025-12-03)

### Low Priority (Lower Impact or Not Applicable)

#### 7.9 Design-First Workflow Flag
Explicit "design-first" option in `/opsx:new` — start from design.md, derive requirements. Currently implicit.

#### 7.10 Semantic Rename/Relocate
Would require tree-sitter + language-specific rename logic. High effort, limited benefit in CLI context.

#### 7.11 Enterprise Governance
Not relevant — set-core is single-user/small-team. MCP registry controls unnecessary.

#### 7.12 ACP (Agent Communication Protocol)
We have git-based team sync. ACP is IDE-centric. Only relevant if we want Kiro CLI interop.

---

## 8. Key Takeaways

1. **Kiro's biggest technical innovation is AST-based editing** — 34% fewer LLM calls, formatting-resistant. We can partially adopt via tree-sitter symbol reading.

2. **Property-Based Testing is Kiro's strongest quality mechanism** — invariant-based verification vs our checkbox-based verify. This is the highest-value adoption.

3. **CORAL (fleet learning) is powerful but not replicable** — we don't have thousands of users. However, trajectory analysis on our own Ralph loops is achievable and valuable.

4. **Bugfix Spec formalism solves a real problem** — agents over-engineer fixes. The C/P/¬C structure prevents scope drift with minimal overhead.

5. **set-core is significantly ahead in orchestration** — Kiro has no multi-agent DAG, no sentinel, no merge pipeline, no cross-machine sync. This is our core differentiator.

6. **Context efficiency matters** — Kiro's conditional loading (fileMatch) and Powers (keyword activation) reduce waste. Our hooks do similar work but less precisely.

7. **The two tools complement more than compete** — Kiro excels at single-agent code quality; set-core excels at multi-agent coordination. Best ideas from both create a stronger system.
