# Sentinel-v2 Gap Analysis: Missing Capabilities from Industry Best Practices

## 1. Already Covered (What sentinel-v2 handles well)

sentinel-v2 already addresses many core orchestration needs:

- **Self-healing watchdog** with per-state timeouts, hash-based loop detection, and 4-level escalation chain -- this is competitive with or ahead of most open-source tools
- **Event-sourced audit trail** (JSONL) with structured event types, rotation, and auto-generated run reports -- matches the direction OpenHands V1 took with event-sourced state
- **Worktree isolation** for parallel agents -- the dominant industry pattern, used by Claude Code Agent Teams, Multiclaude, Overstory, and Cursor Background Agents
- **Merge conflict avoidance** via project-knowledge cross-cutting file registry and scope overlap detection
- **Context pruning** to reduce token overhead in agent worktrees
- **Modular decomposition** from monolith to sourced libraries -- mirrors OpenHands V0-to-V1 refactor motivation
- **Model routing** (complexity-based) -- Codex does this natively with different model tiers; Claude Agent Teams community has requested it
- **Sentinel crash-restart with backoff** -- basic pattern, being enhanced to liveness-aware
- **Replan cycle** with completed-work injection to avoid duplication
- **Verification rules** (project-knowledge) for post-implementation checks before merge

## 2. GAPS Found

### GAP 1: Agent-to-Agent Communication / Shared Discovery

**Description:** Claude Code Agent Teams introduced inter-agent messaging (mailbox system) where teammates can message each other directly, share discoveries mid-task, and challenge each other's approaches. sentinel-v2's agents (Ralph loops in worktrees) are completely isolated -- they cannot share findings, warn siblings about pitfalls, or coordinate on shared interfaces. Each agent works blind to what others are doing.

**Who does it:** Claude Code Agent Teams (mailbox + broadcast), OpenHands (AgentDelegateAction), Overstory (SQLite mail system), Codex (MCP-based inter-agent handoffs)

**Priority:** HIGH

**Recommendation:** Add an agent message bus. Implementation: a shared `orchestration-messages.jsonl` file (or per-change mailbox directories) that agents can read. The dispatcher injects a "sibling status summary" into each agent's context at dispatch time (what other changes exist, what files they touch). For mid-execution updates, a lightweight `wt-agent-notify` command agents can call to post discoveries that the monitor loop broadcasts to relevant siblings on their next resume. Start simple: broadcast completed-change summaries to in-progress agents touching related files.

---

### GAP 2: Automatic Context Compaction for Long-Running Agents

**Description:** OpenAI Codex has automatic context compaction built into the agent loop -- when token count exceeds a threshold, the conversation is compacted transparently. GPT-5.1-Codex-Max is natively trained for compaction across multiple context windows. sentinel-v2 has no mechanism to help agents that exhaust their context windows mid-task. The watchdog detects stalls but cannot help an agent compact and continue.

**Who does it:** OpenAI Codex (auto_compact_limit, `/responses/compact` endpoint), Cursor (built-in `/summarize` command)

**Priority:** MEDIUM (depends on Claude Code adding native compaction support)

**Recommendation:** Add a `watchdog_context_action` escalation option. Before killing a stalled agent, the watchdog could trigger a "context rescue" -- saving the agent's current progress (git diff), killing the session, and re-dispatching with a compacted prompt that includes the diff and a "continue from here" instruction. This is a poor-man's compaction but could save runs. Track context usage if Claude Code exposes token counts.

---

### GAP 3: Per-Change Token Budgets and Cost Attribution

**Description:** sentinel-v2 has a global `token_budget` and `token_hard_limit` but no per-change token budget. Industry best practice is per-agent/per-lane token budgets with alerting. When one agent burns 5M tokens on a simple task, there is no brake until the global budget is hit.

**Who does it:** Codex (per-task budgeting), industry best practice (per-lane backoff budgets), Cursor (usage tracking per session)

**Priority:** HIGH

**Recommendation:** Add `max_tokens_per_change` directive (default: configurable, e.g. 2M). The watchdog checks each change's `tokens_used` against its budget every poll cycle. When a change exceeds its budget: Level 1 = warn, Level 2 = pause and notify, Level 3 = fail. Complexity-based budgets: S=500K, M=2M, L=5M, XL=10M. This prevents runaway agents from consuming the entire budget on a single change.

---

### GAP 4: Partial Work Salvage on Failure

