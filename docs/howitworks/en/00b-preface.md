# Preface

In the early 2000s, I worked in Hungary as part of a Nokia subcontractor team. We built SMS gateways and similar telecommunications infrastructure — the big infrastructure projects of that era, where reliability wasn't optional but a baseline requirement. Millions of users' messages flowed through our servers, and every minute of downtime had a measurable cost.

That's where I learned what *systems-level thinking* means: it's not enough for a single component to work — the entire pipeline needs to work, end-to-end, day and night, without human intervention. In Nokia's engineering culture, every system had monitoring, a watchdog, and an escalation plan. When something stopped, a human didn't go look at it first — the system tried to fix itself.

This mindset resurfaced twenty years later, in a completely different technological context.

---

`wt-orchestrate` solves the same problem I learned about in Nokia infrastructure: how to run *autonomous, multi-step pipelines* where the system handles errors on its own, escalates on its own, and only asks a human when it truly has to.

The difference: here it's not SMS messages flowing through the pipeline, but *software development tasks*. The "agent" isn't a hardware node but a Claude Code session in a git worktree. The "watchdog" doesn't monitor hardware heartbeats but the iteration hash of `loop-state.json`. But the pattern is the same:

- **Dispatch** → **Monitor** → **Detect failure** → **Escalate** → **Recover or fail gracefully**

This documentation walks through this pipeline, from input to final merge.

\begin{keypoint}
This is not a theoretical document. Every feature described here has been tested and developed on real production projects — wt-orchestrate runs daily on production codebases, autonomously, for hours, without human intervention.
\end{keypoint}
