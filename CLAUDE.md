
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

**Shipped — the safety track, in order.** Nine commits between `8fae5733` and `01701912`
closed every write path into a consumer tree. The list is `git log`; what is NOT in git log
and must not be lost is above and below this line. One item is worth naming because a session
could undo it by accident: **`once: true`** in the deploy manifest separates scaffold from
knowledge — 41 entries are seeded once and never rewritten, 9 namespaced `framework-rules/`
entries keep flowing, and the split follows OWNERSHIP, not file type.

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
coordinate over a **file channel**. The protocol, the durable location, the resume
procedure after a compact, and the rules for checking the Monitor and cron **without
creating duplicates** are in the **`cross-project-channel` skill** — load it whenever you
are coordinating with a consumer's session, resuming one, or suspect a watch has died.

Two things stay here because a session must not have to go looking for them:

- **DECISION 2026-07-24 — the git-based control sync (`set-control-sync`, `.set-control`,
  the ~15 s commit cycle) is NOT the cross-project channel.** Do not revive it for this.
- **Find the channel with** `ls -dt ~/.local/share/set-core/channels/*/ | head`; read its
  `README.md` first. **Remove this section once a real transport ships.**

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

**Known unrelated debt, and how to measure a regression.** This repo has a substantial
pre-existing failure count in `tests/unit`. **A debt figure is a measurement with a
timestamp — never quote a remembered number as a baseline**; every figure written down here
has gone stale within hours at least twice. The only check that works is a **set diff
against a baseline you actually ran**, and building that baseline correctly is subtle enough
to have been got wrong twice: the recipe, the three import roots, the session-end leak
assertion, and why `git stash` must never sit inside a killable command are in the
**`regression-baseline` skill**. Load it before claiming anything about a regression.

## Every reported defect goes into the bug register — stated by the user, 2026-08-19

**A defect that anybody reports — the user, you, a peer session — and that is NOT a
task in an open change goes into [`openspec/bugs/README.md`](openspec/bugs/README.md),
at the moment it is reported.** The user's reason is the one that matters: a session
runs out, and a defect held only in the conversation goes with it.

The line, in the user's own framing (*"olyat ami nem az adott change-be tartozik mint
task"*): in scope for an open change → it is a task in that change's `tasks.md`;
anything else → the register. A register entry leaves by becoming a task or a commit,
never by being deleted.

**Two conditions, and they are what decide whether the file is used or abandoned:**

- **Every entry names how it was MEASURED and what would prove it fixed.** A pile of
  "this looks wrong" is unactionable, which is the same as not having a register. The
  file's own format section carries the shape.
- **Closed with evidence, never removed.** A deleted entry and one that was never
  written are indistinguishable — the same reason a completeness claim must be a
  measurement rather than a summary.

**And verify a relayed report before entering it.** The first three entries came from
three different reporters and one was wider than the code: "the screen cannot stop an
agent at all" was really "stopping is reachable only through an open terminal". The
narrower statement is the one somebody can act on, and the checking cost seconds.

## The product is in ENGLISH — stated by the user, 2026-08-19

**set-core and every open-source `set-*` project are English.** Code, identifiers, UI strings,
comments, `.md` documentation, OpenSpec artifacts — all of it. The reason is not taste: these
repositories are public, and a framework nobody outside one language can read
is a framework nobody outside it can use.

⚠ **Which repositories those are is a MEASUREMENT WITH A DATE, not a list to inherit.**
Measured 2026-08-19 with `gh repo list tatargabor --json name,visibility`: **PUBLIC** are
`set-core`, `set-agent-comm`, `set-copilot`, `set-atlas`, `set-demo`, `set-claude-handoff`
and `set-voice-agent-delivery`; **`set-designer` is PRIVATE**. This paragraph previously
named four repos and called `set-designer` public. Both errors ran in the reassuring
direction — the surface looked smaller and safer than it was — and the four it omitted
included the two most heavily contaminated ones. Re-run the command; do not trust the list.

**The consumer projects are the Hungarian ones** —
which is the same split the abstraction already draws: the domain lives on the project's side,
and so does its language.

