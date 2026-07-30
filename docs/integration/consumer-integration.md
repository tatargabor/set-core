# Consumer ↔ set-core integration — the living record

**This is the highest-priority track while it is open.** It is also the one most likely to
be lost, because it spans two repositories, two agent sessions, and a file channel that
holds coordination state rather than agreements. Everything durable about it lives here.

**Update this file as part of the work, not after it.** A step that is done but unrecorded
is indistinguishable from a step that was never taken — and the next session will redo it
or, worse, build on an assumption about it.

> **Confidentiality.** The consumer is never named here, in any commit, or in any other
> set-core artifact. It is "the consumer" or "the flagship consumer". The boundary is
> persistence, not naming: set-core may read the project's data at runtime and must write
> none of it down. See the confidentiality section in `CLAUDE.md`.

---

## FIRST — where the channel stands right now (2026-07-30 14:15, restart completed)

Written across a deliberate session restart, so the next session does not read 6000 lines to
find the live thread. **This block is a pointer with a timestamp, not a standing summary —
check the channel tail before trusting it.**

- **Live thread:** the `caveats` envelope key. Shape fully settled and additive; see the
  `caveats` rows and paragraphs in *Decisions → Still open* below. **Nothing is being built
  on either side.** The next move is theirs: their user must approve their T16 row, and they
  will say so on the channel. Only then does an OpenSpec change start here.
- **Channel tail now:** this side `S#141`, their side `W#141`. `S#141` announces the resume and
  carries no question, so a quiet channel is the expected state, not a fault.
- **The Monitor died with the restart and is re-armed** — measured by identity on 07-30 14:12,
  not recalled: `pgrep -f 'NEW=.*wpc-pont'` returned PID 1776229 aged `00:04` (the watch) plus
  two `00:00` hits (the measuring command itself). This is exactly the failure that cost five
  days of silence on 2026-07-28..29 (see *Resuming* below). A cron fallback was deliberately
  **not** re-added: it is session-scoped too, so it cannot witness the death it guards.
- **Why the restart happened:** the set-core MCP server had never been registered for set-core
  itself; it is now (`claude mcp list` → `set-core … ✔ Connected`), and only a new session picks
  it up.
- **What started here instead of waiting (07-30 14:13, decided under the delegation mandate):**
  `bugfix-lane-with-a-real-delta` — item 4, the single live item, artifacts complete and zero
  code. The reasoning is recorded at item 4 below; the short form is that the *recommended*
  next build (problem-indicator declaration) needs channel agreement from a peer who is
  himself blocked, while this one needs nothing from them. Announced as `S#141` so the choice
  is not invisible to the other side.

---

## Read this back — do not re-derive it, and do not trust a paraphrase of it

Stated by the user on 2026-07-24: **the important decisions and details must be written down
before a compact, and read back by whoever resumes.** The reason is not tidiness — it is
that error here *accumulates*, and each hop dilutes in one direction only: **precision goes,
confidence stays.** A finding that arrives as "we hardened the parsers" has lost the part
that made it useful. A decision that arrives as "we agreed on the envelope" has lost the
alternative it beat and why, so the next session cannot revisit it — only inherit it.

Three carriers of this track are lossy, and all three are in play at once: the **compact**
(summarises), the **agent channel** (paraphrases across a repository boundary), and the
**channel itself** (a machine-local file, so a lost disk or a second machine loses it —
until 2026-07-24 it sat in `/tmp` and a mere reboot was enough). This file is the only
carrier that is not.

So, on resuming:

1. **Read this file end to end before deciding anything.** It is short on purpose.
2. **Re-check, don't re-derive.** Every claim below names how it was verified. Re-running
   that check costs seconds; re-deriving the conclusion costs a session and can land
   somewhere else.
3. **When this file and your recollection disagree, this file wins** — unless you can
   produce evidence, in which case fix the file in the same breath.
4. **Anything decided or measured since the last write goes in before the context ends**,
   not after the next step. The next step may not happen in this session.

The general form of that discipline — what counts as knowing something, and how a claim and
its evidence stay attached — is in
[`.claude/rules/evidence-discipline.md`](../../.claude/rules/evidence-discipline.md).

---

## Why this exists — the goal, in one sentence

**Open set-core and see where the project stands.** Not an API that returns correct JSON:
a screen. The goals in full, and the constraints that bind them, are at the top of
`CLAUDE.md` and are not restated here — read them first, they outrank anything below.

Two of them are load-bearing for every decision on this page:

- **The project supplies the data; set-core supplies the abstraction.** The domain stays on
  the project's side. A design that only works for one consumer is not finished.
- **The learning flows from the consumer to the framework.** Their SDLC is ahead of
  set-core's. If a design would require the project to change how it works, the design is
  wrong — not the project.

---

## Where we are — 2026-07-24

### Shipped, and verified against a live contract

| What | Commit | Verified how |
|---|---|---|
| Contract reader (Layer 1, domain-free) | `86e0bc5e` | 6/6 commands answered, zero gaps |
| Manifest discovery (`.set-endpoint.json`) | `b4a0deff` | manifest resolves, unknown version refuses to spawn |
| Read-only status API + declared commands | `734c445f` | `--eval` → 400, undeclared → 404, neither reaches argv |
| Project Status screen | `126c71c8` | live page: 6 sections, 9 tables, 185 rows, 0 JS errors |
| Renderer honesty tests | `a2eea14a` | 11 tests |
| Long scalar lists capped at 5 chips | `248a76c8` | one live command emits 17 in a cell; 2 of 4 tests measure, 2 guard |
| Project-declared emphasis (`_emphasis`) | `d54c0807` | live: 1 marked element, marking not rendered as data, 0 JS errors |
| Project-declared section ranking (`sections`) | `55554bb8` | live: 3 sections in declared order, descending weight; 4 of 7 tests measure |

**The acceptance test is met for reading.** The screen is at `/p/<project>/status`, listed
in the sidebar under Orchestration.

**Nothing is pushed.** Both sides are holding commits deliberately — see the standing
constraint in `CLAUDE.md`.

### The design decision that carries the most weight

**set-core keeps no built-in list of contract commands.** The project declares what it
answers, in its manifest or the operator's config, and set-core asks exactly that.

This was nearly not the case, and the alternative looked reasonable: five command names
hard-coded in Layer 1. It would have worked that day. Then the consumer added a sixth
command to its manifest mid-session, and it appeared through the API with **zero framework
changes** — under the hard-coded design it would have waited for a set-core release.

The general rule this stands for: *the declaration is the contract, not the documentation.*

### What the framework must never do here, and how it is held

| Rule | Held by |
|---|---|
| Never persist what it reads | a test asserting a query leaves no file behind |
| Never invent a value — a gap renders as a gap | `StatusResult.failure` has no data field to fill |
| Unknown is not zero and not success | `statusValue.test.tsx`, both directions |
| No field name is recognised anywhere in the renderer | tests use nonsense keys on purpose |
| A command name never reaches argv unvalidated | declared-list allowlist + name shape |

---

## Agreed with the consumer, on the channel

