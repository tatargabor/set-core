
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

**Write it down BEFORE the context ends, and read it back after** (user, 2026-07-24). The
danger on this track is not forgetting — it is **compounding**: every hop through a compact,
through the agent channel, or through a scratch file that evaporates loses precision while
keeping confidence, so a diluted claim gets built on as if it were the measurement. Three
consequences, all binding:

- **Record at the moment of the decision or the measurement**, not at the end of the step.
- **On resuming, re-check rather than re-derive** — every claim in the living record names
  how it was verified, and re-running that check costs seconds.
- **A summary is not a source.** When your recollection and the living record disagree, the
  record wins unless you can produce evidence — and then you fix the record immediately.

What counts as knowing something — the defect classes that keep recurring here, and how to
prove a fix is a fix — is in
[`.claude/rules/evidence-discipline.md`](.claude/rules/evidence-discipline.md).

## The goal this work serves — do not lose this across a compact (2026-07-24)

The user has stated this twice, emphatically, because a context boundary is exactly where
an agreed goal quietly turns into whatever the current task happens to be. **The goals below
survive the compact; the task in flight does not outrank them.**

1. **Connect a consumer project and set-core so the link actually works.** This is the whole
   point of the cross-project coordination — the two copilot sessions talk to each other
   *for this*, not as an end in itself.
2. **Register in set-core what a project needs in order to be visible:** bugs, releases, the
   **test system**, the **live system**, settings, accesses, and the surrounding
   information. **MET as of 2026-07-24** — all of it reaches the framework now; see items
   1–3d of "Next, in order" in the living record for what each one cost.

   *Corrected 2026-07-24 after the consumer's side caught it:* this said "test environment"
   and "live environment", which is narrower than what was asked for and produces a
   different next step. An environment is a place — is it up, what is its URL. A **system**
   also covers whether its tests run, whether they are green, and when they last ran.

   *Corrected again the same day, because this paragraph was stale in the direction that
   causes wasted work:* it said the second "needs its own contract command and is not
   built", and a session reading only this file would have gone off to build one. Both are
   done — the test system through a `commitsSince`-carrying answer that deliberately has no
   `ok` field, the live system through a separate `health` command — and **neither cost the
   framework a single change**, which is the seventh time the declaration-driven design has
   held. Goal 2 is a closed item; goal 5 is the open one.
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

**Corrected 2026-07-24 — "every write path" was counted in files, and one of them was not a
file.** A fifth path existed and is now closed (`9ab3e6b6`): a dependency install run with
`cwd` set to a WORKTREE. A worktree shares one `.git`, so a `prepare` script that installs
git hooks rewrites the **host** repository's hook wiring with a path inside the worktree —
and orchestration then deletes the worktree. Nothing on disk points back at the cause; hook
managers gitignore their own directory so `git status` stays clean; and a hook that cannot
run does not error, it just stops enforcing. It was found on a real repository ten days
later, by the consumer, while looking for something else.

Two lessons outrank the fix. **A completeness claim is a measurement, not a summary** — the
sealed statement above was true of everything that had been enumerated, which is not the
same as everything that exists, and it read as the latter for five days. And **the guard
belongs where the effect is, not where the alarming word is**: no hook installer is called
anywhere in this repo, and it did not need to be.

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

## "comm" means `set-agent-comm` (`sac`) — stated by the user, 2026-08-19

