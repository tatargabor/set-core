---
marp: true
theme: default
paginate: false
backgroundColor: #0f172a
color: #e2e8f0
size: 16:9
style: |
  section {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    background-color: #0f172a;
    color: #e2e8f0;
    padding: 40px 80px;
  }
  h1 {
    color: #38bdf8;
    font-size: 2.4em;
    border: none;
    margin-bottom: 0.3em;
  }
  h2 {
    color: #7dd3fc;
    font-size: 1.5em;
    margin-bottom: 0.4em;
  }
  strong { color: #fbbf24; }
  em { color: #94a3b8; font-style: normal; }
  code {
    background: #1e293b;
    color: #a5f3fc;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.9em;
  }
  blockquote {
    border-left: 4px solid #fbbf24;
    background: #1e293b;
    padding: 12px 20px;
    border-radius: 0 8px 8px 0;
    margin: 16px 0;
    font-size: 0.95em;
  }
  blockquote p { margin: 0; }
  table {
    font-size: 0.8em;
    width: 100%;
    margin-top: 12px;
  }
  table th {
    background: #1e3a5f;
    color: #7dd3fc;
    padding: 8px 12px;
    font-weight: 600;
  }
  table td {
    background: #1e293b;
    border-color: #334155;
    padding: 8px 12px;
  }
  img {
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  }
  section.cover {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 60px;
  }
  section.cover h1 {
    font-size: 4em;
    color: #22c55e;
    letter-spacing: 0.08em;
    margin-bottom: 0.1em;
  }
  section.cover p {
    max-width: 700px;
  }
  section.divider {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
  }
  section.divider h1 {
    font-size: 2.8em;
    border: none;
    margin-bottom: 0.2em;
  }
  .metric {
    display: inline-block;
    text-align: center;
    margin: 0 24px;
  }
  .metric .val {
    font-size: 2.8em;
    font-weight: 800;
    color: #22c55e;
    line-height: 1;
  }
  .metric .label {
    font-size: 0.75em;
    color: #6b7280;
    margin-top: 4px;
  }
---

<!-- _class: cover -->

# SET

**Autonomous multi-agent orchestration for Claude Code**

Give it a spec. Get merged features.
*Greenfield or brownfield. Full app or single module.*

<!-- SPEAKER_NOTES:
SET takes a markdown specification and uses parallel AI agents to build
working applications. Today: intro to the system, then live demo.
-->

---

# The problem with AI coding today

<br>

> **Same prompt, different result.** Run it twice, get two different applications.
> Agents hallucinate features, skip requirements, and forget everything between sessions.

<br>

We tried "just prompting" agents to build apps. Results:

- 3 agents chose **3 different table libraries** for the same spec
- Cart feature shipped **without price calculation** (no one asked for it explicitly)
- LLM code review **let through a `TODO: implement later`** that broke checkout
- 15+ agent sessions, **zero voluntary memory saves** -- they never learn

<br>

**SET exists because prompting isn't engineering.**

<!-- SPEAKER_NOTES:
These are real examples from our first CraftBrew and MiniShop runs.
Not theoretical -- this is what happens when you give agents freedom
without structure, verification, or memory.
-->

---

# Six pillars -- what makes it work

![w:1100](diagrams/01-six-pillars.png)

<br>

| Pillar | In one sentence |
|--------|----------------|
| **SPECIFY** | Structured input with requirements + acceptance criteria, not vague prompts |
| **DECOMPOSE** | Intelligent planning into parallel changes with dependency DAG |
| **EXECUTE** | Iterative implementation in isolated git worktrees, not single-shot prompts |
| **SUPERVISE** | Three-tier supervision (sentinel > orchestrator > agents), 30s crash recovery |
| **VERIFY** | 7 deterministic gates -- exit codes, not LLM vibes |
| **LEARN** | Every run improves the next -- templates, memory hooks, cross-run learnings |

<!-- SPEAKER_NOTES:
These six pillars are the mental model. Every feature maps to one of these.
Each was born from a real failure that cost hours of compute.
-->

---

# The pipeline

![w:1100](diagrams/03-pipeline.png)

<br>

**spec.md** is the input. The system digests it into requirements, decomposes into
independent changes, dispatches parallel agents, verifies each through 7 gates,
merges to main, and replans if coverage is under 100%.

**Fully autonomous.** The sentinel supervises everything -- crashes, stalls, budget.

<!-- SPEAKER_NOTES:
This is the full pipeline. Each stage is automatic. The sentinel is the
autonomous supervisor that handles infrastructure-level problems.
If something fails, the system diagnoses before it retries.
-->

---

# What it builds -- MiniShop

![w:520](../images/auto/app/products.png) ![w:520](../images/auto/app/admin-dashboard.png)

A complete **Next.js e-commerce app** -- product listing, cart, checkout, admin CRUD,
auth, seeded database. Built from a markdown spec + Figma design.

**6 changes | 1h 45m | 0 human interventions | 70 tests | 100% spec coverage**

<!-- SPEAKER_NOTES:
This is the hero result. Not scaffolding -- a working application with
real data, functional navigation, responsive layout. The agents wrote
38 Jest tests and 32 Playwright E2E tests as part of the implementation.
-->

---

# The numbers

<br>

<div style="text-align:center; margin: 20px 0;">
<span class="metric"><span class="val">6/6</span><br><span class="label">changes merged</span></span>
<span class="metric"><span class="val">1h 45m</span><br><span class="label">wall clock</span></span>
<span class="metric"><span class="val">0</span><br><span class="label">interventions</span></span>
<span class="metric"><span class="val">70</span><br><span class="label">tests written</span></span>
<span class="metric"><span class="val">2.7M</span><br><span class="label">tokens total</span></span>
</div>

<br>

| What | How |
|------|-----|
| **5 gate failures** | All self-healed -- agent reads error, fixes, re-runs gate |
| **83-87% convergence** | Run same spec twice, measure structural overlap |
| **100% schema match** | Data model is fully deterministic across runs |
| **26:1 cache ratio** | Prompt caching cuts actual cost dramatically |

<br>

> Roughly equivalent to **a day's work by 3-4 senior developers**.

---

# Self-healing -- it doesn't retry, it investigates

![w:1100](diagrams/07-self-healing.png)

<br>

Real example from MiniShop: Playwright auth test expected redirect to `/login`,
but middleware redirected to `/admin/login`. The gate caught it, the agent
read the error, traced the middleware, updated 3 test files. No human involved.

**The system fixed a bug in SET's own code during an E2E run** -- and committed the fix
so it never happens again.

---

# Works everywhere

<br>

| | **Greenfield** | **Brownfield** | **Isolated unit** |
|---|---|---|---|
| **What** | Full app from spec + design | Your existing codebase | One module, one feature |
| **Example** | MiniShop: 6/6 merged, 1h 45m | SET builds itself: 1,500+ commits | "Add 3 API endpoints with auth" |
| **Pipeline** | 6-15 parallel changes | Same gates, reads existing code | Single change, full verification |

<br>

**The entry barrier is not a 30-page spec.** It can be a single task description.
The pipeline scales from a sentence to a specification.

> SET itself is built with SET -- 376 specs, every commit through the same pipeline.

---

# Scale -- from simple to complex

<br>

| | **micro-web** | **MiniShop** | **CraftBrew** |
|---|---|---|---|
| **Complexity** | 4 pages | E-commerce with admin | Multi-tenant, 28 DB tables |
| **Changes** | 3 | 6 | 15 |
| **Wall time** | ~20 min | 1h 45m | ~6h |
| **Tokens** | ~50K | 2.7M | ~11M |
| **Merge conflicts** | 0 | 0 | 4 (auto-resolved) |
| **Result** | 100% | 100% | 100% (run #7) |

<br>

**1,500+ commits | 134K LOC | 376 specs | 100+ E2E runs**

Built and used in production.

---

<!-- _class: divider -->

# Live demo

*Dashboard | Scaffolds | Pipeline in action*

<!-- SPEAKER_NOTES:
Now switch to the browser. Open http://localhost:7400.
Show the dashboard with a completed run.
Walk through: Changes tab, Phases, Tokens, Sessions, Sentinel.
Then show a scaffold: the micro-web spec, the generated code, the tests.
If time: start a fresh micro-web run and watch it live.
-->