**Description:** When a change fails (watchdog escalation level 4, or agent crashes), sentinel-v2 marks it as `failed` and the work is lost. There is no mechanism to salvage partial progress -- the git diff in the worktree may contain valuable partial implementation. Replit Agent has checkpoint/rollback. Codex preserves work across compaction. Industry practice treats partial results as more valuable than blocked pipelines.

**Who does it:** Replit Agent (checkpoints + rollback), Codex (persistent thread state), industry pattern ("partial results over blocked pipelines")

**Priority:** HIGH

**Recommendation:** Before marking a change as `failed`, automatically: (1) capture `git diff` from the worktree, (2) save it as `changes/{name}/partial-diff.patch`, (3) record which files were modified and test results in the event log. When replanning or retrying, the dispatcher can provide this patch as "previous progress" context so the next agent does not start from zero. Add a `salvage_on_fail` directive (default: true).

---

### GAP 5: Quality Gate Hooks (Pre/Post Events)

**Description:** Claude Code Agent Teams has `TeammateIdle` and `TaskCompleted` hooks that run external scripts to enforce quality gates -- exit code 2 sends feedback and keeps the agent working. sentinel-v2's verification is built-in (test, review, smoke, project-knowledge rules) but not extensible. Users cannot inject custom checks without modifying set-core source.

**Who does it:** Claude Code Agent Teams (hooks system: TeammateIdle, TaskCompleted), Codex (MCP-based tool gating), Multiclaude (CI-centric gates)

**Priority:** MEDIUM

**Recommendation:** Add hook points in the orchestration lifecycle: `pre_dispatch`, `post_verify`, `pre_merge`, `post_merge`, `on_fail`. Each hook is an optional shell script path in `orchestration.yaml`. The hook receives change name, status, worktree path as arguments. Non-zero exit blocks the transition. This makes verification extensible without modifying set-core internals. Example: a `pre_merge` hook that runs `pnpm lint` or checks for console.log statements.

---

### GAP 6: Retry with Exponential Backoff and Jitter

**Description:** sentinel-v2's watchdog escalation is linear (level 0->1->2->3->4) with fixed timing. The sentinel uses a fixed 30s backoff between restarts. Industry best practice for 2025-2026 is exponential backoff with jitter to prevent thundering-herd effects, plus classification of transient vs. permanent failures.

**Who does it:** Industry standard (exponential backoff + jitter), AWS Strands Agents, all production distributed systems

**Priority:** MEDIUM

**Recommendation:** (1) Sentinel backoff: change from fixed 30s to exponential (30s, 60s, 120s, 240s) with jitter (random 0-25% added). (2) Watchdog: classify failures as transient (PID died, API timeout) vs. permanent (test failures, scope violation) and only retry transient failures. (3) Add `max_retries_per_change` directive to cap how many times a single change can be retried before permanent failure.

---

### GAP 7: Agent Teams Abstraction -- Concrete Hooks

**Description:** sentinel-v2's design mentions an "Agent Teams abstraction layer" as a non-goal (abstraction layer only, not implementation). But Claude Code Agent Teams is now available (experimental, Feb 2026). The spec should define concrete integration hooks: how to dispatch via Agent Teams instead of wt-loop, how to map worktrees to teammates, how to use the shared task list and mailbox.

**Who does it:** Claude Code Agent Teams (shared task list, mailbox, TeammateIdle/TaskCompleted hooks, plan approval workflow)

**Priority:** HIGH

**Recommendation:** Define a `dispatch_backend` directive with values `wt-loop` (current) and `agent-teams`. For `agent-teams` mode: (1) the orchestrator becomes the team lead, (2) each change maps to a teammate spawned with a targeted prompt, (3) the shared task list maps to the orchestration plan, (4) teammate completion triggers poll_change verification, (5) TeammateIdle hook triggers watchdog check. This does not need to be built now, but the interfaces should be specified so the modular extraction does not preclude it.

---

### GAP 8: Structured Observability / Tracing

**Description:** sentinel-v2's event log is a good start, but it lacks structured tracing across the full agent lifecycle. Industry practice in 2025-2026 is OpenTelemetry-style spans with parent-child relationships, per-trace cost attribution, and queryable observability. The flat JSONL event log cannot express: "this merge attempt was triggered by this poll cycle which was part of this monitor loop iteration."

**Who does it:** Langfuse (agent observability), AWS Strands (OpenTelemetry integration), all production-grade frameworks

**Priority:** LOW (event log is sufficient for now, tracing is future work)

