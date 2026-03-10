# Why Is This Needed?

## The Problem

AI-powered code development tools — like Claude Code, Cursor, or GitHub Copilot — have revolutionized individual developer productivity. A developer in a single session can implement complex features within hours.

But what if the task is **not one feature**, but *twenty*?

A mid-size specification (e.g., the next version of a SaaS application) typically contains 10-30 independent development tasks. There are dependencies between them: authentication is needed for the profile page, the API is needed for the dashboard, migrations are needed for every database operation. Managing this manually:

- A feature is done → manually merge, manually test
- Merge conflicts → manually resolve, re-test
- An agent gets stuck → manually debug, context-switch, restart
- Specification changes → manually re-plan, re-prioritize
- Token budget runs out → manually monitor, restart session

All of this is **management overhead**: a significant portion of the developer's time goes not to coding but to pipeline coordination.

## The Solution: Autonomous Orchestration

`wt-orchestrate` automates this overhead. Starting from a single specification:

1. **Automatically plans** the tasks (decomposition, DAG)
2. **Executes them in parallel** in isolated worktrees
3. **Continuously monitors** the agents (15s poll, watchdog)
4. **Automatically tests and reviews** completed work (quality gates)
5. **Merges** the results (merge, conflict resolution)
6. **Continues** to the next phase (auto-replan)

This means that after handing off a specification, the system can work for *hours* without supervision, while the developer focuses on other tasks — or sleeps.

## Who Is This For?

This system is built for **individual developers and small teams** working with AI agents. It doesn't replace CI/CD (Jenkins, GitHub Actions) — it complements it, in the *development phase*, before code even reaches the CI pipeline.

Typical usage pattern:

```
Morning:   Hand off spec → wt-orchestrate plan → start
Daytime:   Other tasks, meetings, planning
Evening:   wt-orchestrate status → 12/15 changes merged, 2 running, 1 failed
           Review → approve → the rest continues
Next day:  Everything done, open PR
```

\begin{keypoint}
The goal is not that humans "aren't needed." The goal is that humans are needed where humans are irreplaceable: writing the specification, making design decisions, and final approvals — not babysitting the pipeline.
\end{keypoint}

## How Is This Different from CI/CD?

| Aspect | CI/CD (e.g., GitHub Actions) | wt-orchestrate |
|--------|------------------------------|----------------|
| **When it runs** | After commit/PR | *Before* commit — during development |
| **What it does** | Build, test, deploy | Planning, implementation, test, merge |
| **Who works** | Deterministic scripts | AI agents (creative, adaptive) |
| **Error handling** | Fail → red pipeline | Fail → retry, redispatch, escalate |
| **Parallelism** | Job matrix (fixed) | DAG-based, dynamic dispatch |
| **Feedback loop** | Human fixes, re-push | Agent fixes, re-tests |

The two complement each other: `wt-orchestrate` produces the code, the CI/CD pipeline validates and deploys it.