**Talking to the user is ENGLISH too, from 2026-08-29.** This sentence used to read "talking to
the user stays Hungarian", carving the conversation out of the rule. The user closed that carve-out
directly — asked whether the switch covered the conversation as well, they answered that it does.
`~/.claude/settings.json` already carries `"language": "English"`, so the harness agrees with the
file; if the two ever disagree, ask rather than guess which one is stale.

**The exceptions do not follow the conversation into English.** A verbatim quote of the user stays
in the language they said it in — inside an English sentence — for the same reason it does in a
commit message: a paraphrase destroys the evidence a quote carries. Same for the domain word.

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

**SETTLED 2026-08-29 by the user: commit messages are ENGLISH from now on.** This paragraph
used to say the question was deliberately left open, and it is now closed in the English
direction — the user's words were *"tell agents here in the project to switch to english"*, and
the consumer side is switching in the same round.

**What changes:** every commit message written from now on, in this repo and in every public
`set-*` repo. Same for anything else an agent writes that lands in the repository or in a
published artifact — a PR body, a tag message, a release note.

**What does NOT change, and both halves are load-bearing:**

- **History is NOT rewritten.** Measured 2026-08-29: 38 of the last 40 subjects carry Hungarian
  diacritics, out of **2641 commits total**. Converting a history is a different act from writing
  the next message; a mass rewrite would break every sha reference in the bug register, the living
  record and the archived changes, for no reader's benefit. So expect a mixed log — deliberate,
  not drift.
- **The three exceptions above still hold.** A verbatim quote of the user stays verbatim, inside
  an English message; `docs/howitworks/hu/` stays translated; the Hungarian-consumer test fixtures
  stay Hungarian. A commit message quoting the user says what was actually said.
- **The domain word stays.** The consumer's business vocabulary is not a technical term to
  translate — that rule is unaffected by which language the surrounding sentence is in.

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
- **The memory system.** A memory written while working on consumer data can capture that
  data verbatim. The automatic session-end extraction that made this routine is gone with
  the removed subsystem, but a hand-written memory carries the same risk. Generalize before saving —
  describe the pattern, never the instance — and treat a memory naming a consumer entity as a
  defect to correct, not as harmless.
- **Diagnostic output.** Error paths that dump a record, a URL, or a row to aid debugging.
  Log the shape, not the content: `db_safety.py` logs a URL's scheme and nothing else, which
  is the pattern to copy.

## Memory — the native layer, and what it does NOT do

**set-core ships no memory subsystem.** The one it had was removed on 2026-08-22
(`openspec/changes/remove-shodh-memory`) after it was measured **injecting a false claim
about the user** into unrelated sessions: over 21 days and 4958 transcripts, 187 memory
lines reached a session and **168 of them (89.8 %) were `User frustrated` records**. The
detector fired on exclamation marks, so `szuper!!!` and `pont igy akartam!!!` — both
delight — were stored and replayed as anger. **Exactly one line in 187 was a reusable
fact.** The same write path also persisted meeting-transcript content, which is the
confidentiality carrier this file names below.

**What memory IS now:** Claude Code's own per-repository directory,
`~/.claude/projects/<project-slug>/memory/`, indexed by `MEMORY.md`. Nothing else. Do not
introduce a second store beside it.

**The limit is load-bearing, so it is stated rather than assumed.** Only the **first 200
lines, or 25 KB**, of `MEMORY.md` are injected at session start. Content past that cut
loads for nobody and **nothing warns** — the same silent-truncation shape as an empty
injection reading like "no relevant memory". Measured 2026-08-21: one project's index was
already 123 lines / 20 550 bytes, so this is near-term, not theoretical. Keep the index to
one line per memory; treat 150 lines or 20 KB as the point to prune.

The topic files themselves are **not** loaded at startup — read them with ordinary file
tools when the index says one is relevant. `/memory` browses and edits; `/context` shows
what actually loaded this session.

**What was lost, stated so you meet a documented absence rather than a missing feature:**
no semantic search, no tag filtering, no temporal queries, no full-text search, no
cross-device sync, no version history, and no automatic session-end extraction. The removed
subsystem had **all seven** — and produced one useful line in 187. Searching means reading
the index and opening the file it points at. If you need one of the seven, that is a change
of its own, measured against the native layer rather than against a vacuum.