**Recommendation:** Add a `trace_id` field to events that links related events into a trace (e.g., all events for a single change share a trace). Add a `span_id` for nested operations (e.g., merge_attempt within a poll_cycle). This is a simple addition to the JSONL schema that enables future tooling without requiring OpenTelemetry infrastructure. Reserve the fields now even if unused.

---

### GAP 9: Idempotent Operations / Crash-Safe State Transitions

**Description:** The current state management uses read-modify-write on `orchestration-state.json` with `jq ... > tmp && mv tmp state.json`. If the orchestrator crashes between the jq write and the mv, or during a multi-step state transition (dispatch + update status + update worktree path), the state can be inconsistent. OpenHands V1 uses event-sourced state with deterministic replay specifically to solve this.

**Who does it:** OpenHands V1 (event-sourced state with deterministic replay), Codex (persistent thread state with server-side durability)

**Priority:** MEDIUM

**Recommendation:** Since sentinel-v2 already adds an event log, make state reconstructable from events. Add a `reconstruct_state_from_events()` function that can rebuild `orchestration-state.json` from `orchestration-events.jsonl`. The sentinel can call this on startup if state appears inconsistent (e.g., running change with no PID, or state mtime older than events mtime). This provides crash recovery without a full event-sourcing architecture.

---

### GAP 10: Dedicated Merge Agent / Tiered Conflict Resolution

**Description:** sentinel-v2 uses `wt-merge` for LLM-based conflict resolution, but the merge strategy is single-tier: try merge, if conflict use LLM resolution, if that fails queue for retry. Overstory uses a 4-tier conflict resolution system (fast-forward, auto-resolve, LLM resolve, human escalation). Multiclaude uses a dedicated merge agent that continuously polls and merges.

**Who does it:** Overstory (4-tier FIFO merge queue), Multiclaude (dedicated merge agent), Claude Code Agent Teams (file ownership boundaries)

**Priority:** LOW (current merge works, optimization is incremental)

**Recommendation:** Document the merge tier hierarchy explicitly in the merger module: Tier 1 = fast-forward (no conflict), Tier 2 = git auto-resolve (trivial conflicts), Tier 3 = LLM merge resolution (semantic conflicts), Tier 4 = human escalation (mark as needs-human-merge). The current code likely does Tiers 1-3 already but does not explicitly classify them, making debugging harder. Add tier classification to MERGE_ATTEMPT events.

---

### GAP 11: Plan Approval / Human-in-the-Loop Before Implementation

**Description:** Claude Code Agent Teams has a "require plan approval" mode where teammates plan in read-only mode, submit the plan for lead approval, and only begin implementation after approval. sentinel-v2's planner generates and validates a plan, but there is no structured plan-review step where the human can approve individual changes before dispatch begins.

**Who does it:** Claude Code Agent Teams (plan approval mode), Devin 2.0 (Ask and Plan modes), Cursor (plan mode in agent)

**Priority:** MEDIUM

**Recommendation:** Add a `plan_approval` directive (default: false). When true, after `cmd_plan()` generates the plan, the orchestrator enters a `plan_review` status. The user can view the plan (`set-orchestrate plan --show`), modify it (edit the JSON), and approve (`set-orchestrate approve`). Only after approval does `cmd_start()` proceed to dispatch. The current checkpoint/approve flow handles this partially but not at the plan stage.

---

## 3. Anti-Patterns to Avoid

### ANTI-PATTERN 1: Full Autonomy Without Structured Oversight (Devin 1.0)
Devin 1.0's fully autonomous cloud sandbox approach led to a 70% failure rate in real-world evaluations and developers feeling "sidelined from architectural decisions." sentinel-v2's checkpoint system and human-in-the-loop approval is the right approach. Do NOT remove checkpoints in favor of full autonomy.

### ANTI-PATTERN 2: Unbounded Agent Communication (Group Chat Orchestration)
Some frameworks use "group chat" patterns where all agents participate in a shared conversation. This causes token explosion and coordination overhead that scales quadratically. sentinel-v2 should keep agents isolated by default and only share targeted summaries, NOT full conversation histories.

### ANTI-PATTERN 3: Nested Agent Teams
Claude Code Agent Teams explicitly prohibits nested teams ("teammates cannot spawn their own teams"). Deep nesting creates unmanageable state trees and exponential token costs. sentinel-v2 should keep the flat orchestrator->agent hierarchy and NOT allow agents to spawn sub-orchestrations.

