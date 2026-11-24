[< Back to Index](../INDEX.md)

# From orchestration to harness

**Why set-core stopped being an orchestration engine, what it is now, and what came along.**
Written for v2.0.0 (2026-11). The earlier story — wt-tools, the Ralph loop, the orchestration
engine, the sentinel — is in [the development journey](journey.md), which ends in April 2026.

## The short version

set-core was built to take a markdown spec, decompose it into changes, run parallel agents in
git worktrees, gate each one and merge the result. That pipeline worked, and it is documented
and benchmarked. It is also **not what the author ended up using every day.**

What the daily work actually needed was a **harness**: the layer that lets one person run a
dozen or more hand-driven Claude Code sessions across many projects at once — see them all,
answer them from anywhere, keep them from leaking what they must not publish, carry their state
across a context reset, and let them talk to each other. That layer grew around the engine
between July and November 2026, and a usage audit in November made the split explicit:
**the harness was used daily; the engine had not run in 30 days.** v2.0.0 is the release that
says so.

## What changed in practice

Three things moved the work, in this order.

**1. The real projects were ahead of the framework.** From July the main track was connecting a
production client project to set-core. That project had a hand-run development lifecycle that
was more mature than set-core's own — release files, gate chains, a strict naming discipline.
The goal became to bring its further development *into* set-core without damaging what already
worked, which ruled out the engine's model ("give me a spec, I'll build it"). What the project
needed from the framework was visibility (bugs, releases, the test and the live system, on one
screen) and safety, not autonomy. The consumer status contract — a versioned command the
project exposes and set-core reads — came out of this, and it is domain-free: the project
supplies the data, set-core supplies the abstraction.

**2. The bottleneck was the human, not the agents.** With many sessions running in parallel, the
expensive moments were not "the agent writes code slowly". They were:

- a question or a permission prompt sitting in a terminal nobody was looking at;
- a session losing its precision through a context compaction while keeping its confidence;
- two sessions doing the same work, or one waiting on the other with no way to say so;
- an agent committing a client's name, a credential or a local path into a public repository;
- a deploy overwriting a file a project had edited by hand.

Each of those became a component: the **question and notification relay** (to the dashboard and to
a phone), the **auto-answer** that proposes replies from the session's own sources, **session
handoff and auto-clear** (`set-claude-handoff`), the **agent bus** (`set-agent-comm`),
**`set-leakscan`** at commit, push and agent-tool level, and a **provenance-guarded
`set-project` deploy** that never overwrites what a project owns.

**3. Measuring what is used.** In November a 30-day audit read every session transcript on the
machine, the settings of every registered project and the service logs (the full method is in
`openspec/changes/fleet-era-consolidation/design.md`). It found:

- **used daily:** the fleet dashboard and agent owner, the relay hooks, the wave board, knowledge
  search, the leak scan, `set-project`, the machine doctor, the provider tools, and the
  OpenSpec skills deployed into projects;
- **not used in 30 days:** the orchestration engine (~29k lines of core), its web pages, the
  sentinel, the git-based messaging path, **21 deployed `/set:*` slash commands with zero
  calls**, three hooks that ran on every turn in ~48 projects with nobody reading their output,
  and a 3.2k-line API module imported by nothing.

## What set-core is now

| part | what it does |
|---|---|
| fleet dashboard + agent owner | launch, watch, instruct and stop agent sessions across projects from one screen |
| relay hooks + auto-answer | questions, permission prompts and notifications reach the dashboard or a phone; a decider can propose and send answers from the session's own sources |
| `set-project` | deploys rules, skills, hooks and the MCP registration into a project — never overwriting what the project edited |
| project role rules | a generated, git-excluded rule per project naming its role and its relations |
| `set-kb` | knowledge-base search over a project's documents (CLI and MCP) |
| `set-leakscan` | commit, push and agent-tool gates against client names, credentials, local paths and private terms |
| `set-doctor` | the machine check, each finding with the command that fixes it |
| `set-watchdog` | probes the fleet for quiet failures during the day |
| providers | run the same sessions on a non-Anthropic model, explicitly, never as a silent fallback |
| wave board | a progress board a project publishes for the people it works with |
| OpenSpec | every framework change still goes proposal → specs → design → tasks → verify |

The companions are listed in [the repository family](../ecosystem.md).

## What was removed, and why

- **The memory subsystem** (removed 2026-08-22). Measured over 21 days: of 187 memory lines it
  injected into sessions, **168 were "user frustrated" records** — its detector fired on
  exclamation marks, so delight was stored and replayed as anger — and one line was a reusable
  fact. Claude Code's own per-project memory replaced it.
- **The knowledge-pack bridge, a dead API module, a stopped design-tool integration** — no
  callers.
- **The `/set:*` orchestration and git-messaging slash commands** — zero calls in 30 days; no
  longer deployed, and removed from projects on their next `set-project init` (only copies
  that were not edited locally). **This is the breaking change of v2.0.0.**

## What is dormant, not gone

The orchestration engine, its CLI and its web pages are still in the repository in v2.0.0. They
are **dormant**: nothing deploys their commands and nothing on the author's machine runs them.
They are retired in stages, each its own OpenSpec change with its own precondition —
`hook-diet`, `retire-orchestration-cli`, `retire-orchestration-engine` (after a week of
route-hit counts and a regression baseline), then `profile-layer-decision`. See the
[roadmap](../roadmap.md).

## What carried over from the engine

Not the pipeline, but what it taught:

- **OpenSpec as the unit of work** — framework changes still go through it; the engine's
  absence made the discipline matter more, not less.
- **Deterministic gates over judgement** — the leak scan, the deploy provenance check and the
  checkout guard are gates in the same sense the merge gates were: an instruction is not a
  constraint, so what an agent cannot do is decided by the tools it holds.
- **Evidence discipline** — a claim travels with the command that proves it. The rules in
  `.claude/rules/evidence-discipline.md` were written while debugging the engine and apply
  unchanged to the harness.
