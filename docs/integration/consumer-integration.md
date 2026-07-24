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

## Next, in order

1. **The acknowledgement surface.** The pain the consumer measured is state that lives
   nowhere: manual post-deploy steps that exist only in one person's memory, per
   environment. The read side already shows them. The button waits on the storage decision.
2. **Second: the reporter-feedback trace.** Same class — a step the process requires and
   nothing records, so it cannot be checked. Note carefully what the measurement does and
   does not prove: it shows the answer is *unverifiable*, not that it was never sent.
3. **Then the factory layer proper** — planning releases and bug fixes inside set-core.
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