### ANTI-PATTERN 4: Aggressive Automatic Compaction
Codex has a known bug where agents get stuck in "compaction loops" -- endlessly compacting and re-reading files. Any context rescue mechanism should have a strict retry limit (max 1-2 compaction attempts per change) to avoid this trap.

### ANTI-PATTERN 5: CI-Only Quality Gates (Multiclaude)
Multiclaude's philosophy of "if CI passes, merge it" is too aggressive for production use. Tests can pass while code quality is poor, architectural patterns are violated, or cross-cutting concerns are missed. sentinel-v2's layered verification (test + review + smoke + project-knowledge rules) is the right approach.

### ANTI-PATTERN 6: Same-Model-For-All (Claude Agent Teams Current Limitation)
Claude Agent Teams currently requires all agents to run the same model (Opus 4.6). This is a known limitation the community wants fixed. sentinel-v2's per-change model routing is ahead of the curve here -- keep it.

---

## Summary Priority Matrix

| Priority | Gap | Effort |
|----------|-----|--------|
| HIGH | GAP 3: Per-change token budgets | Low (watchdog enhancement) |
| HIGH | GAP 4: Partial work salvage on failure | Low (add git diff capture) |
| HIGH | GAP 7: Agent Teams concrete hooks | Medium (interface design) |
| HIGH | GAP 1: Agent-to-agent communication | Medium (message bus) |
| MEDIUM | GAP 5: Quality gate hooks | Low (shell script hooks) |
| MEDIUM | GAP 6: Retry with backoff + jitter | Low (sentinel enhancement) |
| MEDIUM | GAP 9: Crash-safe state reconstruction | Medium (replay function) |
| MEDIUM | GAP 11: Plan approval before dispatch | Low (new status + gate) |
| MEDIUM | GAP 2: Context compaction rescue | Medium (re-dispatch logic) |
| LOW | GAP 8: Structured tracing (trace_id) | Low (schema addition) |
| LOW | GAP 10: Tiered merge classification | Low (event enrichment) |

The highest-value, lowest-effort additions are **per-change token budgets** (GAP 3) and **partial work salvage** (GAP 4). These address real production pain points with minimal implementation complexity. **Agent Teams hooks** (GAP 7) is strategically important given that the feature shipped in February 2026 and will likely exit experimental status soon.

---

Sources:
- [Claude Code Agent Teams Documentation](https://code.claude.com/docs/en/agent-teams)
- [Addy Osmani - Claude Code Swarms](https://addyosmani.com/blog/claude-code-agent-teams/)
- [Shipyard - Multi-agent orchestration for Claude Code](https://shipyard.build/blog/claude-code-multi-agent/)
- [OpenHands Software Agent SDK (arxiv)](https://arxiv.org/html/2511.03690v1)
- [OpenAI - Unrolling the Codex Agent Loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
- [OpenAI Compaction API Docs](https://developers.openai.com/api/docs/guides/compaction/)
- [OpenAI - Unlocking the Codex Harness](https://openai.com/index/unlocking-the-codex-harness/)
- [ZenML - Codex CLI Architecture](https://www.zenml.io/llmops-database/building-production-ready-ai-agents-openai-codex-cli-architecture-and-agent-loop-design)
- [Cognition - Devin's 2025 Performance Review](https://cognition.ai/blog/devin-annual-performance-review-2025)
- [Devin Agents 101](https://devin.ai/agents101)
- [Zylos - Long-Running AI Agents 2026](https://zylos.ai/research/2026-01-16-long-running-ai-agents)
- [Eunomia - Checkpoint/Restore Systems for AI Agents](https://eunomia.dev/blog/2025/05/11/checkpointrestore-systems-evolution-techniques-and-applications-in-ai-agents/)
- [Microsoft Azure - AI Agent Design Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [SparkCo - Mastering Retry Logic Agents 2025](https://sparkco.ai/blog/mastering-retry-logic-agents-a-deep-dive-into-2025-best-practices)
- [Apxml - Agent Resource Management](https://apxml.com/courses/multi-agent-llm-systems-design-implementation/chapter-4-advanced-orchestration-workflows/agent-resource-management)
- [Overstory - Multi-agent orchestration](https://github.com/jayminwest/overstory)
- [Cursor Background Agents](https://cursor.com/product)
- [Cursor Changelog 0.50](https://cursor.com/changelog/0-50)
- [n8n - AI Agent Orchestration Frameworks](https://blog.n8n.io/ai-agent-orchestration-frameworks/)
