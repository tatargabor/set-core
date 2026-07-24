# Consumer ↔ set-core integration — the living record

**This is the highest-priority track while it is open.** It is also the one most likely to
be lost, because it spans two repositories, two agent sessions, and a `/tmp` channel that
does not survive a reboot. Everything durable about it lives here.

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
**`/tmp` channel itself** (evaporates on reboot). This file is the only carrier that is not.

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

- **Envelope v1**: `{contractVersion, generatedAt, command, ok, data}`. An unsupported
  version is refused *before* spawning anything.
- **Precedence**: operator config beats the repo manifest. The person present when
  something is wrong must be able to redirect it without editing someone else's repo.
- **Read and write are separate namespaces.** Write commands live in their own list
  (`writeCommands`), are never cached, and a generic renderer walking the read list can
  therefore never call one by accident.
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

### Still open

| Decision | Owner | State |
|---|---|---|
| — | | nothing open |

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

## Next, in order

1. ~~**The acknowledgement surface.**~~ **Built.** The pain the consumer measured was state
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

   **Left open, and it is the project's call because the derivation is theirs:** a fully
   acknowledged step *stays in the list named for open steps*. The count does not shrink —
   15 before, 15 after, one of them recorded as done in both environments. The refuting
   field sits inside the row, but the number is what a person reads, so the refutation is
   not where the decision is made. Reported; not patched here, because filtering rows by
   their meaning is domain logic and it belongs on the side that holds the data.
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
3. **The reporter-feedback trace.** Same class — a step the process requires and
   nothing records, so it cannot be checked. Note carefully what the measurement does and
   does not prove: it shows the answer is *unverifiable*, not that it was never sent.
4. **Then the factory layer proper** — planning releases and bug fixes inside set-core.
   Its shape is the router between differentiated ADWs already identified in the
   2026-07-19 verdict, not a new system.

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
