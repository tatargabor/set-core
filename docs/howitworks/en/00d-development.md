# Development History

## Four Weeks from Specification to Autonomous Orchestration

`wt-tools` development started on February 10, 2026. In four weeks, the project grew from a simple worktree manager into a full autonomous orchestration framework. This chapter covers the key milestones and the arc of development.

## Week 1 — Foundations (Feb 10-16)

**Worktree management and agent supervision.**

The first week addressed the question "how do we run multiple Claude Code agents in parallel?" The answer: git worktrees — each agent works on its own branch, in its own directory, and merge happens at the end.

Completed:

- `wt-new` — worktree creation and initialization
- `wt-list`, `wt-status` — agent state tracking
- `wt-merge` — worktree merge to main
- `wt-close` — worktree cleanup
- `wt-loop` ("Ralph") — iterative agent cycle, automatic restart

The "Ralph loop" got its name during internal development: an agent that keeps taking another crack at the task until it's done — like a persistent colleague.

## Week 2 — Orchestration and OpenSpec (Feb 17-23)

**Automating manual coordination.**

In the second week it became clear that manual worktree management doesn't scale. If 10 features need parallel development, something is needed that:

- Plans the order (what depends on what)
- Starts the agents (dispatch)
- Monitors them (monitor)
- Merges the results (merge)

Completed:

- `wt-orchestrate` — the first version of the full orchestration pipeline
- Plan generation from brief → DAG → dispatch → monitor loop
- Topological sorting and parallel dispatch
- Checkpoint-based merge policy
- OpenSpec integration — structured proposal/design/tasks workflow

## Week 3 — Quality and Reliability (Feb 24 – Mar 2)

**From "works but sometimes breaks" to "reliable."**

The third week worked from lessons learned in live runs. The first production runs (sales-raketa project) revealed:

- Agents sometimes get stuck → **Watchdog system** (4-level escalation)
- Merges sometimes conflict → **LLM conflict resolution** (3-layer)
- Tests sometimes don't run → **Verify pipeline** (test → review → smoke)
- Token consumption sometimes explodes → **Budget control** (soft + hard limit)

Completed:

- Watchdog: stall detection, hash loop recognition, L1→L4 escalation
- Verify pipeline: test gate, code review gate, smoke test
- Token tracking: per-change + aggregate counters
- Email notification (Resend integration)
- `wt-sentinel` — the orchestrator's supervisor (crash recovery)

## Week 4 — Digest, Coverage, and Self-Healing (Mar 3-10)

**From task execution to specification comprehension.**

The fourth week brought the "professional" level: the system no longer just executes tasks but *understands* the specification.

Completed:

- **Spec digest pipeline** — structured processing of multi-file specifications, REQ-XXX identifiers
- **Ambiguity triage** — automatic detection of unclear points, human decision-making
- **Requirement coverage** — tracking whether every requirement is covered
- **Cascade failure** — if a dependency fails, dependent tasks also stop
- **Watchdog redispatch** — complete rebuild of stuck changes in fresh worktrees
- **Phase-end E2E** — Playwright tests at phase end, with screenshot gallery
- **HTML report generation** — detailed run summary, coverage matrix

## The Maturation

Development wasn't linear but exponential: each week built on the lessons of the previous one. In the first week, the system ran unsupervised for 5 minutes. By the fourth week, it could handle 5 hours — overnight, while sleeping, on production codebases.

```
Week 1: wt-new + wt-merge      → "manual multi-agent"
Week 2: orchestrate + plan      → "automatic coordination"
Week 3: watchdog + verify       → "reliable automation"
Week 4: digest + coverage       → "intelligent orchestration"
```

\begin{keypoint}
The most important lesson: an orchestration system's value is not in handling the "happy path" — anyone can do that. The value is in error handling, recovery, and escalation. 80\% of the system deals with what can go wrong.
\end{keypoint}