**When anything in this project says *comm*, *messaging*, or *the bus*, the default subject is
[`set-agent-comm`](https://github.com/tatargabor/set-agent-comm) (`sac`, `~/code2/set-agent-comm`)
— the newer external system, and the good one.** Written down because a session got it wrong in
exactly the way that costs a decision: it read a review finding's "framework bus" column as the
**git-based** `/set:msg` path and merged that path's measurement into `sac`'s, which made a
working system look dead.

The three things are separate and only one of them is *comm*:

| | what it is | measured state |
|---|---|---|
| **`sac`** — THIS is comm | file channel + registry, rooms, typed messages, declared focus, appending writes, and it solved waking an idle session | 2026-08-19: **2 of 4** live agents reachable — see the enrolment note below |
| `/set:msg`, `/set:inbox`, `/set:broadcast`, MCP `send_message`/`get_inbox` | the **older git-based** path through a `.set-control` worktree | 2026-08-19: **0 of 39** registered projects have that worktree, so these error everywhere. Do not build on it; do not quote its numbers as comm's. |
| the runtime's own cross-session socket | Claude Code's native channel, `/run/user/1000/cc-socks/<pid>.sock` | reaches every live session because a session does not opt into existing |

**Why `sac`'s coverage is not a defect, and what follows from it — the user's answer, 2026-08-19:**
`sac` knows an agent that **enrolled a seat**; it cannot message one that has not. That is not a
gap to route around with a second channel — **enrolling an agent is its own module**, and the way
to 4-of-4 is to enrol, not to keep two transports alive forever. So a surface that finds an
unreachable agent offers *enrolment*, never a parallel path.

**And the older path's number must not be borrowed.** `0/39` is a fact about the git-based
worktree bus. Stating it about "comm" describes a working system as a dead one — the same
defect class as measuring a proxy instead of the thing, with the fail direction that abandons
something that works.

## Cross-project agent channel — TEMPORARY (from 2026-07-24)

While set-core and a consumer project are being integrated, their two copilot sessions
coordinate over a **file channel**, because no shared transport exists. **Remove this
section once the real transport ships.**

*Corrected 2026-07-29 — the stated reason was wrong, and wrong in the direction that closes
off a working option.* This said `.set-control` is per-project, so `send_message`/`get_inbox`
"cannot cross a project boundary". Measured: the registry is **global**
(`~/.config/set-core/projects.json`, 38 entries), and `_find_control_worktree()`
(`mcp-server/set_mcp_server.py:462`) walks it and returns the **first** project that has a
`.set-control` directory — regardless of which project the server was started in. So both
sides would resolve to the *same* worktree; the project boundary was never the obstacle. The
real ones are that **no `.set-control` exists anywhere** (checked on both trees → both tools
return `Error: No .set-control worktree found`), and that the git-based ~15 s commit cycle is
rejected below. This is the proxy-instead-of-the-thing class applied to a code path: the
sentence described what the resolution *ought* to scope to, not what the function does.

**DECISION 2026-07-24 — do not revive the git-based control sync for this.** The existing
agent-messaging path (`set-control-sync`, `.set-control` worktree, ~15 s commit cycle) is
rejected as the cross-project channel: it caused problems in practice, and it carries
*ephemeral messages* where this coordination needs *durable state*. A live (non-git)
transport may be built later as its own piece of work; until then the file channel below is
the agreed mechanism.

**Protocol — one file, one writer.** Channel dir:
`~/.local/share/set-core/channels/<consumer-slug>/` (the slug is runtime-derived; never
hard-code a consumer name here — see External Project Confidentiality below). Each side
appends **only** to its own file and reads the other's:

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
- The channel survives a reboot but **not a lost disk, and not another machine.** It is
  coordination state, not the agreement itself: anything durable belongs in a repo. Read the
  channel to rebuild the contact; read `docs/integration/consumer-integration.md` to learn
  what was decided.

**DONE 2026-07-24 — the channel moved off `/tmp` (user instruction), jointly, both sides
switched.** A restart or a power cut used to lose the status. Kept here rather than deleted,
because every reason below is a rule the *next* move would otherwise rediscover:

- **Target: `~/.local/share/set-core/channels/<slug>/`.** Measured, not invented: that root
  already exists and is the framework's durable per-user store (`memory`, `metrics`,
  `e2e-runs`, `manager`, `runtime`). Survives reboot, pollutes neither repository, and is
  symmetric — neither side's tree is the host.
- **Why not a gitignored directory inside this repo**, even though the user allowed one:
  `.gitignore` is itself a *tracked* file, so an entry naming the consumer would publish the
  name that External Project Confidentiality forbids. The gitignore would BE the leak.
  Neutral ground cannot produce that problem at all. (A generically-named local dir such as
  `docs/integration/local/` stays fine — the rule is about the consumer's name, not the
  practice.)
- **Copy, never move.** `mv` breaks the peer's live watch mid-flight; `cp` is reversible and
  leaves the old file as a fallback. Both sides append a final pointer entry to the OLD file.
  **A closed file must state its successor, not merely fall silent** — otherwise a session
  that lands on it reads the old tail as the current state, which is the exact loss the move
  was meant to prevent. The old dir also gained a `MOVED.md`; neither side deletes it.
