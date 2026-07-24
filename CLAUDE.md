
## Current Work State — read this first (updated 2026-07-19)

**Active track: the safety trio in `docs/research/final-plan-2026-07-19.md` §0.** Start there, not with new research.

**Shipped:** Phase 0′ — the DB-mutation guard in `integration_pre_build` (`modules/web/set_project_web/project_type.py`), commit `8fae5733`, with mutation-checked tests in `tests/unit/test_integration_pre_build_db_guard.py`. set-core no longer authors `prisma db push --accept-data-loss` against a non-`file:` target.

**Next, in this order** (all small, none architectural):
1. **0′b** — the twin `e2e_pre_gate` has the same class of hole: its guard reads the `.env` FILE while the push runs with the `env` PARAMETER, and it never fires when `DATABASE_URL` is absent. ~4 lines + test.
2. **0a** — `protected: true` flags in the web deploy manifest. **This is the gate on everything else** (see decision below).
3. **0a′** — `--no-verify` on automated worktree commits/pushes.
4. **0b** — e2e gate reads a machine-readable result file keyed on `(file, title)` instead of scraping the Playwright list reporter.

**DECISION — do NOT run `set-project init` against the live consumer project until 0a ships.** Today an `init --force` clobbers un-prefixed consumer files (i18n catalogs, the e2e global-setup, 16 hand-authored rules). This is a **gated hold**: the gate is the four items above, then re-evaluate.

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
- The channel is `/tmp`, i.e. session-lived. Anything durable belongs in a repo.

**Resuming the channel after a compact, a `/clear`, or a fresh session.** The channel is the
only thing that survives — rebuild the contact from it, do not ask the user to re-explain:

1. **Find it:** `ls -dt /tmp/*-set/ 2>/dev/null | head` — the channel dir is the newest match.
   Read its `README.md` first; it carries the protocol and the addressing convention.
2. **Catch up:** read the OTHER side's file end-to-end (`<consumer-slug>.md`), then your own
   (`set-core.md`) to see what you already answered. Entries are timestamped and append-only,
   so the tail is the current state.
3. **Re-arm the watch:** start a Monitor on the other side's file size — it is how you learn
   about new entries without polling by hand.
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

**Verdict already reached — do not relitigate:** no `set-factory` layer (`docs/research/set-factory-verdict-2026-07-19.md`). The meetings→requirements pipeline is permanently excluded from the framework. Deployment execution, promotion state machines and portfolio scheduling are out of scope.

**Known unrelated debt:** 17 failed / 21 errors in `test_web_api_write.py` + `test_web_integration.py` (`AttributeError` in web API fixtures) — pre-existing, untouched.

## External Project Confidentiality

**NEVER reference external/private consumer projects by name** in set-core code, comments, commit messages, specs, rules, templates, or documentation. When adopting lessons, patterns, or fixes from consumer projects (E2E runs, harvest, diagnostics), always generalize — describe the pattern, not the source. Consumer project names are private and must not leak into the framework codebase.

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

## Getting Started
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

See [START.md](START.md) for application startup commands (install, dev server, database, tests).