**Two rules on what may be written, both learned the expensive way:**

- **A memory records a fact, never a claim about the user's state.** No inferred emotion, no
  sentiment label the source text does not support. And **never store a harness artifact
  verbatim** — a task notification, a cross-session message, another agent's system prompt,
  a transcript fragment. Those were 89.8 % of what the old system injected.
- **Confidentiality survives the removal.** No memory file may carry a consumer project
  name, a partner name, a personal name, or content derived from a customer's data.
  Generalise before saving; a memory naming a real entity is a defect to correct, not
  harmless content. See External Project Confidentiality above.

### Memory Safety During Verification
Memory is a hypothesis, not a verdict. During `/opsx:verify`, always check the filesystem
(Glob, Grep, Read) — never skip a check because a memory says "known false positive" or
"same pattern". A memory records what was true when it was written, and it is not
branch- or worktree-aware.


Also read [`templates/core/rules/spec-verify-gate.md`](templates/core/rules/spec-verify-gate.md)
when you run `/opsx:verify` by hand. The generated skill performs neither the framework's
extra checks (traceability matrix, acceptance criteria, scope boundary, overshoot, the
per-change `verify-hook.sh`) nor the two sentinels the gate parses. The orchestrator's gate
resolves and names that file automatically; an interactive run does not.

## Auto-Commit After Apply
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

After a skill-driven apply (e.g. `/opsx:apply`) finishes or pauses, automatically commit all changes. Follow the standard commit flow (stage relevant files, write a concise commit message).

## E2E runs and consumer diagnostics

set-core is developed and battle-tested through consumer projects. Everything about
setting up a run, starting the sentinel, comparing two runs, harvesting framework fixes
from a consumer, and running the web dashboard's Playwright suite is in the
**`e2e-runs` skill** — load it before touching any of that.

**The one rule that stays resident, because breaking it costs a whole run:** NEVER
initialize an E2E run by hand. Use `tests/e2e/runners/*.sh`. If you must init manually,
`--project-type web --template nextjs` is mandatory — without it no `project-type.yaml`
is written, `NullProfile` loads, and every integration gate silently skips.

## Compact Instructions

When compacting context, always preserve:
- Current OpenSpec change name and task progress (e.g., "working on modernize-claude-config, 15/30 tasks done")
- List of files modified in this session
- Active worktree path (if working in a worktree)
- Test commands and their last pass/fail results
- Any unresolved errors or blockers
- The cross-project channel dir (if one is active) and the last entry read on each side — the
  section above names where it lives; the `cross-project-channel` skill carries the protocol
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

## Persistent Memory
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

This project uses Claude Code's own per-repository memory: Markdown files under
`~/.claude/projects/<project-slug>/memory/`, indexed by `MEMORY.md`.

**How it actually loads — the limit matters:**
- Only the **first 200 lines, or 25 KB**, of `MEMORY.md` are injected at session start.
  Content past that cut loads for nobody, and nothing warns you. Keep the index to one
  line per memory.
- The individual topic files are **not** loaded at startup. Read them with ordinary file
  tools when the index says one is relevant.
- Use `/memory` to browse and edit, `/context` to see what actually loaded this session.

**What it does NOT do**, so you reach for a documented absence rather than a missing
feature: no semantic search, no tag filtering, no temporal queries, no full-text search,
no cross-device sync, no version history, and no automatic session-end extraction.
Searching means reading the index and opening the file it points at.

**Writing a memory:** one fact per file, with a `name`, a one-line `description`, and a
`type` of user / feedback / project / reference. Add a one-line pointer to `MEMORY.md`.
Never store a harness artifact verbatim — a task notification, another agent's prompt, a
transcript fragment — and never record a claim about the user's emotional state.

**Confidentiality:** no memory file may carry a consumer project name, a partner name, a
personal name, or content derived from a customer's data. Generalise before saving; a
memory naming a real entity is a defect to correct, not harmless content.
