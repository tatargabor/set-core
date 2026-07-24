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

  **One shape question is on the channel, not decided here:** their declaration calls the
  field `published_answer` and names three fields for set-core to combine
  (`data.bugs[].hasRegressionTest` + `.onBaseline` + FIXED status). Combining them IS the
  reimplementation the rule forbids, so the ask is that they publish the already-decided list
  under one path. That is a request about what they expose, never about how their gate works.

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

### The property this keeps re-proving, measured seven times

New producer fields reach the screen with **zero framework changes** — most recently 67 bug
rows carrying two new planning fields, and a blocker carrying a nested list plus a nested
table (`plannedIn` on 4, `wasPlannedIn` on 22). This is no longer a pleasant surprise; it is
the contract's defining property, and the useful inversion is: **the day a new field needs a
framework change, a name has been burned in somewhere, and that is the bug** — not the field.

### Still open

| Decision | Owner | State |
|---|---|---|
| Whether a derivable list stays in the contract | consumer | measured: nothing here depends on it, so it is theirs to decide — and the row's height is this side's problem to fix, not a reason to drop their field |

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

The negotiated agreements are here; the conversation is not. The channel is `/tmp`-lived
and rebuilds the contact — see the cross-project channel section in `CLAUDE.md` for how to
find it, catch up, and check (never blindly re-arm) the watches.

One rule from that section is worth repeating because it was learned expensively: **a word
like "measured" obliges showing the evidence.** A plausible guess crossed this channel, was
reasonably taken for a measurement, and reached both projects' rule books before anyone ran
the one-line check that disproved it. The same failure recurred four times in one day on
formatting fields — SHAs, counts, timestamps — precisely because nobody reads those as
claims. *If a field is machine-processed, it cannot be "formatting", however much it looks
like it.*