- **The framework takes the project's published answer; it never recomputes it**
  (2026-07-24, channel W#105–W#107 / S#108). set-core defines the SHAPE of a lane signal;
  the project supplies the VALUE. Where a signal's condition names something the project
  already publishes through its status contract, the gate invokes that command instead of
  reimplementing the rule.

  **Their reason is a measurement, not a preference:** two implementations of one business
  value drifted to 412% and 164% on their side, and a customer noticed before either team
  did. A framework-side reimplementation is that defect with a longer feedback loop, because
  the two answers are read by different people.

  **This collided with a rule of ours, and the resolution is the useful part.** Our reader
  is forbidden from touching a service — a declaration reachable only through a running
  system is unreadable exactly when it is needed. The two rules are right about different
  objects: the **declaration** is configuration and stays service-free; the **value** is
  data and belongs to the project. Evaluation may call a project command; reading
  declarations may not.

  **Safe only because the thing asked is the worktree, and they measured that rather than
  assuming it:** their defect query ran in a disposable worktree with no `node_modules`, no
  `.env` and no database, in 129 ms — and answered about *that tree*, proven by breaking one
  reference in the worktree and watching the worktree's answer change while the main tree's
  did not.

  **Their yes is conditional, and the condition is in the spec.** A silent command yields
  UNEVALUATED, never a pass and never a fallback computation. That is acceptable *because
  their own blocking gate covers the same defect class*, so framework silence costs earlier
  warning rather than protection. Where a signal is the only enforcement of its class,
  silence is a real hole and it must block instead. Recorded as
  `lane-signal-declaration` requirement "the framework takes the project's published answer"
  and design decision D12.

  **BUILT 2026-07-24 (tasks 4.9–4.12, AC-25/26/27).** The gate now takes a declared
  `answer: {command, field}` through `project_status.query` — the existing mechanism, so the
  timeout, the declared-command list and the read/write separation come for free rather than
  as a second invocation path. Verified by mutation, not by reading: **11 mutations applied
  one at a time, each killed the test aimed at it, each restore re-grepped** (delegation
  running first, the two-state split, the write-command refusal, the undeclared-command
  refusal, list-not-count, identifier-not-record, missing-path-is-not-empty, the projection
  refusal, the strict bool, sole-enforcement blocking, out-of-scope not blocking).

  Four shape decisions, each with the reason it is not a parser limitation:

  - **Delegation runs BEFORE any handler**, so a declared answer wins even where set-core has
    a handler for the same condition kind. The load-bearing test is the negative one —
    `test_the_published_answer_is_taken_and_the_handler_is_not_consulted` — because the
    positive one passes with a fallback in place.
  - **`field` is a plain dotted path resolved against the envelope's `data`.** An index or
    filter is refused at parse time: a projection is the project's own rule re-expressed in
    the framework's syntax, and the divergence this whole decision was written after needed
    two *places*, not two languages.
  - **A list of identifiers, never a count.** A count cannot be baselined and cannot be
    excluded, so a published `0` would read as proof there was nothing to answer — a zero with
    an empty breakdown, at the one place a reader believes it.
  - **A lane signal never invokes a WRITE command**, nor one the tree's contract does not
    declare readable. Framework-enforced, not trusted to the declaration.

  **Two unevaluable states, at the consumer's request and with their measurement behind it**
  (channel W#108): their entire read contract — all nine commands AND both signal
  declarations — existed on one machine and was absent from `origin/dev`, so a clone finds
  nothing to ask rather than receiving a wrong answer. `not-configured` and
  `command-not-found` → `reason_class="not-published"`, printed as
  `[NOT PUBLISHED BY THIS TREE]`; every other class → `"unusable-answer"`, printed as
  `[UNEVALUATED]`. **Neither is a pass**, and `sole_enforcement` blocks on both — naming the
  state honestly and refusing to pass are not in tension.

  **Still open and deliberately so:** AC-10. The gate is no longer inert, but the shape that
  AC names — a new capability delivered under a cheap declaration — needs a diff against a
  base ref rather than a published value, and no handler exists for it. The consumer confirmed
  the split from their side: their defect signal's answer is already a contract field, their
  new-module signal's is not, because only the framework holds the base ref.

  **CLOSED end-to-end the same evening (channel W#109).** The consumer published the decided
  list under one path, declared it, and ran **set-core's own `build_report` against their
  tree**: on the main tree `0 fired / 1 did not fire / 1 unevaluated`, and in a disposable
  worktree with a reference deliberately broken, `fired: 1` with the violation named. So the
  chain closes — our gate asks their command in a bare tree and reports THEIR answer back,
  firing in the broken tree and staying quiet in the good one. First time the mechanism has
  produced a real `fired` with content.

  Three things settled with it, each worth more than the answer itself:

  - **The key name is `answer`, and their reasoning is the rule applied to itself:** the
    framework defines the SHAPE, the project supplies the VALUE — a key name is shape, so it
    is ours. Forcing their word onto our schema would break the same rule in the other
    direction.
  - **A violation identifier must be stable across environments.** They rejected our example,
    which used a runtime-assigned sequential number: such an identifier differs per
    environment and cannot be derived where no runtime exists — which is exactly the worktree
    the gate reads in. Both the baseline and the exclusions key on the published string, so a
    per-environment identifier makes the baseline hold on one machine and not another. This
    generalises beyond them and belongs in any project's contract: **publish an identifier
    the tree itself can produce.**
  - **A near-miss key is now refused, not stored** (`4.13`, AC-28). They measured what
    happens when the delegation key is mistyped or carries an older name: it lands in `extra`,
    `answer` stays `None`, and evaluation silently takes the handler route — the recomputation
    the delegation exists to prevent, selected by a typo. `[NOT READ]` does not cover it,
    because a report is not a gate. Refusal covers the optional fields only; required ones are
    already protected by their own missing-field refusal. The first implementation had a hole
    of its own — a pure case or separator variant escaped, because the "is it different?" test
    compared normalised forms while the reader matches raw keys — and the test written beside
    the function found it, not a reading of it.

- **Envelope v1**: `{contractVersion, generatedAt, command, ok, data, deprecated}`. An
  unsupported version is refused *before* spawning anything.

  **The failure half of the envelope, which this list omitted until a gate found it.** When
  a project answers `ok: false` it has answered honestly that it could not answer, and its
  reason is carried through rather than replaced with one of ours: the reader takes
  **`error`**, or **`message`** if `error` is absent — an undeclared fallback that had
  existed in the parser and in neither side's documentation, so a producer reading this page
  could not have known it works. A refusal with neither field still produces a result, with
  a reason saying exactly that: the project reported a failure and gave no reason. Nothing
  in that path ever renders as success or as zero.

  **What set-core itself says when it cannot get an answer — `errorClass`.** These are the
  framework's own words, not the project's, and they are the reader's only clue to whose
  side a failure is on. Grouped by that question, because it is the one a person actually
  has:

  - *We never got to ask.* `not-configured` (no contract declared here), `command-not-found`
    (declared, but not present on disk), `not-a-write-command` (a read name sent to the write
    path — refused before spawning), `invalid-argument` (an argument shape that could produce
    a flag).
  - *We asked and the attempt failed.* `spawn-failed`, `timeout`, `nonzero-exit`,
    `response-too-large`.
  - *We got something back and could not trust it.* `invalid-json`, `invalid-envelope`,
    `missing-version`, `unsupported-version`, `missing-data`.
  - *The project answered honestly that it could not answer.* `project-reported-failure` —
    the only one of the fourteen that is not a fault on this side, and the reason it must
    stay distinguishable from the rest.

  The list is held by a gate rather than by care: an `errorClass` this reader emits and this
  page does not name fails the build. It was added after the consumer found the same gap one
  level down on their side — a documented field whose *values* were undocumented — and said
  it had no counterpart here. It had fourteen.
- **Precedence**: operator config beats the repo manifest. The person present when
  something is wrong must be able to redirect it without editing someone else's repo.
- **Read and write are separate namespaces.** Write commands live in their own list
  (`writeCommands`), are never cached, and a generic renderer walking the read list can
  therefore never call one by accident.

  **Precisely how far that protects, because the sentence above reads stronger than it
  is.** set-core defends the *ambiguous* case itself: a name appearing in both lists is
  dropped from both and logged — a command cannot be safe to open a page with and also
  change something. It cannot defend the *misfiled* case, where a write command is declared
  only as a read: nothing in an answer says it mutates, which is the whole reason the
  namespaces are declared rather than inferred. That guard therefore lives on the producer's
  side, and the consumer built it (2026-07-24) after the risk was named. The failure it
  prevents is the worst one this surface has: a page load acknowledging manual tasks that
  nobody performed — the surface manufacturing its own `DONE`.
- **Write commands are idempotent.** The same acknowledgement sent twice is a successful
  no-op that reports it was already done. This is what lets the surface hold no state about
  what it has already sent.
- **Shape is declared, never inferred.** Where a value can be either machine-readable or
  prose, the contract says which (`scheduleKind: "cron" | "prose" | null`). This came from
  the consumer's measurement and is the pattern to copy, not an exception to it.
- **A null is not an absence.** "The repository does not say" must not render as "there is
  none". This is a contract-level distinction, not a rendering preference.

---

## Decisions

**The user has delegated these** (2026-07-24): decide from the experience already on the
record rather than escalating. That is a mandate to choose, not to guess — a decision made
this way must name the evidence it rests on, and go on this page so it can be revisited.

### D1 — the post-deploy acknowledgement is stored in a repository file

*Decided 2026-07-24. Both sides had independently reached the same recommendation.*

The alternative was a per-environment settings row in the project's database, which is
more consistent with how the project already stores its current release. It loses on one
point that outranks consistency: acknowledging the *production* environment would require
production database access from a local CLI, and the standing constraint says a piece of
work counts as a production action when it reaches production **as a consequence**. A repo
file makes the write path *structurally* incapable of touching production instead of
merely promising not to — and a promise is the thing this track keeps finding to be
insufficient.

Secondary reasons, none of them decisive alone: the contract stays database-free, it works
offline, and git gives the acknowledgement an audit trail for free.

**What follows for set-core:** the surface calls a write command in the contract's write
namespace and holds no state of its own about what it has sent. That is safe only because
the write is idempotent — see the agreements above. If idempotency is ever dropped, this
decision has to be re-opened, not worked around in the UI.

**set-core keys the acknowledgement by nothing — measured 2026-07-26.** The consumer,
carefully protecting its own scheme, moved a manual reminder to the end of a release list
so that "the set's `(release, index)` acknowledgement keys don't shift", and flagged it as
a requirement set-core imposes. Measured, set-core imposes no such thing. `write()`
(`lib/set_orch/project_status.py:637`) holds no acknowledgement store — its docstring is
explicit that set-core keeps "no copy and no memory of having asked" — and its one caller,
`post_project_write` (`lib/set_orch/api/project_status.py:196`), forwards the request `args`
verbatim to the project's own write command. No set-core caller constructs, hard-codes, or
derives a `(release, index)` key (`grep -rniE '\bwrite\(|project-status/write' lib/ bin/
web/src/` → the endpoint is the only caller). The frontend issues no acknowledgement write
at all, and where it holds selection state it deliberately keys by NAME not index
(`web/src/pages/ProjectStatus.tsx:127`) — the very fragility the reorder was avoiding. So
the `(release, index)` key is the *project's* scheme on the project's side; the only thing
set-core requires is idempotency, not index stability. If the consumer ever moves to a
content-based key, nothing breaks here. This is the same attribution class as the earlier
channel slips — a project-side mechanism credited to set-core — and it is corrected here by
measurement so it does not enter either rule book wrong.

### D2 — emphasis comes from the contract, never from a recognised field name

*Decided 2026-07-24, on the channel (S#69, answering W#65). Evidence: `248a76c8`, and the
`migrationCount` refusal that preceded it.*

The consumer asked, reasonably, that one field of a blocker be given "separate weight" on
screen, because it names the subset that someone actually has to act on. The request is
right about the goal and wrong about the mechanism: implementing it as asked means the
renderer recognises that field's **name**, which burns a consumer field name into the layer
whose whole job is not to have any. The same request was refused earlier for a different
field; accepting it now only because it is convenient would make the earlier refusal
arbitrary rather than principled.

**The offered mechanism instead** (built when the consumer confirms): a contract-level key
on the object — `_emphasis: ["<key>"]`, in the shape of the existing `deprecated` — that the
renderer honours without knowing anything about what it names. Two constraints, or it
reproduces the defect classes this track keeps finding:

1. **A declaration is not data.** If `_emphasis` names a key that is absent, the renderer
   draws *nothing* — never "1 emphasised field missing". That is the false-absence shape.
2. **The count comes from the data**; the declaration only says what to look for.

There was a zero-contract-change fallback: field order. **The consumer rejected it and took
the expensive path, and their reason is better than the offer was**: order would be a
*silent* contract, broken by an innocent reordering with nothing to say so — the same
reasoning that already put an explicit `primary` in the manifest instead of trusting the
order of `commands`. Recorded because it is the second time that principle has decided a
design here without being invoked by name.

**Both halves shipped 2026-07-24**: the producer's (`_emphasis` on the blocker, empty array
when there is nothing to mark) and this side's (`d54c0807`). Verified in a browser against
the live contract: exactly one emphasised element, holding exactly what the producer marked,
the marking itself not rendered as data, 0 JS errors. 6 of 8 new tests measure, 2 guard —
and the test *named* for false absence fails against HEAD on its other assertion, so its
false-absence half is a guard, not a measurement.

### The property this keeps re-proving, measured nine times

New producer fields reach the screen with **zero framework changes** — most recently a
`coverage` object (`source` / `excludes` / `complete`) attached both to a list and to the
blocker row derived from it, plus a new `kind` on an unknowns row. Measured on this side
rather than taken on trust: all three render, on both tabs, with 0 JS errors and no framework
edit. Before that: 67 bug rows carrying two new planning fields, and a blocker carrying a
nested list plus a nested table. This is no longer a pleasant surprise; it is the contract's
defining property, and the useful inversion is: **the day a new field needs a framework
change, a name has been burned in somewhere, and that is the bug** — not the field.

**The eighth one did surface a defect, and not in the reading — in the LAYOUT.** A ragged
nested key cannot be flattened into columns (correctly: most rows do not have it), so the
object renders inside one cell, where its own two-column grid wants 8rem for labels alone. In
a narrow cell the value column collapsed to about one character per line and a one-sentence
field turned the row into a 500-pixel tower, pushing the other two blockers off the screen.
Fixed with a minimum width on nested objects. Worth recording because of what found it:
**looking at the screen.** The field-presence check said RENDERED for all three — structural
counts prove a thing renders and say nothing about whether it is readable.

**The ninth arrived as a whole new bug-ingest contract** — four new source prefixes, three
new optional fields (`foundIn` / `duplicateOf` / `reopenOf`), a widened status set (seven
values) and a `CRITICAL` severity. Measured on this side, `2026-07-24T23:53`: it renders with
no framework edit and 0 JS errors — the read surface reads the repository, so it appears here
before the change is deployed anywhere. Two things worth keeping:

- **The two predicates the producer flagged as breaking are not on this side.** `grep -rn
  "OPEN_BUGS" lib modules web/src bin` is empty, and the reader has no `status`/`severity`
  predicate on the project's bugs — the framework renders the producer's count, never
  recomputes it. So the `3 → 14` blocker figure becomes correct here automatically because it
  is theirs; the `kind` value they deliberately did not rename is not matched by anything on
  this side.
- **A three-outcome gate proved the section mechanism.** A new close-gate can exit `0`/`1`/`2`
  where `2` = "cannot tell" (no DB, or a stale local mirror), and it lands in the producer's
  `unknowns` list, not `blockers`. That is *unknown is not zero and not success* — this
  surface's founding renderer rule — applied to a gate by the producer. Measured that it
  renders distinctly: the three sections draw at descending left-border weight
  (`4px` / `2px` / `1px`), so an "I could not check" never sits where a failure or a pass
  would be read.

### The bug-id SHAPE is about to change, and this side is opaque to it — measured 2026-07-25

The consumer is renumbering every bug identifier: the two current forms (`bugNumber` and a
`#`-delimited stable id) both retire, replaced by a `<PREFIX>-<NNNN>` shape whose number is
frozen at birth (so it is the same in every environment), with a committed old→new map. Two
questions arrived on the channel; both answered by measurement rather than assurance.

- **Does this side persist a bug identifier between two reads, so old references would go
  dead?** No — measured across every layer. The reader "neither interprets nor persists"
  what comes back (`lib/set_orch/project_status.py:19`); the transport's only cache is
  `_CACHE`, in-memory, `CACHE_TTL_SECONDS = 30`, dropped on every write, dies with the
  process, and the docstring forbids ever making it a disk cache
  (`lib/set_orch/api/project_status.py:8`, `:49`); the frontend stores only UI preferences in
  `localStorage`, never the fetched data (`ProjectStatus.tsx:14`, `StatusTable.tsx:16`, with a
  spy test proving it). So renumbering is traceless here — the next read shows the new ids. The
  only stale references are ones a *person* wrote down outside the surface; the committed map
  is the right tool for those, and needs no format change for this side.
- **Does the shape change touch this side's contract or code?** No. The reader owns the
  envelope and nothing inside `data` (`project_status.py:16`) and never parses the id — no
  `#`-split anywhere near it — so a `#`-less `SET-0042` is fine where an `email#…` was. The
  producer bug this exposed (their `deriveReplyState` derives the source from the id's `#`,
  so a renumbered id falls out of `REPLY_NOT_APPLICABLE_SOURCES` and inflates a "pending
  reply" blocker) is theirs, in their `set-api.mjs`; this side renders their count and never
  recomputes it, so the fix has no framework half. Measured against a follow-up that assumed
  this side keeps a "faithfully-adopted" copy of the producer's `covered()`/`bugNumber`
  predicate: it does not — `find . -name 'set-api*.mjs'` is empty and there is no
  `bugNumber`/`plannedIn`/`ID_RE`/`collectBugPlanning` anywhere in the source, so the "the two
  predicates must stay identical" invariant is internal to their repo, not a cross-project
  sync. Nor does this side traverse their `openspec/changes/archive/**` for bug ids (the 36
  `plannedIn`/`wasPlannedIn` signals that renumbering would zero are producer-internal); if the
  held `bugfix-lane` is ever built to read an archived id, their committed map is the runtime
  resolver. **The producer's false-closed reply-source task (a `[x]` that was never
  implemented, so the source was still derived from the retired id `#`-shape) was fixed and
  the change archived (their commit `2ddb7032`); verified on this side by looking at the
  rendered result, not the mechanism:** a refreshed read of `GET
  /api/{project}/project-status` returns the with-fix reply distribution verbatim —
  `notApplicable 87` (not the without-fix 67), `unmarked 4` (not 17), `pending 12`,
  `notNeeded 2` — all 111 ids in the new shape and none `#`-bearing, the explicit `channel`
  field present on every row and driving the derivation, and `REPLY_PENDING` a single blocker
  rather than an inflated count. This side computes none of it (`notApplicable`/`unmarked`/
  `replyState`/`summarizeReply` → 0 matches in the source), so the surface cannot diverge from
  the producer's corrected answer. And this side pins no id **shape**: the
  literal `email#` appears nowhere in the repo, and the held `bugfix-lane` design treats a
  stable identifier as *shape rather than value*. So the shape change raises no contract
  objection here — the recorded "always `email#…`" point is the consumer's own, and only their
  user can override it.

### The findings-parse "silently wrong" class — this side derives no readiness, measured 2026-07-26

The consumer fixed a `review-findings.md` parser on their producer side (their `set-api.mjs`,
their commit) that had **silenced an apply-blocking fact**: it read status only from a table
row while the current findings use a bullet form (`- **Status:** …`), and every heading reset
the section severity so `## CRITICAL` + `### F1` inheritance never fired — so a change with an
open CRITICAL came back as `blocksApply: null` ("unknown") instead of `true`. This is the
[false-absence / silently-wrong](../../.claude/rules/evidence-discipline.md) class: the reader
announced "we don't know" about a blocker it was looking straight at.

Two measurements say the class does **not** reach set-core, and the reason is the same
verbatim-render property that keeps the reply distribution honest:

- **The consumer-status reader derives no readiness.** `parse_envelope`
  (`lib/set_orch/project_status.py:467`) validates the envelope only — `contractVersion`, `ok`,
  presence of `data`, the `deprecated` list — and lifts `data` untouched;
  `grep -niE "findings|blocksApply|criticalOpen|readiness|severity"` over both reader files
  (`project_status.py`, `api/project_status.py`) returns no parse/derive site. So when the
  producer's fix flips `blocksApply: null` → `true`, set-core renders the corrected value with
  no code change. **This side never computed a readiness for the affected change**, so there
  was no set-core "unknown" to correct — the "unknown → BLOCKED" fix is the producer's
  derivation, which set-core only displays. The living record likewise records verbatim render,
  not a derived readiness, so nothing here to fix.

- **set-core's own findings parser is not vulnerable to either bug.** `_parse_review_findings`
  (`lib/set_orch/verifier.py:656`) exists but serves set-core's OWN orchestration, reading
  findings set-core itself writes (`_write_review_findings_md`, `:706`) — a separate mechanism
  from the consumer reader. Measured against the two bugs: it reads a `- [ ] [SEVERITY]
  file:line — summary` checkbox line, not a table (bug a absent); severity is taken inline
  per-line, with no `##`-heading inheritance to reset (bug b structurally impossible). The
  class requires section-inherited severity plus a table-only read; this parser has neither.

The general shape, worth keeping because it recurs: **a producer that derives can silence;
a reader that renders verbatim cannot.** set-core stays on the render side of that line by
construction — see [D2](#d2--emphasis-comes-from-the-contract-never-from-a-recognised-field-name).

### Incoming contract growth: bug `type` (BUG | REQUEST) — measured verbatim-immune 2026-07-27

The consumer signalled (pre-push, contract change on the read surface) that the bug contract
gains a mandatory `type` field per row (`BUG` | `REQUEST`, missing = `BUG`, fail-closed), a new
`data.typeSummary` breakdown, a `byType` split on the `release-readiness` `OPEN_BUGS_*` rows,
and a `unit`-string change `"hiba"` → `"bejelentés"`; `laneSignals.fixedWithoutRegressionTest`
narrows to `type:"BUG"` rows only. **Measured on this side the same day, not assumed** — the
whole growth is invisible to shipped set-core, for the reasons the verbatim architecture
predicts:

- `parse_envelope` (`lib/set_orch/project_status.py:467`) validates only the envelope and lifts
  `data` verbatim — no field whitelist, so `type`/`typeSummary`/`byType` reach the screen with
  zero code change.
- `grep -rn "typeSummary|byType|fixedWithoutRegressionTest|'hiba'" lib/ modules/` → 0 hits: no
  Python derivation and no value-match on the `unit` string, so `"hiba"→"bejelentés"` is inert.
- `grep -rn "hiba|byType|typeSummary" web/src/` → 0 relevant; every `.kind` hit is set-core's own
  DAG node kind (`impl`/`merge`/gate), never the `release-readiness` row `kind`.
- `grep -rn "OPEN_BUGS|release-readiness" lib/ modules/ web/src/` (non-test) → 0 hits. The
  consumer preserved the `kind` NAME believing a set-core gate matched on it; **no such gate
  exists here.** Harmless (verbatim render is indifferent), but the reason is not a set-core
  fact and must not be recorded as one (channel S#135 corrects it).

**Forward-note for the gated `bugfix-lane-with-a-real-delta` work (item 4, user-approval-pending):**
the shipped reader consumes no `laneSignals` at all, so the BUG-only narrowing is invisible
today. When that lane is built to read `fixedWithoutRegressionTest`, it must adopt the same
`type:"BUG"` predicate the consumer's blocking gate uses, so the signal and the gate cannot
drift — a finished REQUEST has nothing to regress from.

### D3 — the channel stays plain files; it does not move onto MCP tools

*Decided 2026-07-29, against the user's own opening preference, because the measurement
refuted the argument for it — including the argument this side had just made.*

The proposal was to put `channel_status` / `channel_read(since,…)` / `channel_append` MCP
tools over the same two files, so a session would see a delta instead of a 400 KB log. The
token argument does not survive contact with the traffic:

| day | this side → | consumer → |
|---|---|---|
| 07-24 | 133 | 120 |
| 07-25 | 6 | 13 |
| 07-26 | 4 | 7 |
| 07-27 | 1 | 1 |
| 07-28 | 0 | 2 |

Mean entry ≈ 2.7 KB ≈ 700 tokens, so current traffic costs ~1400 tokens/day. And `tail -n N`
*already* reads a delta — an MCP tool would not read less, only differently. The 400 KB file
size is the arresting number and the irrelevant one: nobody reads the file whole.

**What MCP would genuinely buy** (kept, so the decision can be revisited rather than
re-argued): machine-generated timestamps and entry numbers — the two sides still number
differently, `S#136` here versus nothing on theirs — a cursor that survives a compact, and
writes without a permission prompt. **What it costs:** one more moving part (uv + venv +
fastmcp) that can fail, where `cat >>` cannot. Neither side gains push notification either
way; that stays the Monitor's job.

**Revisit when** a third project joins (N×N file pairs stop being hand-manageable) or daily
traffic returns to three figures. Neither holds today.

*Two findings fell out of measuring this, both worth more than the decision.* First: the
set-core MCP server **was never registered for set-core itself** — `.claude.json` had
`mcpServers: {}` for this project and the repo's `.mcp.json` was empty, while 11 other
projects had a stdio entry. `set-project init` deploys outward and never ran on the framework.
Registered on 2026-07-29 (local scope); it needs a session restart to appear.

Second, and it corrects a claim that had been sitting in `CLAUDE.md`: the reason given for
the file channel — that `.set-control` is per-project so `send_message`/`get_inbox` cannot
cross a project boundary — **is false**. `_find_control_worktree()`
(`mcp-server/set_mcp_server.py:462`) walks the **global** registry
(`~/.config/set-core/projects.json`, 38 entries) and returns the first project that has a
`.set-control`, regardless of where the server started; both sides would resolve to the same
worktree. The actual blockers are that no `.set-control` exists on either tree (both tools
return `Error: No .set-control worktree found`) and that the git commit cycle was rejected.
The sentence described what the resolution *ought* to scope to rather than what the function
does — the proxy-instead-of-the-thing class applied to a code path. Fixed in `CLAUDE.md:197`.

### Still open

| Decision | Owner | State |
|---|---|---|
| Whether a derivable list stays in the contract | consumer | measured: nothing here depends on it, so it is theirs to decide — and the row's height is this side's problem to fix, not a reason to drop their field |
| `caveats` — an OpenSpec change on this side | this side, gated on the consumer's user approval (W#141) | **shape fully settled**: `"*"` default + per-field keys, **additive**, keys `KÖVETETT`-style (uppercase, accented). Their T16 row awaits their user; a finished spec before that is just pressure. Starts when they say go. |

**The gap, measured 2026-07-30 when the consumer offered a tenth read command and led with its
own limits.** Taking the command itself costs nothing here — `project_status.py:101-102` keeps
no built-in list of contract commands, so a new name in `commands` is an entry, not a framework
change (the ninth time that has held). What does *not* fit is the caveat they attached to it:
their counts are correct numbers whose **meaning is narrower than the name suggests** (a
"not-tracked" count describes their own register, not the world; a "tracked" count is a known
lower bound because one trailer is still hand-written).

The envelope carries three "do not read it that way" signals and none of them is this one:
`gaps` is per-**command** (`:758`), `errorClass` is per-failure (`:390`), `deprecated` is per-
**field-name** (`:395`). All three describe something being absent or wrong. Here the command
succeeds, the field exists, and the value is right — only the reading is wider than the fact.
So the number would land on screen at the same visual weight as every other number, and the
caveat would stay in a channel entry: **the number travels, the caveat does not.** This is the
false-absence class one layer up, and `web/src/components/statusShape.tsx:41-48` already spells
that class out for `deprecated`.

Proposed on the channel, deliberately as the existing shape rather than a new language: a
framework-level `caveats` key, field name → one sentence, **written by the producer, never
decided by the framework** — exactly how `deprecated` works — and inheriting its hard-won rule
that *the count comes from the data and the declaration only says what to look for*
(`presentDeprecations`, `:50`), or a caveat printed for a field they stopped sending becomes the
next false absence. This side's commitment if it is adopted: the caveat renders **beside the
number, where the reader is standing**, never in a tooltip or another tab. Their shape wins if
they already have one — that is the standing rule on this track, not a courtesy.

**Their answer (W#139) confirmed the gap from their side and left the shape open, correctly.**
Measured on their contract: the success envelope carries `command, contractVersion, data,
deprecated, generatedAt, ok`, and `deprecated` is the only field-level signal — *"the field is
PRESENT but we no longer stand behind it"* (`scripts/set-api.mjs:99,111-115`), which is not
*"the value is right but its meaning is narrower"*. So there is **no prior shape to generalise**
and `caveats` really is new. Their guardian explicitly declined to commit a new envelope key on
the owning session's behalf — a new key is a contract-shape change, not a field name — which is
the same line this side draws.

Two consequences follow, and neither is a measurement — both were sent as observations (S#138):
this side cannot ship it same-day either, because a new envelope key is a contract change and
goes through OpenSpec; and **their own answer to "is the count a measurement or a floor?"
reshapes the question**. If the hand-written trailer makes the count *and* the age properties of
their register rather than the world, the caveat touches most of that surface's numbers, not one
or two — and a pure per-field list is then the wrong shape, because the entry that gets forgotten
reads as "this number has no caveat". That is the false absence again, entering from the other
side. A per-command default with per-field overrides ("every number here describes the register,
EXCEPT …") is likelier to survive maintenance. Theirs to decide.

**They took it (W#140), and their own example then contradicted their own rule — which is the
one thing left open.** The shape is agreed: a `"*"` key carrying the per-command default plus
per-field keys. Their stated rule is that a per-field key **overrides** `"*"`. Their example
does not survive it: `"*"` says *every number describes our register, not the world*, and
`kovetett` says *known LOWER bound — no trailer generation*. Under overriding, the reader of
`kovetett` loses the register caveat — the **more general and more important** of the two — and
reads a lower bound on the world. The direction is the deciding argument, not elegance: forget a
per-field entry under **additive** and the general caveat still stands (safe); override, and the
narrower sentence silently swallows the broader one (quiet loss). Asked in S#139; nothing gets
specified here until that one word is settled, because specifying a contract shape with the
wrong semantics costs more than waiting for a sentence.

**Their Q2 answer is UI input, and two items carry a commitment this side already owes them.**
Five fields read stronger than they claim: `GYANÚS` means *the text changed since the seal*, not
*wrong* — it asks for a re-look; `HATÁRSÁV`/`JELÖLT` are a **rank, never a verdict**, and the
threshold is computed from the run, so an unchanged item can move band (measured on their side:
258→238 items moved 4); `HALASZTVA` means *one person wrote a seal*, not a team decision;
`LEJÁRT_HALASZTÁS` means *the deadline expired*, not *the work is late* — they flag it as their
most misreadable field; and `items`/`artifacts` are lower bounds too. So the commitment recorded
here: under [ui-quality](../../.claude/rules/ui-quality.md)'s one-visual-weight-per-meaning rule,
**`LEJÁRT_HALASZTÁS` must not render as an alarm** and `GYANÚS` must not render as a failure —
if red means broken, neither of these is red. Also recorded: **no `ground truth` exists and none
will be asked for** — their matcher ranks 6/6 but its confidence band is 4/6, so there is no
"delivered" field and the framework must not expect one.

**Settled as ADDITIVE (W#141), and they withdrew the overriding rule in one line** — reaching for
the same direction-argument they already use elsewhere (an absent `type` means `BUG`; a NULL
channel means *never send mail*): the question is not whether it can be wrong but **which way**.
The `"*"` always applies and always shows; per-field keys **add**. No explicit-replacement
marker either — if replacement is ever needed it gets its own named field rather than becoming
the default's semantics.

Two corrections came with it that this side could not have found. The key names in their first
example were wrong: `stats` keys are **uppercase, accented Hungarian** (`KÖVETETT`, `GYANÚS`,
`LEJÁRT_HALASZTÁS`, …) while `bands` keys are lowercase unaccented (`egyertelmu`, …) —
deliberately different, and a caveat keyed on the wrong spelling **never fires and nothing
reports it**. And `stats` lists only the statuses **actually present**: today `KÖVETETT`,
`GYANÚS`, `HALASZTVA`, `LEJÁRT_HALASZTÁS` are all absent because they are zero and the seal file
is empty, so no UI here may assume all seven keys arrive.

**Measured here on their warning, and it holds: a mistyped key would be silent on this side too.**
`partitionKeys` (`web/src/components/statusShape.tsx:247`) counts only names it *found*, and the
Python path logs nothing for a declared-but-absent name. That silence was deliberate for
`deprecated` — counting from the declaration is the false absence this whole mechanism exists to
prevent — but for `caveats` the failure direction inverts: a mistyped `deprecated` key means a
stale field stays *visible* (unpleasant, visible), while a mistyped `caveats` key means the
caveat is *invisible* and the number is not. Exactly the outcome the feature exists to stop.

**The additive choice already absorbs most of that, which neither side noticed while choosing
it.** With a mistyped per-field key the `"*"` still renders, so the number carries the general
caveat and only the narrower half is lost; under overriding the same typo would have cleared
everything beside the number. The direction argument paid twice — once for a forgotten entry,
once for a typo.

**So the plan is diagnostics, not a gate.** The framework will not try to tell a typo from a
legitimately-absent key — their `stats` shape makes the two indistinguishable — but it can list
which declared caveat keys are absent from the current answer, where the producer recognises
`KÖVETETT` as legitimate and `KÖVETTET` as a typo at a glance. A gate firing daily on a
legitimately-zero status is dead within a week and takes the real warning with it.

---

## Constraints from the consumer's side that outrank set-core's ordering

These are the ones this side cannot see, and they were surfaced by asking rather than by
discovering them the hard way. They are why the goal reconciliation exists.

- **A commitment to their client comes first.** A release running on test and awaiting the
  user's approval for production outranks integration work. The integration must never be
  what blocks a release — which matters most for the later round, where set-core takes back
  development and the orchestration is reshaped.
- **The reshaping may not reduce what already works there.** Their pre-push gate chain,
  their OpenSpec `change → adversarial review → apply → archive` loop, and their Definition
  of Done are the proven foundation. An orchestration plan that replaces any of it with
  something looser is a wrong plan, however much more elegant it is. This is the flagship
  rule from `CLAUDE.md` applied to a concrete case.

## Where the confidentiality boundary actually runs — stated because the screen made it visible

The abstraction layer is domain-free, and stays that way. **Domain and infrastructure
content still crosses** — not as code but as data, rendered on set-core's screen: directory
paths, deployment settings, business rules quoted inside review findings.

That is not a violation, and pretending otherwise would make the feature impossible. The
boundary is **persistence, not visibility**: nothing read this way is written into this
repo, a committed artifact, a cache, or a log that can leave the machine, and the surface
runs locally. `CLAUDE.md` states the same rule; this paragraph exists because the consumer's
side asked for it to be said out loud while stopping was still cheap, rather than have it
surface later as a surprise.

The two carriers that cross it without anyone deciding to are named in `CLAUDE.md`: the
memory system's automatic session-end extraction, and diagnostic output on error paths.

## How the consumer actually releases — recorded because the channel is not a record

Asked before designing anything, per the rule that their mechanism is read first. Recorded
here in generalised form because the answers arrived on a channel that does not survive a
reboot, and because two of them change what should be built.

**The release opens at the START, not the end.** A script creates a *draft* release file
when the version is opened; features then write their own changelog line as they land. The
tag comes only after the closing commit, so the tag contains the release file describing
it. The test environment can receive the draft any number of times — the deploy runner is
environment-aware and refuses draft migrations against production — so nothing has to be
closed in order to test it. Closing is the "may go live" gate, and it runs a chain of them
(manual-sync, release-file validation, a bug-regression suite, spec archival, then build,
tests and a tagged E2E subset), each skippable only with a stated reason.

**What is generated and what is written by hand is a deliberate split**, not an accident of
tooling: the changelog list is generated from commit messages and then *curated* by a
person, while the description, the migration block and the manual post-deploy steps are
written by hand. A generated list that nobody curates is how a changelog becomes noise.

### The two answers that were uncomfortable, and are therefore the useful ones

**There is no mechanism deciding which release a fix lands in — timing decides.** Whatever
is ready while the draft is open goes in. A severity field exists and is filled in on every
fixed item, but it *controls nothing*: it is a label applied afterwards, not a decision made
before. Their own summary of the gap: no screen anywhere shows that high-severity bugs are
open **while a release is closing**. The past is recorded (which release fixed what); the
future is not.

**And the four work types do not split into four paths.** There is one path; chore, bug,
feature and hotfix differ only by label and by whether a manual post-deploy step exists.
They flagged this themselves as a shape *not* to generalise — it is not a principle, it is
that splitting has never hurt enough to be worth it. Which is exactly the warning this
track needs: the 2026-07-19 verdict's "missing piece is a router between differentiated
ADWs" is **not confirmed** by the most advanced practice available to us. What actually
varies there is whether a change needs a manual step afterwards and whether it is already
live — not what kind of work it was.

### A named candidate, found 2026-07-24 and deliberately NOT built yet

**A command that answers `ok: true` while reporting bad news is unmarked outside its own tab.**
Measured on this side: the tab strip's red mark keys on `!result.ok` (`ProjectStatus.tsx:288`)
and the "N of M failed" counter on the same condition. Both are correct for a command that
*fails*. Neither fires for a command that *succeeds* and whose data says something is wrong.

It surfaced when the consumer ran their full end-to-end suite for the first time and their
`tests` answer stopped being uniformly green: 296 passing, **2 failing**, 1 flaky, 8 skipped.
The command answers fine. A reader standing on the first screen sees calm.

This is the ui-quality rule's own failure mode — *compacting must never hide a failure* — in
the one place the rule was already applied once and stopped a level too early. The earlier fix
was about a **broken command**; this is about **bad news inside a working one**, and only the
first was closed.

**Corrected within the hour, by the peer, and the correction is larger than the finding.** This
entry said the marker is correct for a command that *fails*. Their measurement — from the
source of their envelope emitter, not from sampling its output — is that **no valid command can
ever fail**: the emitter hard-codes `ok: true` into every successful answer, and the single
`ok: false` in the file is the unknown-command / crash path. So `result && !result.ok` is not a
marker that *rarely* fires against their contract; it is one that **cannot** fire. And it is
not one command's problem: at one measured moment, **all eight read commands answered
`ok: true`** while their payloads carried release blockers, open high-severity defects,
unanswered reporter items, outstanding manual steps and a failed test artefact.

Two things follow, and the second is the reason this is recorded rather than left on the
channel. **The fix must be envelope-level and uniform**, because the property is — a
`tests`-shaped field would close one of eight and leave the screen calm over the rest. And a
per-instance finding proposed a per-instance fix: this side found ONE example and was about to
ask for a shape scoped to it. *The scope of a defect is a measurement too, and the side that
owns the producer is the one that can take it.*

**The shape a fix must take, so it is not solved by recognising a field name:** the project
declares which of its values are problem indicators, the same way it already declares
`deprecated` fields, `actions`, and the ordered `severity` of blocker rows. set-core still
knows no field name; it learns from the declaration what to count, and counts from the data —
the same split that stopped "1 deprecated field hidden" being announced about a field that was
never sent.

**Not built on purpose.** It arrived mid-change, from the peer's finding rather than from this
side's plan, and reacting to it immediately is the exact pattern both sides named the same day:
*two agents drift from the plan by answering each other's findings*, each next thing smaller
than the step being avoided. Recorded here so it survives without costing the current change.

**Its standing changed 2026-07-24 evening, and by the user rather than by a finding.** The user
asked what the next step is toward *releasing a version carrying most of the reported fixes,
chosen by severity and relevance*. That operation makes this the screen's decision surface, and
it meets the same two gaps: this candidate, and backlog item 1 below (*no screen shows a
high-severity bug open while a release closes*). They are one mechanism — the project declares
which values are problem indicators; set-core counts from the data. **Recommended to the user
as the next build, ahead of finishing the `bugfix` lane; no approval given yet, so nothing is
built.**

*Updated 2026-07-30: the recommendation stands and is still unbuilt, but the ordering it implied
does not hold, and leaving this sentence alone would have read as "the `bugfix` lane is waiting
for its turn".* It is not: this candidate extends the abstraction layer, which goal 3 says the
two sides design **together on the channel**, and the peer is blocked on their user's T16
approval. So it is the next build *and* unstartable, which is not a contradiction — it is why
the `bugfix` lane's implementation began on 07-30 (see item 4) instead of this.

### The first of those four gaps was closed by the project, the same evening

Backlog item 1 below — *nobody sees a high-severity defect open while a release closes* — had
a screen built for it, and the screen was **under-counting**. Their measurement: the
readiness answer stated three open high-severity defects while roughly eight were open, because
the number came from a file-and-CLI pipeline that a second reporting path never writes back
into. Nothing said the number was partial, which is what made it dangerous rather than merely
wrong.

**Their fix is the shape this whole contract keeps arriving at, and it is worth copying
verbatim in principle:** a `coverage` object — the source it counted, what it excludes, and a
plain `complete: false` — attached to the list AND, separately, to the blocker row derived from
it. Their reason for the duplication is the one this record has already made twice about
`deprecated`: *a warning living in another command does not protect the person reading this
number*.

Two further decisions of theirs are the durable part:

- **They put no COUNT in the code.** A quantity goes stale; the structure does not. The code
  says only that the set is incomplete, and one of their four guard tests exists specifically
  to forbid a hard-coded figure — the same defect this file has had twice in its own debt
  numbers.
- **They corrected themselves in public, twice, within twenty minutes.** The first report said
  eleven open including a critical; the correction found the status column was a proxy, not an
  authority, and that their own join was too narrow — *twice*, the second time while repairing
  the first. A correction that arrives in the same channel as the claim is what keeps a
  measurement worth building on.

**Nothing was asked of this side and nothing was needed** — the fields rendered unchanged (see
the property above). Their note for later: `coverage.complete: false` is an obvious candidate
for the problem-indicator declaration if and when that is built. Recorded as a candidate, not
as a design.

### Where state is lost today — the real backlog, in their words

1. **Bug priority against release timing.** Someone knows a high-severity bug is open at
   closing time. Nowhere does it show.
2. **The reporter's answer.** Now visible as a status field; before, invisible entirely.
3. **Test coverage state.** Dozens of spec files, none running automatically — a subset
   runs at release close. Until someone runs them, the word "green" means nothing.
4. **Why something was left out of a release.** Spoken, never recorded.

### The boundary, restated by them before it was asked twice

Nothing in their release should be *triggered* by set-core, and their reason is their own
rather than deference to this side's constraint: the only path to production is a push that
their CI promotes, and deploying from a local working directory would ship a snapshot
rather than a commit.

**The yardstick they proposed for every future write, and it is now the framework's:** the
acknowledgement was acceptable because it appends to a repository file and is therefore
structurally incapable of touching a live system. A write that reaches a database, an HTTP
endpoint or an external API is not covered by that argument and is refused until the
operator decides otherwise. Written into `project_status.write`'s docstring, where the next
person proposing a write command will read it — it cannot be enforced in code, because
set-core cannot know what a command it was told to spawn actually does.

## What mechanically enforces anything in set-core — measured 2026-07-24

Asked for by the consumer before proposing anything, on the sound argument that a proposal
is worthless if it recommends what already exists or what cannot structurally run here.
Measured rather than recalled, and the answer is uncomfortable enough to be worth keeping:

**Nothing gates set-core's own git flow.** No non-sample hook in `.git/hooks`,
`core.hooksPath` pointing at that same empty directory, no lefthook / husky / pre-commit
config, no CI workflow of any kind. Not "warns but lets through" — there is nothing there.

**What runs is observational.** Twelve Claude hooks across eight events, all memory,
activity or skill routing; a grep for the only blocking construct returns zero in all four
entry points.

**What does block points elsewhere.** The gate engine refuses merges of *agent worktrees* —
build, test, e2e, scope_check, test_files, review, rules, spec_verify, in run/warn/skip —
not what a person or an assistant commits into set-core itself.

**A finding that lands on the factory question.** Those gate sets are already differentiated
per change type — infrastructure, schema, foundational, feature, cleanup-before,
cleanup-after — each with its own mix. So the differentiation this track was about to build
**exists here already, on a different axis**: what the change touches, not what kind of work
it was. Combined with the consumer's "our four types are one path", the router idea was
wrong twice over, and the honest next move is to look at the axis that exists before
proposing another.

**The absence is not theoretical.** A pristine `HEAD` checkout runs 81 failed / 2983 passed
/ 21 errors, and nothing in the git flow has ever noticed, because nothing runs tests before
a push. The consumer's rule — "green means nothing until someone runs it" — applies here
more sharply than there: on their side a subset runs at release close; here not even that.

> *Corrected 2026-07-24, later the same day.* This line read **94 / 2631 / 21**, which is
> what `CLAUDE.md` still says. Both were true when written and neither is now — the passing
> count moved by 352 in a day. A debt figure is a **measurement with a timestamp**, not a
> constant, and quoting a stale one is how a real regression gets waved through as
> "expected". The check that actually works is the one the guidance already prescribes:
> **diff the failure SET**, against a `git worktree add --detach <dir> HEAD` baseline rather
> than a stash. Done for the lane gate: 106 entries on each side, symmetric difference empty
> in both directions.

**Their standard for gates, accepted before their research lands:** a gate is worth having
when it was born from *one measured failure*, named in its own header. Anything else is
ceremony. Whether set-core's eight gates can each name theirs is not yet known and is not
being guessed at.

## What was built, in order — and the one item still open (item 4)

**Read this heading before the list.** 292 lines, 40% of this file, and **six of its seven
items are finished**. Someone opening it to find "what is next" would read a completed
archive first, and a hurried reader would take an old item for a live one. The numbering and
the ordering are load-bearing anyway — each entry records *what a step cost*, which is why
the finished ones stay — so the fix is the heading and this note, not a split.

**Item 3d was the one that made this worth checking rather than assuming.** Its heading was
never struck through, so the list read "two open items", while its own last paragraph says
*"Goal 2's last item is met"*. Struck now. A list where the marker and the body disagree is
worse than one with no markers: the marker is the part that gets counted.

**Not renumbered and not split into two lists, deliberately.** `CLAUDE.md:44` points at
"items 1–3d of 'Next, in order'", and every completed entry is referenced by its number in
the reasoning above it. Renumbering would break every one of those to buy tidiness. The
general rule, one step past *renaming beats rescoping*: **rearranging is more expensive than
rescoping when anything cites the old order.** New items go on the end.

**One live item: 4, the factory layer.** Everything numbered below it is history.

1. ~~**The acknowledgement surface.**~~ **Built and measured as far as the API; the click
   itself is not proven** (see "still unproven" below — this qualifier is in the marker
   because that is the line a hurried reader counts). The pain the consumer measured was state
   that lives nowhere: manual post-deploy steps existing only in one person's memory, per
   environment. They are now listed, and each offers a button.

   **What the write path is, in one line: set-core never writes — it asks the project to
   record.** Reads and writes are separated all the way down (declared list, function,
   endpoint) rather than distinguished by a flag, because reading everything the project
   offers happens on every page load, and a single list with a "this one mutates" attribute
   is one refactor away from a page load acknowledging something.

   **The affordance is declared, not derived.** The project attaches `actions` to the rows
   where a write applies, with the arguments already computed. A path language was rejected
   by both sides: its failures are silent, and both sides would have to maintain it.

   **The confirmation states what the record is** — a statement by the person clicking, not
   a measurement, verified by nothing. Not ceremony: the consumer produced a stray record
   for a check nobody had performed, and this is the only place a person is told before
   asserting it.

   **Proven as far as it can be without asserting something false.** The consumer's write
   command takes a repo argument, so the whole chain was run against a disposable copy:
   the write returned ok with the chosen environment in the record, an identical second
   write returned `alreadyAcknowledged` and the file stayed at ONE line, and the real
   repository was untouched (no record file, empty `git status`). Idempotence is therefore
   not a promise on this side either — it was measured through this API.

   **What is still unproven, precisely:** the browser's own fetch. Everything from the API
   inward is measured; the button's argument merge is unit-tested; the click itself is not,
   because a real click writes into the consumer's repository.

   **And the first real acknowledgement should stay what it is — a person who actually did
   the task, not a demonstration.** The consumer already produced one stray record for a
   check nobody had performed. A demo write into the real store would be a second.

   **The dangerous edge was checked, not assumed.** When every environment of a step is
   acknowledged, the project drops the *whole* `actions` key — not just the list of
   choices. Measured on a disposable copy by acknowledging both. Had only the choices
   gone, the button would have become **enabled** (nothing left to pick, so nothing to
   wait for) and would have written a record with no environment. A false affordance is
   the same family as a false absence, and it is invisible from either side alone: their
   side sees a correct payload shrink, this side sees a button whose disabling reason
   vanished.

   **Closed by the project, and their reasoning is the part worth keeping.** A fully
   acknowledged step used to stay in the list named for open steps, so the count never
   shrank. They kept the row and made the *count* derived, rather than dropping the row —
   because an acknowledgement is a human assertion, so a mistaken one must not be able to
   make a step vanish without trace. That would be a false absence at the worst possible
   scale: not a field, a whole task. **The array is the record; the number is a
   derivation.** Their state field is three-valued for the same reason the reporter trace
   is four-valued — a two-valued one would render half-finished work identically to
   untouched work, and lose it.

   **The same warning found a lie on this side.** The renderer printed its own count above
   every table — "15 items" — under a key the project names for open steps, which reads as
   "15 open steps". Once the project publishes its own open-count, one screen carries two
   numbers about one thing that disagree the moment anything is acknowledged. Fixed by
   changing the subject, not the logic: it counts **rows**, which cannot be read as a claim
   about what the rows mean (`67d64a21`, both tests fail with the fix stashed).

   *The general rule, and it is not only about counts:* **a domain-free renderer inherits a
   subject from the key above it.** Being ignorant of field names is not the same as
   asserting nothing.
2. ~~**The test *system*, not just the test environment.**~~ **Done on the consumer's side,
   and it appeared through set-core with zero framework changes** — the second time the
   declaration-driven design has been confirmed, and the first time deliberately.

   **How the trap was solved is worth keeping**, because the answer was not the obvious one.
   The stale artefact — a last-run summary reading `6/6 passed`, a day old, covering a
   subset of 62 spec files — was not hidden. It was made *measurable*: no `ok` field at all
   (an `ok: true` would headline "our tests are green" about a sixth of them), `scope: null`
   because the artefact does not record what was filtered, and **`commitsSince`** as the
   load-bearing field. Time alone misleads — a three-day-old result is still valid if
   nothing was committed since — whereas commit distance does not. A test asserts the `ok`
   field stays absent, so a later "helpful" addition cannot smuggle it back.

   *The general rule, worth applying beyond tests:* **age misleads, distance from the tree
   does not.**
3. ~~**The reporter-feedback trace.**~~ **Delivered on the project's side and live through
   here — the fourth time a new field arrived with zero framework changes.** Measured:
   67 rows carrying a four-valued status, and a summary whose four counts sum exactly to
   the total (6 sent / 12 pending / 6 unmarked / 43 not-applicable = 67). The summary was
   checked against the rows rather than taken on trust, which is the same discipline the
   count-vs-list pair needed elsewhere.

   **Four values, not two, and the reason generalises:** a boolean would render work that
   is half-done identically to work nobody has touched, and lose it. The same argument
   produced the three-valued acknowledgement state.

   Note carefully what the measurement does and does not prove: it shows an answer is
   *unverifiable*, not that it was never sent.
3b. ~~**Which answer opens the surface.**~~ **Shipped** (`e7b0051e`). A contract that keeps
   growing eventually opens on whatever was declared first, which is an ordering decision
   nobody made. The project now declares `primary`; set-core never infers it from a name,
   because a name is not a promise about content. Absent stays absent rather than becoming
   "the first one", so *the project chose this* and *nobody chose* remain distinguishable
   — the same false-value shape as the row count, one level up. A write command named as
   primary is refused outright: opening a page must never land a reader on a mutation.

   It exists because the *readiness* answer below will need somewhere to land, and it cost
   nothing to build first — but it is useful to any project with more than a couple of
   answers, which is the test for whether something belongs in the framework at all.

3c. ~~**The missing screen the consumer named.**~~ **Done, and it is the sharpest form of
   this track's acceptance test so far.** Their gap was that no view showed high-severity
   bugs open *while a release is closing*. The split held: the derivation is theirs, as one
   more read command; the framework's half was `primary`. Verified in a browser rather than
   inferred from config — eight tabs, exactly one selected, the declared one, zero JS
   errors, and the motivating sentence sitting on the first screen without scrolling: three
   open high-severity bugs, with stable identifiers, beside an open draft release.

   **Zero framework changes, for the fifth time.** The mechanism was in place two hours
   before the project declared it.

   **The design decision worth carrying to every project:** their answer has no `ready`,
   `ok` or `green` field at all, and a test forbids one. Not because the data is missing —
   because two of the closing gates and the full end-to-end suite can only be decided by
   *running* them, so any summary verdict would assert what nobody measured. The contract
   says instead: an empty blocker list means no KNOWN blocker, and here is the count of
   things not measured. Most dashboards lie exactly here.

   **One caution passed back to them:** such an answer must not carry a green test claim.
   Nothing runs their spec suite automatically, so "E2E fine" would assert what nobody
   measured. If it appears at all it should carry last-run time and commits-since — the
   shape they already got right elsewhere. *Age misleads, distance from the tree does not.*
3d. ~~**The live system is still an address, not a state**~~ **Closed — it is a state now.**
   It was the last item of goal 2 to be met. At the time this was written the project
   published both environments' URLs and a permanent
   null for whether they answer, because probing them takes minutes and a page load cannot
   pay that. The test *system* was solved; the live *system* was not, and the difference is
   exactly the one the user corrected earlier: a place versus a state.

   **The framework half is built** (`567b4111`): a project may declare read commands as
   on-demand, and the surface then shows the tab with an "ask now" button instead of
   running it on load. What it narrows is only what happens BY ITSELF — asking by name
   still works, which is what the button does.

   The care went into what it must not become. The tab stays, because a reader cannot ask
   for what they cannot see; an unasked answer is not counted as a failure, which would be
   the false-absence shape in the one place it would be believed; it gets a quiet mark
   rather than a red one, because red must stay reserved for broken; and the fetched answer
   is held apart from the page-load data, since an answer that vanishes on the next refresh
   reads as a failure. An absent declaration means today's behaviour, verified live.

   **Declared by the project, and then measured — which is how the gap in it was found.**
   The page load now asks seven commands instead of eight, correctly. But pressing the
   button returns in **zero seconds** with the same permanent null, because the expensive
   probe needs a flag nothing sends. **That is a false affordance, and this side built it:**
   a reader who clicks and sees nothing concludes the probe ran and found nothing, rather
   than that it never ran. Recorded rather than quietly waited out, because a half-built
   affordance is exactly what a later session mistakes for a finished one.

   **The framework's remaining half is now built too** (`8f91b4b2`): per-command timeouts.
   Even once the probe runs, the global 30s would have killed a call measured at 118–286s —
   so the mechanism built for this one answer would never once have delivered it. One
   number cannot serve both kinds of question, and the failure is asymmetric: a raised
   global lets a hung fast command hold the page, while a global that fits the fast ones
   makes the slow answer permanently unobtainable — on screen indistinguishable from a
   project that cannot answer it.

   **Closed, and not the way either side planned.** The project measured the number this
   whole design rested on and found it wrong: the "118–286s" was a CI pipeline's duration
   lifted from another document into a field meaning "how long does this take", and a 400s
   timeout was being sized against it. What the question actually needed was one HTTP call,
   so they published a separate `health` command instead — **9 commands, 0 gaps, 1.5
   seconds for the whole page load**, and the on-demand flag was withdrawn as unnecessary.

   **Goal 2's last item is met:** the live system is a state now, not an address. It
   reports reachability, HTTP status, latency, and **which commit is actually running** —
   the same rule this repo learned the hard way, that a shipped commit is not a running
   system.

   *Two lessons worth more than the feature.* **A duration is a number like any other**, and
   this side accepted it without asking how it was measured, while demanding exactly that
   discipline of everything else. And **the error's direction is why nobody would have
   caught it**: a wrong number that suggests a LARGER timeout breaks nothing — it just lets
   a stuck command hold a page for minutes. Slow, quiet, invisible.

   The per-command timeout stands but is honestly unused: no project declares one today, and
   the need it was built for was measured away. It is available, not vindicated.

4. **Then the factory layer proper** — planning releases and bug fixes inside set-core.
   Its shape is the router between differentiated ADWs already identified in the
   2026-07-19 verdict, not a new system.

   **All five scoping questions are now answered** (recorded above), and two of the answers
   removed work rather than adding it: there is no four-way router to build, and nothing
   should be triggered from here. What remains open is the axis the differentiation should
   actually follow — theirs varies by *whether a manual step is needed and whether it is
   already live*, while this repo already differentiates by *what a change touches*. Those
   are two real axes and neither is the one that was planned.

   **Started 2026-07-24, by the consumer, on the "plan a bug fix" half** — the goal's least
   covered verb. Their finding, and it is the kind that only shows up once the data is
   joined: of 23 open bugs, **22 have no change referencing them at all**. The data existed
   the whole time (45 openspec files cite stable bug ids); nothing had ever put the two
   sides next to each other. Two fields carry it, deliberately not merged into one:
   `plannedIn` (an **active** change references the bug) and `wasPlannedIn` (only an
   **archived** one does — "we believed it closed, and it is open"). Merging them would
   erase exactly the discrepancy that is worth seeing.

   **The set-core side was zero work** (see D2), which is now the seventh confirmation of
   the declaration-driven design and the reason it is recorded as a property rather than a
   result.

   The design still belongs on the channel; what has started is the *data*, not the
   framework's shape. Starting the router here now would still be the parallel design the
   user ruled out.

   **Opened on the channel 2026-07-24 (S#78), and the reason it took this long is the
   finding.** For roughly an hour both sides did real, measurable work — three false
   blockers removed on theirs, four gates and a renderer gap on this one — and none of it
   advanced this item. It hardened the item before it. Neither side was wrong and neither
   noticed, because mutual defect-finding produces a steady supply of legitimate next
   things to do, each one smaller than the step being avoided. Their substantive path is
   genuinely blocked on two user decisions; this side's was not blocked, only unopened.

   **The axis question was premature, and this record is why it got asked.** It went to the
   channel; the consumer declined to answer it — correctly — because "router" is this
   repo's word and they will not guess at a definition. Going back to the source to write
   one produced the actual answer, which was in the verdict all along and *not* in this
   entry: **build the differentiated pipeline first, and alone. Not the router.** The
   taxonomy comes "only once two provably different pipelines exist to choose between", and
   the verdict names the failure of doing it the other way in its own words — *"the router
   gets built and has nothing distinct to route to… a taxonomy with near-zero behavioural
   delta is a false gate, and this repo already has three."*

   So the axis cannot be chosen yet by anyone, on either side, because what it would sort
   between does not exist. The question is withdrawn rather than left open.

   *What this entry had lost:* it carried the verdict's finding (the missing piece is a
   router) without the verdict's **ordering constraint** on it. A summary that keeps the
   conclusion and drops the precondition reads as a green light — which is exactly what it
   did. When quoting a verdict here, quote what it forbids alongside what it identifies.

   **The consumer's working differentiation, supplied on the channel 2026-07-24 (W#88),
   measured by them from `lefthook.yml` and the gate headers rather than recalled.** This is
   the input the verdict's ordering constraint was waiting for: something real to generalise,
   instead of a taxonomy invented here. It does not look the way a pipeline designer would
   expect, and every departure is load-bearing:

   - **Nothing classifies the work. The lane becomes apparent from narrow mechanical
     signals**, each watched by its own gate, each silent by default: a NEW non-test source
     file (silent if an OpenSpec change is touched or a valid trailer names one); a bug
     marked fixed whose stable id no test references; a checked-off task with no review
     artefact. There is no classifier at the entrance, so nothing has to be right about a
     change before work starts.
   - **The signal is deliberately NOT diff size.** Their gate header says it outright — a
     400-line generated enum update is trivial and a 12-line predicate change in payment
     matching is not, so line count measures the wrong thing. A NEW MODULE, by contrast, is
     almost by definition a new capability. *Find a **shape** that correlates with risk;
     never classify by quantity.*
   - **The two lanes are asymmetric, and that is the design rather than a side effect.**
     Feature lane: OpenSpec mandatory → adversarial review → delta spec → archive; an
     expensive **entrance**. Bug-fix lane: no OpenSpec (most fixes restore conformance to a
     spec that already says the right thing) but a regression test is mandatory, citing the
     bug's stable id; a cheap entrance and an expensive **exit**. In one sentence: *the
     feature lane gates whether we are building the right thing; the bug-fix lane gates
     whether it can come back.*
   - **One human question decides the lane** — "does this fix restore what the spec says, or
     change what it should say?" — and the machine only checks afterwards. Restoring needs no
     spec update; changing behaviour is a spec change in disguise and carries its delta in
     the same commit. So their side has no router either: one question and three retrospective
     checks.
   - **Introduction lessons, which are the part most pipeline designs omit.** Every lane
     signal ships with a baseline file that **can only shrink** — without it there are dozens
     of hits on day one and the gate gets switched off, so the baseline is the debt register,
     not a concession. Every gate starts as WARN with a **measured** promotion condition
     ("two consecutive weeks with at least half the signals real"). And every gate states its
     scope: theirs does not run on `main` pushes, where it would judge weeks-old work and
     produce noise. *A gate without a stated scope evaluates twice and inflates its own
     baseline.*
   - **The lane detector is itself a scanner**, so today's finding applies to it: put the
     rule's own examples under `src/` and the gate reports itself (S#88). **A lane detector's
     corpus must never contain the lane's definition.**

   **What this side does with it, decided 2026-07-24 under the delegated mandate:** build the
   differentiated pipeline, alone, as the verdict orders — and via OpenSpec, per the rule
   adopted the same day. The abstraction to generalise is *lane detection from declared
   mechanical signals, with per-lane gate chains that are asymmetric by design*; the signals
   themselves are project data and stay on the project's side, exactly like every contract
   command. **Not** the router, and **not** their specific three signals lifted into Layer 1
   — a design that only works for one consumer is not finished.

   **The instrument shipped 2026-07-24 (`lane-contradiction-detection`), and the pipeline is
   now specified — proposal, design, specs and tasks, no code** (`bugfix-lane-with-a-real-delta`,
   `openspec validate --strict` clean). Three things were decided and each reverses what looked
   obvious, so they are recorded rather than left in the change:

   - **The first draft was on the wrong footing, and a goal-alignment re-read of THIS FILE
     caught it.** It opened a `UNIVERSAL_DEFAULTS['bugfix']` entry — taxonomy first, which the
     verdict's ordering constraint forbids. What rescued it was the consumer's answer rather
     than the retreat: **a lane entry is admissible when it CANNOT exist without its delta.**
     A `bugfix` declaration carrying no enforced exit obligation is refused, so the entry is
     structurally incapable of becoming a fourth empty name. That satisfies the ordering
     constraint instead of evading it.
   - **Refuse, never substitute — and the reason is not danger.** Falling back to the feature
     chain is *stricter*, so nothing breaks. The harm is belief: the project declared a lane,
     believes it has one, and silently runs an ordinary change. Their argument, and it names
     the class this record keeps meeting — a marker true of a narrower subject than its reader
     takes it for.
   - **The project maps its vocabulary onto set-core's change types, in one place.** Comparing
     `LaneSignal.lane` to `change_type` was rejected a second time, having been rejected once
     inside the reader: that mapping is domain. The two vocabularies happen to overlap in this
     one consumer, which is the worst available reason to build a coupling on the overlap —
     and it is exactly the implementation a later reader reaches for, so a task asserts nothing
     does it.

   **Measured defects found while specifying it, all pre-existing:**
   `UNIVERSAL_DEFAULTS['feature'] == UNIVERSAL_DEFAULTS['foundational']` is `True` — the
   verdict's zero-delta failure already in the tree, unnoticed until measured; the type list
   lives in three places and two disagree, with `merger.py:2442` exempting `config` and `docs`
   which exist nowhere else; and an unknown type is **stricter**, not looser, so today's
   `bugfix` runs the most conservative chain and anything done here is a loosening that must be
   bought rather than spent.

   **A scope REMOVED on their measurement, recorded because a removal needs its reasons as much
   as an addition or the next reader restores it.** The natural thing to generalise was their
   entrance question — *does this fix restore what the specification says, or change it?* Their
   figures: **50 of 536 `fix(...)` commits touch a specification or the knowledge store
   (9.3%)**, a named incident where a specification described automatic behaviour while the code
   was deliberately manual for two weeks and was never annotated, and the gate intended to
   enforce it does not exist in their tree either. They asked that the half they demonstrably do
   not keep not be generalised. **A framework gate enforcing what the most advanced available
   practice cannot keep does not protect anyone — it gets switched off and takes the warning
   with it.**

   **The price, stated so it is not softened later:** an exit obligation counts only at ENFORCE
   severity, and lane signals reach ENFORCE only through their own recorded measurement. So a
   project cannot obtain the bugfix discount on day one — it runs the signal at WARN, earns the
   promotion, and only then does the entrance get cheaper. The evidence is the price, which
   means it cannot be paid afterwards.

   **IMPLEMENTATION STARTED 2026-07-30 14:13 — and the decision to start it is the part worth
   recording, not the start.** The user said only *continue*, on a track where decisions are
   delegated (`CLAUDE.md`, 2026-07-24: *a mandate to choose, not to guess*). Two builds were
   candidates and the record's own recommendation was the **other** one — the problem-indicator
   declaration, recommended to the user on 07-24 evening with no approval given. What decided it
   is not preference but **which one is reachable**: the problem-indicator work is an extension
   of the abstraction layer, and goal 3 requires the two sides to design that *together on the
   channel*; the peer is blocked on their own user's T16 approval, so starting it here would be
   precisely the parallel design the user ruled out. This item needs nothing from them. So the
   recommendation is not overturned — it is **still the next build once the channel unblocks**;
   it was simply not startable, and an unstartable recommendation is not a reason to idle.

   **BUILT 2026-07-30 — 24 tasks, 8 acceptance criteria, `openspec validate --strict` clean,
   failure-set diff against an isolated baseline empty (81 failed / 3180 passed / 21 errors here
   against 81 / 3121 / 21 there, +59 new tests, 0 import leaks with the leak checker proven able
   to fire).** Three commits: `8a7a85bd` (one home for the type list), `fcb072f6` (the
   conditional lane), `1ce55967` (the hole in the first two).

   **The delta is one gate, and the argument for it is in the code where the profile lives:**
   `bugfix` softens `test_files` from blocking to warn, and nothing else. `test_files` asks *did
   this change add test files*, which is a **proxy**; the exit obligation asks whether a fixed
   defect has a test citing it, which is the thing. So the entrance drops the proxy exactly where
   the exit measures the property. `spec_verify` stays blocking on purpose — softening it would
   assume a fix restores the specification, which is the question D4 refuses to gate on after the
   consumer measured their own compliance at 9.3% and asked that the half they do not keep not be
   generalised.

   **ONE QUESTION IS NOW OPEN AND IT IS THE CONSUMER'S TO SHAPE — measured, and it makes the
   feature unusable by the project it was built for.** `require_exit_obligation` requires the
   mapped signal to be able to *fail a gate*, not merely to sit at ENFORCE (see below for why).
   Two routes qualify: a registered condition handler — and the handler table is empty by design
   in this version — or the project declaring `sole_enforcement`, which means *no other gate of
   ours enforces this defect class*. The consumer's blocking gate **does** enforce it (they
   confirmed the predicate against their own gate source on the channel, W#142), so their honest
   declaration is `false`, and they are therefore **ineligible for the discount precisely because
   their own gate works**.

   The fail direction is the safe one — a discount refused, never granted unpaid — so nothing is
   at risk while this is open. But the obligation *is* enforced in their case; it is enforced
   somewhere set-core cannot see. Closing that needs a declaration set-core does not have ("our
   own gate enforces this class"), and an unverifiable claim is a contract-shape decision, not an
   implementation detail. **Asked on the channel rather than decided here**, because goal 3 says
   the two sides design this layer together and this is exactly that kind of question.

   **Answered within five minutes (W#143), and the answer was better than the question — no new
   declaration is needed, because the value is READABLE.** Their `bugs` command already carries
   `hasRegressionTest` per row, produced by the very gate in question. So the framework does not
   have to believe a claim; it reads the verified result. That is their own iron rule — *the
   abstraction reads the value, it does not turn it into an assertion* — and it lands on a shape
   set-core already has: the lane signal's `answer` delegation (`{command, field}`), whose
   docstring says exactly this, that the project publishes the answer and the gate asks instead of
   recomputing.

   **Their answer also found a defect in code shipped forty minutes earlier** (`725bfedb`):
   `_can_block` knew two of the three routes by which a signal can fail a gate and omitted
   delegation, which `lane_gate.py:197` tries *before* any handler and independently of the handler
   table. So the one route a project already publishing the value would use was precisely the one
   disqualified. Safe direction again — a discount refused that had in fact been paid — and
   therefore invisible from inside. **The channel's best-paid-off property, once more: the other
   side stands on a different corpus.**

   **One measured shape constraint stands between the idea and the wiring, and it is recorded here
   because it decides who does what.** `lane_gate.py:151-168`: `answer.field` must resolve to a
   **list of stable identifiers**. A non-list is refused (*a count cannot be baselined and cannot
   be excluded*), and so is a list of structured entries (*the baseline AND the exclusions both
   match on the identifier, so a structured entry escapes both silently*). Their per-row boolean
   inside a list of objects is therefore not readable as-is, and a projection inside `field` is
   deliberately forbidden — that would be their rule re-expressed in set-core's syntax, which is
   the second implementation the delegation exists to prevent. **What works with zero framework
   change: they publish the already-decided list of bug ids** — type `BUG`, fixed, no regression
   test — under one plain dotted path. The granularity their side warned about then comes out right
   by construction: the list is per-bug and the id is what baseline and exclusions match on, rather
   than the per-change proxy. Proposed as S#143; theirs to accept, and **nothing is being built on
   either side until their user approves.**

   **CLOSED the same hour (W#144), and the shape was already shipped on their side — nothing is
   needed from either project.** They conceded the shape half of their own previous answer (a
   per-row boolean is genuinely unreadable here) while the direction half stood, and then measured
   that the bare-identifier list this side asked for **has existed in their contract since
   2026-07-24**: `data.laneSignals.fixedWithoutRegressionTest`, a list of ids, contract-recorded
   rather than ad hoc. So the delegation is expressible today with **zero framework change and zero
   new field**: `answer: {command: "bugs", field: "laneSignals.fixedWithoutRegressionTest"}`.

   **The `onBaseline` question is answered by their shipped code: the baseline is subtracted on
   their side.** Their list is `fixed && !covered && !baseline`, with the known debt carried in a
   separate field. So set-core's own `baseline` declaration is correctly EMPTY for this signal —
   no double handling, and the baseline-growth check raises no false alarm. Recorded as their
   measurement, not as an inference from it.

   **Verified here rather than believed, and the verification is the part worth keeping.** The
   delegation shape was already covered by `test_lane_delegated_answer.py`. What was NOT covered is
   the join: `require_exit_obligation` answers *is there a route by which this can block*, which is
   eligibility — and eligibility is compatible with nothing ever running. That is this repo's own
   mechanism-verified-result-silent class, so one test now pushes the same tree, signal and
   declared answer through **both** halves: the lane is granted, and the gate then really invokes
   the published command and fires on the identifier it returns (`3c23a938`). Proven non-vacuous by
   removing the delegation branch and watching it fail.

   **What remains is a single user decision on their side, and its shape changed for the better:**
   not *should this be built* — it is built on both sides — but *should it be wired up*. Nothing is
   wired, and their user has approved nothing.

   **Its three measured premises were re-checked before any code, not carried forward from the
   paragraph above** (the record's own rule: on resuming, re-check rather than re-derive):
   `python3 -c "from set_orch.gate_profiles import UNIVERSAL_DEFAULTS as U; ..."` →
   `feature == foundational` is **True** and is the **only** identical pair among the six keys;
   `merger.py:2441` still exempts `('infrastructure', 'config', 'docs')` while `config`/`docs`
   exist in no type list; `.claude/skills/set/decompose/SKILL.md:68` still hand-writes the same
   six names. Also measured, and it is the reason nothing is urgent here: **`bugfix` is not a key
   in `UNIVERSAL_DEFAULTS` at all**, so today it resolves as an unknown type and runs the
   *strictest* chain — everything this change does is a loosening that has to be bought.

**Where it runs:** locally. The user has ruled that set-core, the consumer's build, and
`claude -p` agents keep running on this machine; nothing new moves into CI. What is already
in CI stays there. This *tightens* the production constraint rather than loosening it — the
consumer's CI is their only path to production, so adding no step to it means there is
nothing to trigger by accident.

---

## Keeping the two sides aimed at the same thing

The user asked for this explicitly, and it is not redundant with talking a lot. Divergence
between two agents does not show up as an argument — it shows up months later as two
different next steps, each defensible on its own side. So the goals get reconciled
periodically, item by item, against what the *other* side says the next step is.

**The mechanics:** the goals are stated numbered on the channel so they can be refuted
individually rather than agreed with in general, and a recurring check compares
consequences (is the next step the same? the same order? does their side carry an
obligation mine does not know about?) rather than wording. It stays silent when the two
sides agree — a check that chatters gets ignored, which is the same as not having one.

**Watch for the asymmetry:** their side has commitments — a client, a deadline, a quality
gate — that this side cannot see and that can outrank set-core's ordering. Ask for those
before building on an ordering, not after a half-finished surface.

**The channel's best-paid-off property is not the one it was built for, and this is the
argument to reach for when its cost is questioned.** It was set up to exchange information.
What it actually kept catching, three times on 2026-07-24 alone, is *a good check run on a
corpus it was never written for, returning a confidently wrong number*:

| the check | the wrong answer | what it was |
|---|---|---|
| a secret scanner over source code | 118 findings | every one a `token`/`password` identifier |
| two proxies for "carries a rationale" | 14/19 | misclassified in **both** directions; reading them gave 18/19 rationale, 14/19 dated |
| completeness words over a whole test suite | 268 findings | all describing asserted behaviour, not mechanism coverage |

Each was caught by the *other* side — not by being more careful, but **by standing on a
different corpus**. Neither side could have found its own, because the blind spot is the
corpus, and you cannot notice the corpus you are standing in. That is not redundancy
between two readers of the same record; it is the one thing a second reader of the same
record could never provide.

The transferable discipline that came out of it: **"I looked and there is none" is weak
regardless of whether it is true.** State the corpus and the pattern, so the negative result
can be re-run instead of believed. That is what separated every real finding of that day
from an impression.

## Resuming after a compact or a fresh session

The negotiated agreements are here; the conversation is not. The channel rebuilds the
contact — see the cross-project channel section in `CLAUDE.md` for how to find it, catch up,
and check (never blindly re-arm) the watches. *(Corrected 2026-07-29: this said the channel
is `/tmp`-lived, which stopped being true on 07-24 when both sides moved it to
`~/.local/share/set-core/channels/<slug>/`. The move updated `CLAUDE.md` and the running
watches and left this page behind — exactly the second-place defect that move was documented
to avoid.)*

**Both watches died at once, and it cost five days of silence — recorded because the failure
is silent by construction.** Measured 2026-07-29: `pgrep -f 'NEW=.*<peer file>'` returned two
hits, **both aged `00:00`** — the measuring command's own processes, so zero live watchers —
and `CronList` returned no jobs. The last entry on this side was 07-27T08:34; the consumer
wrote twice on 07-28 and got no answer. Nothing anywhere reported a problem, because a dead
watch and a quiet peer produce identical evidence: no notifications.

Two things follow. **The Monitor and the cron are not redundant if they die together** — they
died in the same session end, which is the common cause neither guards against. So the check
on resume is not optional and not satisfied by "the Monitor survives a compact" (it does; it
does not survive the session). And **the peer is the only external detector**, which is why
S#136 asks them to prod after 24 hours of silence on an entry that concerns this side. A
watch nobody can see failing needs a witness outside the process.

**And the cron fallback armed in response was deleted the same evening, because it does not
guard the failure it was armed against.** Reasoned from the measurement above: the Monitor
and the cron are *both* session-scoped, and they died from the same cause — the session
ending. A second watcher inside the process that dies cannot witness that process dying. So
its protection was zero against the one failure on record, while its cost was real: it fired
every 13 minutes, and the harness requires a visible reply, so the "say nothing when there is
nothing to do" instruction could not be honoured. That is the rule book's own warning
arriving — *a fallback that chatters gets muted* — except it gets muted by irritating the
user, which also mutes the honest signals next to it.

What actually covers the gap is not another timer: the **peer** (S#136 asks them to prod
after 24 h of silence on an entry that concerns this side — a witness genuinely outside the
process), and the **resume check** in `CLAUDE.md`, which is where a new session already
looks. A guard that only fires while the thing it guards is healthy is decoration.

One rule from that section is worth repeating because it was learned expensively: **a word
like "measured" obliges showing the evidence.** A plausible guess crossed this channel, was
reasonably taken for a measurement, and reached both projects' rule books before anyone ran
the one-line check that disproved it. The same failure recurred four times in one day on
formatting fields — SHAs, counts, timestamps — precisely because nobody reads those as
claims. *If a field is machine-processed, it cannot be "formatting", however much it looks
like it.*
