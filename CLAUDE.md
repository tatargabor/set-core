
## ⚠ ACTIVE TRACK — highest priority while it is open

**The consumer ↔ set-core integration. Its living record is
[`docs/integration/consumer-integration.md`](docs/integration/consumer-integration.md).**
Read it before deciding what to do next, and **update it as part of the work, not after** —
a step that is done but unrecorded is indistinguishable from one that was never taken.
It holds what is shipped and verified, what is agreed with the consumer, the decisions
taken and why, and the ordered next steps. The goals and constraints below outrank it.

**The user has delegated the decisions on this track** (2026-07-24): decide from the
experience already on the record rather than escalating. That is a mandate to choose, not
to guess — a decision made this way names the evidence it rests on and goes in the living
record, so it can be revisited rather than merely inherited.

## The goal this work serves — do not lose this across a compact (2026-07-24)

The user has stated this twice, emphatically, because a context boundary is exactly where
an agreed goal quietly turns into whatever the current task happens to be. **The goals below
survive the compact; the task in flight does not outrank them.**

1. **Connect a consumer project and set-core so the link actually works.** This is the whole
   point of the cross-project coordination — the two copilot sessions talk to each other
   *for this*, not as an end in itself.
2. **Register in set-core what a project needs in order to be visible:** bugs, releases, the
   **test system**, the **live system**, settings, accesses, and the surrounding
   information. Today none of that reaches the framework.

   *Corrected 2026-07-24 after the consumer's side caught it:* this said "test environment"
   and "live environment", which is narrower than what was asked for and produces a
   different next step. An environment is a place — is it up, what is its URL. A **system**
   also covers whether its tests run, whether they are green, and when they last ran. The
   first was already satisfied; the second needs its own contract command and is not built.
3. **The project supplies the data; set-core supplies the abstraction.** The consumer exposes
   endpoints — a command speaking a versioned contract — and set-core's abstraction layer is
   extended to read them. The layer stays domain-free; the domain stays on the project side.
   The two sides design that extension **together, agreed on the channel**, not in parallel.
4. **The acceptance test is one sentence: open set-core and see the project's development
   status.** Not an API that returns correct JSON — a screen that shows where the project is.
5. **Then bring the manual OpenSpec-change operation back into set-core — but smartly.**
   First round: see everything in set-core, prepare a release, plan bug fixes, manage
   releases. Later round: development itself returns too, and the orchestration will
   need reshaping for it. That reshaping is expected, not a surprise to be avoided.

**Which way the learning flows — stated by the user on 2026-07-24, and it reverses the
usual assumption.** The consumer in this integration is their **flagship**: their newest and
most advanced client project, hand-developed, with an **SDLC far ahead of set-core's**.
set-core has not been developed for a while, and it is **set-core that has to catch up to the
mechanisms already working there** — not the other way around.

Three things follow, and none of them is optional:

- **Do not "correct" the consumer's process toward set-core's shape.** Its development
  foundation is proven and in daily use. The work is to bring that project's further
  development *into* set-core **without damaging that foundation** — extend it, never
  replace it. A design that requires the project to change how it works has failed, not
  the project.
- **Read their mechanism before designing ours.** When their side has already solved
  something (release YAMLs, gate chains, a contract shape, a naming discipline), the
  default is to adopt the shape, generalise it, and give it a home in the framework —
  after asking on the channel what it is actually for. Inventing a parallel mechanism
  because ours would be tidier is the failure mode to watch for.
- **Generalise, because this schema is meant to be reused.** The user wants the same
  pattern carried to other projects. So every piece of it lands as an abstraction with the
  domain on the project's side — which is also what the confidentiality boundary demands.
  If a design only works for one consumer, it is not finished.

**On the `set-factory` verdict, which this partly supersedes.** The user has asked for a
factory layer directly, so the 2026-07-19 "no" no longer settles the question — but read
what it actually rejected before treating this as a reversal, because most of it still
holds and the distinction is what keeps the work honest:

- **Still rejected, and nothing above asks for it:** a new repo or layer above set-core;
  the meetings→requirements pipeline (permanently out); set-core *executing* deployments.