- **The watches are the dangerous step.** Kill the old Monitor FIRST, identified by the file
  it watches (`pgrep -af "<old path>"`), and only then start one on the new path — otherwise
  two run and every entry arrives twice. Same for the cron. During the cutover **one Monitor
  watching BOTH paths** is the correct shape (used by both sides here): the duplicate bug is
  two watchers on one file, not one watcher on two.
- **`CLAUDE.md` is the second place, and the second place is itself the error source.** The
  path lives in the rule book as well as in the running watch, so a move that updates only
  the watch sends the *next* session to the dead location. The peer had seven occurrences,
  this file six — of which two were instruction-valued. Grep before declaring the move done.

**Resuming the channel after a compact, a `/clear`, or a fresh session.** The channel is the
only thing that survives — rebuild the contact from it, do not ask the user to re-explain:

1. **Find it:** `ls -dt ~/.local/share/set-core/channels/*/ 2>/dev/null | head` — the channel
   dir is the newest match. Read its `README.md` first; it carries the protocol and the
   addressing convention. (Before 2026-07-24 the channel lived under `/tmp/*-set/`; if you
   land there, its last entry names the successor.)
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
   **Check the Monitor by WHAT IT IS, not by a number you remember.** Use
   `pgrep -af "<watched file>"` — match the process by the file it watches. `ps -p <pid>`
   answers a different question: whether *a* process holds that number. PIDs are recycled,
   so the answer can be yes while the Monitor is long dead, and the check then reports a
   watch that is not there. A task registry is worse still: the Monitor is a background
   process and does not appear in `TaskList` at all, so a registry lookup answers "no
   watcher" for a watcher that is running — which sends you to start a second one, which is
   the exact duplicate this step exists to prevent.

   **But `pgrep -af "<watched file>"` MATCHES ITSELF, and piping it into `grep -c` counts
   the count.** Measured four separate times on 2026-07-24: the check reported 3 and then 2
   watchers while exactly one was running. Every extra hit was the measuring command — the
   pattern appears in the searching shell's own command line, and so does any word used to
   filter it (`grep -c "while :"` matches a command containing the string `'while :'`). This
   is the same class as the completeness-word sweep: **the measurement is inside the corpus
   it measures.** Its direction is the dangerous one — it over-reports, and "two watchers"
   invites killing one, which can leave zero.

   Resolve each PID instead of counting lines, and discriminate by age — a real Monitor is
   hours old — but **the impostor is NOT always `00:00`.** Measured 2026-07-30: a self-match came
   back at `00:30`, because the measuring pipeline itself takes time to run. Age is a hint; the
   discriminator is `lstart` plus the command line, since a real watcher's argv contains the loop
   and the watched path while a self-match's contains the harness's shell snapshot.

   **And a dead watch is not necessarily a failure: check whether another session TOOK OVER.**
   Also measured that day — a Monitor exited non-zero because an incoming session had killed it by
   PID to avoid two watchers on one file, the outgoing session read that as the silent-death
   failure, re-armed, and recreated the duplicate. A deliberate kill and a spontaneous death
   produce identical evidence and need opposite responses; the channel tail separates them in one
   read.


   ```bash
   pgrep -f 'NEW=.*<watched file>' | while read -r p; do
     ps -o pid=,etime=,lstart= -p "$p"
   done          # one row per candidate; the seconds-old one is your own command
   ```

   This is the same defect class as reading a verdict out of prose: **measuring a proxy
   instead of the thing.** A remembered PID is a proxy for a process; a registry entry is a
   proxy for a running program; a matched substring is a proxy for a decision. The direction
   of the wrong answer is what makes it expensive — here it says "missing" for something
   present, and the correction is to create a duplicate.
   - a **Monitor** on the other side's file size (`persistent: true`) — how you learn about
     new entries without polling by hand. It is a real background process; `pgrep -af` on
     the watched path is the evidence, and it outlives a compact.
   - a **CronCreate** catch-up every ~10 minutes as the fallback for when the Monitor does
     die. Its prompt: read the last peer entry, check whether you have already answered it,
     do the work and reply if not, restart the Monitor if it is gone, and **say nothing at
     all when there is nothing to do** — a fallback that chatters gets muted. Pick a period
     that does not coincide with the peer's (they run one too); cron jobs are session-only
     and expire after 7 days.