- **The verdict's own finding, which the goals above are a direct continuation of:** the
  factory frame *is already* the set-core ↔ project split, the OpenSpec chain *is* one
  ADW, and the genuinely missing piece is a **router between differentiated ADWs**
  (chore / bug / feature / hotfix) — an extension of an existing router, not a new system.
- **The one real tension, and how it resolves:** the verdict said delegate release and
  promotion to the tools that already do them. The goal above is to *plan, prepare and
  manage* releases, which is not the same act as shipping them. set-core shows the state
  and helps decide; the project's own CI remains the only thing that deploys. Keep that
  line visible in whatever gets built — it is also the consumer's own iron rule.

**Standing constraint — NEVER deploy a consumer to production. Test environment at most.**
Stated by the user on 2026-07-24 and not time-limited. It binds every path, not just the
obvious one: not a direct deploy command, not a push to a branch whose CI promotes to
production, not a release-management action that ends in a production release, and not a
"just this once to verify the fix". If a piece of work would cause a production deploy as a
*consequence*, that counts and the answer is still no — ask the user instead. The framework
never executes deployments at all (see the factory-verdict note above); this constraint is
the narrower, operational one that also covers merely *triggering* someone else's pipeline.

**The safety track below is finished, and it is a precondition for this, not a substitute.**
Do not let it become the work again. And a shipped commit is not a running system — a
long-lived service holds the code it started with (`systemd ExecMainStartTimestamp`).

## Current Work State — read this first (updated 2026-07-24)

**The deploy is sealed. Every write path into a consumer tree is now guarded, and a live
first init has been run and verified.** The 2026-07-19 safety track is complete; do not
reopen it, and do not start new research on it.

**Shipped — the safety track, in order:**
- `8fae5733` — DB-mutation guard in `integration_pre_build`; no more
  `prisma db push --accept-data-loss` against a non-`file:` target.
- `d3769483` — `protected: true` across the web manifest.
- `eb7e2839` — the two remaining live-DB paths: a guard refusing config-supplied destructive
  commands against a non-`file:` target (`lib/set_orch/db_safety.py`, both post-merge paths),
  and dispatch re-running the project's `worktree-init` hook *after* `env_vars`, so the
  project's per-tree database name wins. They were a chain, not two bugs.
- `aed09d3c` — install-time hash ledger + tombstones (`set/.deploy-manifest.json`), covering
  BOTH deploy engines, and a `--dry-run` that finally reports the bash engine too.
- `a20aab1f` — ownership checks on the two mutation paths outside the engines.
- `a0334e19` — the `e2e_pre_gate` twin hole, and the gate reading a machine-readable result
  file keyed on `(file, title)` instead of scraping the Playwright list reporter. A measured
  consumer runs Playwright with `--reporter json`, so the old regex matched nothing and the
  gate read zero failures.