4. **Announce the resume** in your own file: one `TÉNY` entry saying the context restarted and
   which entry number you have read up to, so the other side knows nothing was lost.
5. **The durable agreements are not in the channel.** The negotiated contract lives in the consumer's
   planning document (the channel's entries point at it) — read that before answering anything
   substantive, and never re-open a decision it already records.

**Addressing convention (spoken sessions).** When both copilots listen to the same
microphone, the speaker names the addressee **first in the sentence** — a turn opening with
this project's name (`set-core`, or its spoken variants) is for this session; a turn opening
with the other project's slug is not, and this session stays silent on it. An unaddressed
turn is for whoever it is actually useful to. Getting this wrong is what makes two copilots
talk over each other.

## Framework work goes through OpenSpec again — decided by the user, 2026-07-24

**On the set-core side this is settled, not a preference.** It was reopened because a day's
work slipped past it unnoticed: **81 commits, zero through an OpenSpec change**, and set-core's
largest new capability — the consumer status contract — had **no capability spec at all**.
The user's reason is the one that matters and it is not process hygiene: OpenSpec was adopted
here because set-core's accumulated knowledge had outgrown what plain agent operations could
carry. A capability that lives only in code, commit messages and a decision log is exactly
that failure returning.

**The rule, and the line it draws:**

- **New capability, or a change to a contract → OpenSpec.** Use `/opsx:ff` when the shape is
  already known; it produces every artifact in one pass and costs little against work that
  needs tests and verification anyway.
- **A measured defect fix → a direct commit is fine** — unless it changes contract behaviour,
  in which case it carries a spec delta. This is the same distinction the integration track
  keeps making by hand: *a fix* versus *a mechanism*.
- **Behaviour that shipped without a spec is documented retroactively**, as a change whose
  tasks are already done, then archived so the deltas reach `openspec/specs/`. The first one
  is `2026-07-24-consumer-status-contract` (20 requirements, three capabilities). Do not
  invent a new format for this — that change is the worked example.

**What this does NOT license.** It is not a reason to route a five-minute peer-reported fix
through a proposal, and it does not reopen the research habit the Discipline note below
closes. Two measured cautions, both current: **10 of 28 existing changes fail
`openspec validate --strict`**, and the last archive before 2026-07-24 was in April — so
adding changes without archiving them is a real failure mode here, not a hypothetical one.
The delta parser also **ends a section at any `##` heading**, so scope blocks written inside
`## ADDED Requirements` parse as zero requirements and validate as an empty change.

**The `/opsx:*` skills and commands are GENERATED — never customize them (2026-08-17).**
`.claude/skills/openspec-*/SKILL.md` and `.claude/commands/opsx/*.md` carry
`generatedBy: "<cli-version>"` and are rewritten wholesale by every `openspec update` — no
preserve marker, no merge. An update from 1.1.1 to 1.9.0 took with it the spec-verify
sentinels the gate parses, the `input.md` pre-read and the domain-knowledge loading; two
unit tests noticed and nothing else did. The direction matters: the new upstream versions
were **better**, so reverting was never the answer — only the carrier was wrong. Put an
OpenSpec-native rule in `openspec/schemas/spec-driven/schema.yaml` or `openspec/config.yaml`
(`context:`, `rules:`, `operations.*.guidance` — all three measured to reach the agent), and
a framework rule in a framework-owned file. Full table and the measurements:
[`.claude/rules/openspec-artifacts.md`](.claude/rules/openspec-artifacts.md).

**Discipline.** Between 2026-07-14 and Phase 0′ this repo produced five research documents and zero lines of code while a six-line guard stood between an orchestration run and a production-data mirror. Research is not the default next step — shipping the listed items is. Before proposing a new investigation, check whether it is already answered in `docs/research/`.

**Partly superseded — see the goals section at the top of this file.** The 2026-07-19
verdict (`docs/research/set-factory-verdict-2026-07-19.md`) still governs three things and
they are not open: no new repo or layer above set-core, the meetings→requirements pipeline
is permanently excluded, and set-core never *executes* a deployment. What the user has since
asked for — seeing project status in set-core, and planning/preparing/managing releases —
sits outside those three, and the verdict's own finding (the missing piece is a router
between differentiated ADWs) is what it continues.

**Known unrelated debt — and the figure is not the check.** Measured on a pristine checkout
of `HEAD` (2026-07-24, late): **81 failed / ~2980 passed / 21 errors**, and the failures are
not confined to `test_web_api_write.py` + `test_web_integration.py`. Pre-existing and outside
the current track.

**Do not quote this number as a baseline.** It has now been stale twice in one file: "17
failed" understated it by ~77, and "94 / 2631 / 21" — written earlier the same day — was off
by 352 passing tests within hours. The passing count also moves a few tests between runs. A
debt figure is a *measurement with a timestamp*, and a stale one waves a real regression
through as "expected".

**The check that works is a set diff against a baseline you actually ran.** Never a stash
inside a killable command — a timeout between the stash and the pop leaves a clean tree and
the whole session's work in `stash@{0}`, which looks exactly like a command that never
started:

```bash
git worktree add -q --detach /tmp/base HEAD
python -m pytest tests/unit -q -p no:randomly 2>&1 | grep -E "^(FAILED|ERROR) " | sed 's/ - .*//' | sort > /tmp/now.txt
# THREE import roots, and a session-end assertion that nothing leaked. Both matter — see below.
cat > /tmp/leakcheck.py <<'EOF'
import os, sys
def pytest_sessionfinish(session, exitstatus):
    base = os.environ["BASELINE_ROOT"]
    leaks = sorted({m.__name__ for m in list(sys.modules.values())
                    if getattr(m, "__file__", None) and "/set-core/" in str(m.__file__)
                    and not str(m.__file__).startswith(base)})
    if leaks:
        print(f"BASELINE LEAK ({len(leaks)}): " + ", ".join(leaks[:25]), file=sys.stderr)
        session.exitstatus = 99
EOF
(cd /tmp/base && BASELINE_ROOT=/tmp/base/ \
   PYTHONPATH=/tmp/base/lib:/tmp/base/modules/web:/tmp/base:/tmp \
   python -m pytest tests/unit -q -p no:randomly -p leakcheck 2>&1 \
    | grep -E "^(FAILED|ERROR) " | sed 's/ - .*//' | sort) > /tmp/base.txt
diff /tmp/base.txt /tmp/now.txt   # empty = no regression, whatever the counts say
git worktree remove /tmp/base --force
```

**The `PYTHONPATH` line and the assertion are not decoration — without them this check does
not compare two versions.** Measured 2026-07-24: `set-core` is installed editable, so its
`__editable___set_core_0_3_0_finder` resolves `set_orch` to `/home/…/set-core/lib` from
*anywhere*. A worktree at `/tmp/base` therefore ran the BASELINE TESTS against the WORKING
TREE's library — a hybrid, not a baseline.

Its fail direction is what makes it expensive: the usual change is additive, so old tests
still pass against new code and the failure sets come out identical. The check then reports
"no regression" having compared one version with itself, and it does so most convincingly
exactly when it is least earned. It only became visible when two baseline tests failed that
could not fail at `HEAD` — the hybrid's own tell, and it appeared by luck.

So: point `PYTHONPATH` at the worktree's source roots, and **assert where the imports came
from before believing the run**. This is the proxy-instead-of-the-thing class applied to a
version: `cd`-ing into a worktree is a proxy for running its code.

**And the first repair of it was itself incomplete, which is the more useful half.** It set
`PYTHONPATH=/tmp/base/lib` and asserted `set_orch` — one package, named by hand. Measured
afterwards, prompted by an integration peer generalising the finding on their own side: this
repo puts first-party code under **three** roots, and a raw `.pth` entry hard-codes
`modules/web` to the development tree. `set_project_web` is imported by 10+ unit test files
and was still coming from the working tree, so the "corrected" baseline was *still* partly
hybrid. The named list was a second copy, and it drifted at the moment it was written.

Hence the session-end check above, which asserts **the thing** — no module loaded from any
set-core checkout other than this one — instead of a list of paths somebody has to maintain.
Measured on `HEAD` with full isolation: **0 leaks, 106 failure entries, identical to the
partially-isolated run**, so the earlier conclusion survives while the evidence for it is now
real.