- `ae9706bb` — **`once: true`** separates scaffold from knowledge. 41 manifest entries are
  seeded once and never rewritten (all `rules/*.md`, which deploy un-prefixed into the
  project's own namespace, plus every scaffold file); 9 namespaced `framework-rules/`
  entries keep flowing. The split follows ownership, not file type.
- `f8f92ee3` — **git history as deletion intent.** On a first init the ledger is empty, so an
  absent path read as "new" and came back. Now a path absent from disk AND unknown to the
  ledger is checked against `git log --diff-filter=D`; a committed deletion is intent. Both
  engines, one scan per repository. Fails open (`None` = no information) so a new project
  still receives its templates. `SET_DEPLOY_IGNORE_GIT_HISTORY=1` opts out.
- `01701912` + `e2c818db` — **the fourth unguarded write path closed.** `_deploy_memory` no
  longer shells out to `set-memory-hooks remove`; that tool resolved its own target with
  `git rev-parse`, so a deploy into a non-repo-root walked UP and edited an ancestor
  repository, and it knew nothing about ownership. The in-process cleanup covers a superset
  of the same files through the ledger. Removing it exposed why nobody had noticed: the
  in-process migration matched zero blocks (its regex demanded a closing
  `<!-- /set-memory hooks -->` while the installer emitted `start`/`end`), so the unguarded
  external call had been doing the real work all along. A test now fails if the call
  returns.

**Superseded:** `0a′` (`--no-verify` on automated commits/pushes) is **withdrawn for pushes**.
Consumer gate chains commonly hang off the *pre-push* hook; bypassing it makes every one of
them skip silently. Commits may use `--no-verify`; pushes must never.

**Deploying to a consumer.** Run `set-project init --dry-run` first and read the plan — it is
honest about its own blast radius, including the bash engine. Then diff-check the consumer's
`.claude/`, hook config and gate scripts after the real run; an empty diff on hand-authored
files is the pass condition. Consumers no longer need to hand-maintain the `tombstones` list.

**Precision on "verified", so the next session does not over-trust this.** The live init that
produced a real ledger ran *before* the last four commits. What has been verified against a
consumer tree **since** is the dry-run: a sha256 snapshot of all 2477 files any deploy path
can reach, taken before and after, showed **zero bytes changed**, and the plan it printed
plans 0 overwrites and 0 new command/skill/rule/agent files. So the current code is proven not
to write in preview and proven to *intend* nothing destructive — but no real init has yet run
with `once: true`, git-history intent, and the removed external call all in place. The first
one that does is still worth watching.

## Cross-project agent channel — TEMPORARY (from 2026-07-24)

While set-core and a consumer project are being integrated, their two copilot sessions
coordinate over a **file channel**, because no shared transport exists: `.set-control` is
per-project (`mcp-server/set_mcp_server.py` resolves it under the project root), so the
MCP `send_message` / `get_inbox` pair cannot cross a project boundary. **Remove this
section once the real transport ships.**

**DECISION 2026-07-24 — do not revive the git-based control sync for this.** The existing
agent-messaging path (`set-control-sync`, `.set-control` worktree, ~15 s commit cycle) is
rejected as the cross-project channel: it caused problems in practice, and it carries
*ephemeral messages* where this coordination needs *durable state*. A live (non-git)
transport may be built later as its own piece of work; until then the file channel below is
the agreed mechanism.

**Protocol — one file, one writer.** Channel dir: `/tmp/<consumer-slug>-set/` (the slug is
runtime-derived; never hard-code a consumer name here — see External Project
Confidentiality below). Each side appends **only** to its own file and reads the other's:

| file | writer | reader |
|---|---|---|
| `set-core.md` | this project's session | the consumer's session |
| `<consumer-slug>.md` | the consumer's session | this project's session |
| `README.md` | whoever creates the channel | both |

- **Append-only**, newest last, each entry headed `## <ISO timestamp> — <TYPE>` where TYPE is
  one of `TÉNY` / `KÉRDÉS` / `VÁLASZ` / `KÉRÉS`. Answers cite what they answer (`re: …`).
- One writer per file means **no lock is needed** and no write can be lost. When a genuinely
  shared file must be edited (e.g. a planning doc in the consumer repo), take a POSIX-atomic
  lock first: `mkdir "$F.lock" || exit 1` with `trap 'rmdir "$F.lock"' EXIT`.
- Watch the other side with a Monitor on its file size — do not poll by hand.
- **A word like "measured" obliges you to show the evidence** — the command, its output, a
  `file:line`, a PID, a task id. Without one, the honest word is "assumption", and the other
  side must not write it into a rule book. This is not pedantry: a plausible guess crossed
  this bus, was reasonably taken for a measurement, and ended up in BOTH projects' rules
  before anyone ran the one-line check that disproved it. On an agent channel a confident
  claim propagates further and faster than an ordinary mistake, because the receiving side
  has every reason to trust it.
- The channel is `/tmp`, i.e. session-lived. Anything durable belongs in a repo.

**Resuming the channel after a compact, a `/clear`, or a fresh session.** The channel is the
only thing that survives — rebuild the contact from it, do not ask the user to re-explain:

1. **Find it:** `ls -dt /tmp/*-set/ 2>/dev/null | head` — the channel dir is the newest match.
   Read its `README.md` first; it carries the protocol and the addressing convention.
2. **Catch up:** read the OTHER side's file end-to-end (`<consumer-slug>.md`), then your own
   (`set-core.md`) to see what you already answered. Entries are timestamped and append-only,
   so the tail is the current state.
3. **Check both watches, then re-arm only what is missing.** A dead watch is
   indistinguishable from a quiet peer, so the work stops without anyone noticing — but
   blindly re-arming is its own bug: a duplicate fires the same catch-up twice, and two
   Monitors on one file send two notifications for every entry. **`CronList` first**, and
   look for a live Monitor process before starting one.

   **Both survive a compact** — verified on this machine, not assumed: a `persistent: true`
   Monitor started at 08:19 was still the same live PID hours later, across the compact
   that produced this session's summary (`ps -eo pid,lstart,cmd | grep <watched file>`).
   An earlier version of this section claimed the Monitor does not survive; that claim was
   a guess that travelled between two sessions and got written into both rule books before
   anyone ran the check.
   - a **Monitor** on the other side's file size (`persistent: true`) — how you learn about
     new entries without polling by hand. It is a real background process; `ps` is the
     evidence, and it outlives a compact.
   - a **CronCreate** catch-up every ~10 minutes as the fallback for when the Monitor does
     die. Its prompt: read the last peer entry, check whether you have already answered it,
     do the work and reply if not, restart the Monitor if it is gone, and **say nothing at
     all when there is nothing to do** — a fallback that chatters gets muted. Pick a period
     that does not coincide with the peer's (they run one too); cron jobs are session-only
     and expire after 7 days.
4. **Announce the resume** in your own file: one `TÉNY` entry saying the context restarted and
   which entry number you have read up to, so the other side knows nothing was lost.
5. **The durable agreements are not in /tmp.** The negotiated contract lives in the consumer's
   planning document (the channel's entries point at it) — read that before answering anything
   substantive, and never re-open a decision it already records.

**Addressing convention (spoken sessions).** When both copilots listen to the same
microphone, the speaker names the addressee **first in the sentence** — a turn opening with
this project's name (`set-core`, or its spoken variants) is for this session; a turn opening
with the other project's slug is not, and this session stays silent on it. An unaddressed
turn is for whoever it is actually useful to. Getting this wrong is what makes two copilots
talk over each other.

**Discipline.** Between 2026-07-14 and Phase 0′ this repo produced five research documents and zero lines of code while a six-line guard stood between an orchestration run and a production-data mirror. Research is not the default next step — shipping the listed items is. Before proposing a new investigation, check whether it is already answered in `docs/research/`.

**Partly superseded — see the goals section at the top of this file.** The 2026-07-19
verdict (`docs/research/set-factory-verdict-2026-07-19.md`) still governs three things and
they are not open: no new repo or layer above set-core, the meetings→requirements pipeline
is permanently excluded, and set-core never *executes* a deployment. What the user has since
asked for — seeing project status in set-core, and planning/preparing/managing releases —
sits outside those three, and the verdict's own finding (the missing piece is a router
between differentiated ADWs) is what it continues.

**Known unrelated debt:** measured on a pristine checkout of `HEAD` (2026-07-24): **94 failed /
2631 passed / 21 errors**. The earlier "17 failed" note in this file was stale and understated
it by ~77, and the failures are not confined to `test_web_api_write.py` +
`test_web_integration.py`. Pre-existing and outside the current track — but do not treat a
green-except-94 run as a regression signal without diffing the failure set.

## External Project Confidentiality

**NEVER reference external/private consumer projects by name** in set-core code, comments, commit messages, specs, rules, templates, or documentation. When adopting lessons, patterns, or fixes from consumer projects (E2E runs, harvest, diagnostics), always generalize — describe the pattern, not the source. Consumer project names are private and must not leak into the framework codebase.

**The boundary is persistence, not naming.** set-core may read and display a consumer's data
at runtime — that is the whole point of the abstraction — but it must **persist nothing
derived from it**: not into this repo, not into a committed artifact, and not into any cache,
log, or debug dump that can leave the machine. The interface stays domain-free (`bugs()`,
`changes()`, `releases()`), while what it reads is full of domain: partner names, order
numbers, reporter email addresses, client process descriptions, business rules quoted in
review findings.

Two carriers cross this line without anyone deciding to:
- **The memory system.** Session-end extraction saves insights automatically. A memory written
  while working on consumer data can capture that data verbatim. Generalize before saving —
  describe the pattern, never the instance — and treat a memory naming a consumer entity as a
  defect to `set-memory forget`, not as harmless.
- **Diagnostic output.** Error paths that dump a record, a URL, or a row to aid debugging.
  Log the shape, not the content: `db_safety.py` logs a URL's scheme and nothing else, which
  is the pattern to copy.

## Persistent Memory
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

This project uses persistent memory (shodh-memory) across sessions. Memory context is automatically injected into `<system-reminder>` tags in your conversation — **you MUST read and use this context**.

**IMPORTANT — On EVERY prompt, follow these steps:**
1. **Scan** `<system-reminder>` tags for "PROJECT MEMORY", "PROJECT CONTEXT", or "MEMORY: Context for this command"
2. **Match** — check if any injected memory directly answers the user's question or provides a known fix
3. **Cite** — if a match is found, use it: "From memory: ..." — do NOT re-investigate problems with known solutions in memory
4. **Proceed** — only after checking memory context, do independent research

**This applies to every turn, not just the first one.**

**How it works:**
- Session start → relevant memories loaded as system-reminder
- Every prompt → topic-based recall injected as system-reminder
- After Read/Bash → relevant past experience injected as system-reminder
- Tool errors → past fixes surfaced automatically
- Session end → raw conversation filter extracts and saves insights

**Active (MCP tools):** You also have MCP memory tools available (`remember`, `recall`, `proactive_context`, etc.) for deeper memory interactions when automatic context isn't enough.

**Emphasis (use sparingly):**
- `echo "<insight>" | set-memory remember --type <Decision|Learning|Context> --tags source:user,<topic>` — mark something as HIGH IMPORTANCE
- `set-memory forget <id>` — suppress or correct a wrong memory
- Most things are remembered automatically. Only use `remember` for emphasis.

### Memory Safety During Verification
Memory is a hypothesis, not a verdict. During `/opsx:verify`, always check the filesystem (Glob, Grep, Read) — never skip checks because memory suggests "known false positive" or "same pattern." Memory is not branch/worktree-aware.

## Help & Documentation

When the user asks how a feature works or needs help with set-core:
- **General overview or "what can I do?"**: use `/set:help` (quick reference for all commands, skills, MCP tools)
- **CLI tools** (set-new, set-memory, etc.): run `set-<tool> --help`
- **Skills** (/opsx:*, /set:*): read `.claude/skills/openspec-*/SKILL.md` or `.claude/skills/set/SKILL.md`
- **Memory system**: read `docs/developer-memory.md`
- **Agent messaging / team sync**: read `docs/team-sync.md`

## Auto-Commit After Apply
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

After a skill-driven apply (e.g. `/opsx:apply`) finishes or pauses, automatically commit all changes. Follow the standard commit flow (stage relevant files, write a concise commit message).

## Consumer Project Diagnostics

set-core is developed and battle-tested through consumer projects. Before fixing bugs or adding features, always consult the primary consumer for real-world diagnostics.

### Harvest (primary tool)

After every E2E run, use `set-harvest` to scan consumer projects for framework-relevant fixes:
```bash
set-harvest                          # scan all registered consumer projects
set-harvest --project craftbrew-run-20260320-1445 # scan single project
set-harvest --dry-run                # preview without updating state
```

The harvest tool scans ISS fix commits, classifies them (framework-relevant vs project-specific), and presents them for interactive adoption into planning rules, templates, or core code.

### Manual workflow

1. **Read the latest orchestration run log** — each log has a "set-core Bugs to Report" section and "Conclusions for set-core Development" with prioritized issues, root cause analysis, and design decisions.
2. **Diff .claude/ for upstream changes** — during orchestration, the sentinel or user may improve commands, skills, or configs in the consumer's `.claude/`. Diff against set-core source to find changes to adopt.
3. **Check orchestration.yaml** — the consumer's config reflects production usage. Understand what directives are actually used before changing defaults.
4. **Use run comparison data** — run logs contain quantitative comparisons (wasted iterations, token efficiency, intervention count). Use these to validate whether a fix actually improved things.

### Bidirectional flow

```
set-core (source)                     consumer project
   │                                      │
   ├── set-project init ──────────────────►│  deploy .claude/ files
   │                                      │
   │◄── run logs (bugs, design) ──────────┤  diagnostics after each run
   │◄── .claude/ diffs ──────────────────┤  sentinel/user improvements
   │◄── orchestration.yaml ──────────────┤  config evolution
   │                                      │
   ├── fix bugs, add features             │
   ├── set-project init ──────────────────►│  redeploy
```

## E2E Run Setup

**Read `tests/e2e/README.md` first** — it documents scaffolds, fallback logic, and runner internals.

**NEVER** initialize E2E runs manually. Always use `tests/e2e/runners/`:
```bash
./tests/e2e/runners/run-micro-web.sh     # scaffold + init + register
./tests/e2e/runners/run-minishop.sh      # scaffold + init + register
./tests/e2e/runners/run-craftbrew.sh     # scaffold + init + register
```

If you MUST init manually, **always** include `--project-type web --template nextjs`:
```bash
set-project init --name minishop-run-YYYYMMDD-HHMM --project-type web --template nextjs
```
Without `--project-type web`, no `project-type.yaml` is created → NullProfile loads → integration gates silently skip (no build/test/e2e detection).

### Starting the sentinel

After the runner script finishes, start the sentinel via the **manager API** (not CLI):
```bash
# Restart set-web first if the project was just registered (picks up new projects)
systemctl --user restart set-web && sleep 5

# Start sentinel via API
curl -X POST http://localhost:7400/api/<project>/sentinel/start \
  -H 'Content-Type: application/json' -d '{"spec":"docs/spec.md"}'
```

**NEVER** use `nohup set-sentinel` from CLI — that only starts the orchestrator without the sentinel poll loop.

### Comparing runs for divergence

After two runs of the same spec, compare their structural similarity:
```bash
./bin/set-compare minishop-run-20260315-0930 minishop-run-20260318-1415          # markdown report
./bin/set-compare micro-web-run-20260322-1100 micro-web-run-20260325-0845 --json # JSON output
./bin/set-compare run-a run-b --output docs/comparison.md # save to file
```

Metrics: route coverage, schema equivalence, dependencies, functional categories, template compliance, convention compliance, E2E test results. Score 0-100 with verdict.

## Web Dashboard E2E Tests

The web dashboard (`web/`) has Playwright E2E tests that verify the UI renders API data correctly. Tests run against a **live server** with a **real project** — no mocks.

### Running

```bash
cd web/

# Prerequisites: set-orch-core running, project with completed orchestration
E2E_PROJECT=minishop-run-20260315-0930 pnpm test:e2e

# View HTML report (screenshots on failure, step-by-step trace)
pnpm test:e2e:report

# Single test file
E2E_PROJECT=minishop-run-20260315-0930 npx playwright test changes-data

# Debug with visible browser
E2E_PROJECT=minishop-run-20260315-0930 npx playwright test --headed
```

### What they test

Gate icons, token values, status colors, session counts, duration calculation, phase grouping, chart rendering, log display, tab navigation, action buttons — every tab of the dashboard. Tests fetch API data first, then assert the UI matches. See `web/tests/e2e/README.md` for details.

### After refactoring the web UI

Always run the E2E suite to verify nothing broke. The HTML report (`pnpm test:e2e:report`) shows exactly which assertions failed with screenshots.

## Compact Instructions

When compacting context, always preserve:
- Current OpenSpec change name and task progress (e.g., "working on modernize-claude-config, 15/30 tasks done")
- List of files modified in this session
- Active worktree path (if working in a worktree)
- Test commands and their last pass/fail results
- Any unresolved errors or blockers
- The cross-project channel dir (if one is active) and the last entry read on each side — see
  the temporary cross-project agent channel section above
- **That the channel watches must be CHECKED after the compact, not re-armed on reflex.**
  Both the Monitor and the cron survive it (verified), so an unconditional re-arm produces
  duplicates — two notifications per entry, two answers to one question. Nothing reports a
  watch's death either, and a peer waiting on an answer looks exactly like a peer with
  nothing to say: `CronList` + `ps` for the Monitor, then fill only the real gap.

## Getting Started
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

See [START.md](START.md) for application startup commands (install, dev server, database, tests).