**One thing this does NOT cover**, raised by the same peer with their own measurement: a
**generated artefact** can come from the other tree even when every source path is right,
because it is a product, not a source (their case: a generated database client resolved from
the main tree's `node_modules`, so worktree source ran against main-tree schema — the same
hybrid, and additive changes keep it green). Measured here: set-core's Python has **no
generated layer** (`find lib modules set_tools -name '*_pb2.py' -o -name '*_generated*.py'`
→ empty), so `tests/unit` is not exposed. The dashboard under `web/` does have a build
product, and that path has **not** been measured — do not assume it is clean.

## The product is in ENGLISH — stated by the user, 2026-08-19

**set-core and every open-source `set-*` project are English.** Code, identifiers, UI strings,
comments, `.md` documentation, OpenSpec artifacts — all of it. The reason is not taste: these
repositories are public (`set-core`, `set-agent-comm`, `set-designer`,
`set-voice-agent-delivery` are on GitHub), and a framework nobody outside one language can read
is a framework nobody outside it can use. **The consumer projects are the Hungarian ones** —
which is the same split the abstraction already draws: the domain lives on the project's side,
and so does its language.

**Talking to the user stays Hungarian.** The rule is about what is written INTO the repository,
not about the conversation.

**The exceptions are the load-bearing half of this rule**, because a rule stated without them
is either ignored or applied to things it would damage. Measured on 2026-08-19: **130 `.md`
files under this repo carry Hungarian**, and most of them are one of these:

- **`docs/howitworks/hu/`** — a deliberate translation living beside `docs/howitworks/en/`.
  A translated doc set is not a breach of an English-first rule; it is the rule succeeding.
- **Test fixtures that simulate a Hungarian consumer** (`tests/e2e/scaffolds/**`). Translating
  them would make the fixture stop resembling what it stands for, and weaken the test.
- **Verbatim quotes of the user inside English comments.** A quote is a quote because it is
  what was actually said; paraphrasing it into English destroys the evidence it carries.

Everything else — a UI string, a doc, a spec, an error message — is English.

**What this rule was written after, so the next reader knows what it costs.** The fleet screen
shipped with 318 + 209 + 55 Hungarian characters of user-visible text while **every other file
in `web/src` was English**. Two things made it expensive rather than trivial:

- **There is no i18n layer** — the strings are literals. So six unit tests asserted the
  Hungarian text directly, and the translation broke **15 tests, all fifteen on wording and not
  one on behaviour**. A language switch in a codebase without an i18n layer is a test-suite
  change, and that is the part that gets underestimated.
- **A half-translated screen is worse than either state**, because an assertion written against
  a string the source does not say yet is a test for a screen nobody built. Translate a file and
  its tests in the same commit, and say in the commit which files are still untranslated.

⚠ **NOT settled, and deliberately left open rather than decided quietly: commit messages.**
Measured the same day — **40 of the last 40 are Hungarian**, and the repository is public, so
they are published too. The user named "the program language and the `.md` files"; commit
messages were not named, and converting a history is a different act from writing the next
message. Ask before changing the practice; do not drift either way.

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

Also read [`templates/core/rules/spec-verify-gate.md`](templates/core/rules/spec-verify-gate.md)
when you run `/opsx:verify` by hand. The generated skill performs neither the framework's
extra checks (traceability matrix, acceptance criteria, scope boundary, overshoot, the
per-change `verify-hook.sh`) nor the two sentinels the gate parses. The orchestrator's gate
resolves and names that file automatically; an interactive run does not.

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
- **The living record's path, and that it is read BACK, not summarised forward.** A compact
  keeps confidence and loses precision; the record is the only carrier that does not. If the
  summary and `docs/integration/consumer-integration.md` disagree, the file wins.
- **That the channel watches must be CHECKED after the compact, not re-armed on reflex.**
  Both the Monitor and the cron survive it (verified), so an unconditional re-arm produces
  duplicates — two notifications per entry, two answers to one question. Nothing reports a
  watch's death either, and a peer waiting on an answer looks exactly like a peer with
  nothing to say: `CronList` for the cron, `pgrep -af "<watched file>"` for the Monitor —
  never `ps -p <remembered pid>` and never a task registry, both of which answer a
  different question than the one being asked. Then fill only the real gap.

## Getting Started
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

See [START.md](START.md) for application startup commands (install, dev server, database, tests).
