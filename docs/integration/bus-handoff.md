# Bus handoff — taking over the cross-project channel

Written 2026-07-30 by the outgoing session, for the agent taking the bus over on **bugfix
matters**. Read this before writing a single entry.

**This is a pointer with a timestamp, not a standing summary.** Everything below names how it was
checked. Re-run the check; do not trust the sentence. When this file and the channel tail
disagree, the channel tail wins — it is append-only and it is the record of what was actually
said.

---

## 0. The one rule that outranks everything else here

**One file, one writer.** The protocol has no lock, and the reason it needs none is that exactly
one session appends to each file. Two writers costs two things at once: entries can interleave
mid-write, and the numbering collides.

This is not hypothetical. On 2026-07-30 the peer's side produced **two entries 35 seconds apart,
both numbered `W#147`, saying opposite things about the same row** — because a parallel session
was writing the same file. Their own next entry explained it, and the damage is permanent in a
small way: any future `re: W#147` now identifies nothing.

**So: while you own the bus, the outgoing session must not write to it, and vice versa.** If both
are alive at once, one of you writes and the other hands text over. Do not "just add one entry".

---

## 1. Find the channel — do not hard-code its name

The consumer's name must never be written into this repository (see *External Project
Confidentiality* in `CLAUDE.md`). Derive it:

```bash
ls -dt ~/.local/share/set-core/channels/*/ | head -1     # the channel directory
```

Inside it:

| file | writer | reader |
|---|---|---|
| `set-core.md` | **this project's session — you, once you take over** | the consumer's session |
| `<consumer-slug>.md` | the consumer's session | you |
| `README.md` | whoever created it | both |

Entries are append-only, newest last, headed `## <ISO timestamp> — <TYPE>` where TYPE is one of
`TÉNY` / `KÉRDÉS` / `VÁLASZ` / `KÉRÉS`. This side numbers its entries `S#n`; the peer numbers
theirs `W#n`. Answers cite what they answer (`re: …`). **The channel is written in Hungarian.**

**Catch up before writing:** read the peer's file end-to-end from the last entry you have not
seen, then this side's tail to see what was already answered.

---

## 2. The watch — check it, never re-arm it on reflex

A dead watch and a quiet peer produce identical evidence: no notifications. That cost five days
of silence on 2026-07-28..29. But blindly arming a second one is its own bug — two Monitors on one
file send two notifications for every entry.

```bash
pgrep -f 'NEW=.*<peer file>' | while read -r p; do ps -o pid=,etime= -p "$p"; done
```

**Every hit may be the measuring command matching itself** — the pattern is in the searching
shell's own command line. The rule this repo carried until today was "the impostor is always
`00:00`-aged"; **measured 2026-07-30, that is false.** A self-match came back at `00:30`, because
the measuring pipeline itself takes time to run. Age is a hint, not the discriminator.

What actually discriminates is identity: resolve each PID and look at `lstart` and the command
line. A real Monitor's command line contains the `while` loop and the watched path; a self-match's
contains the shell snapshot the harness sources.

```bash
pgrep -f 'NEW=.*<peer file>' | while read -r p; do ps -o pid=,etime=,lstart=,cmd= -p "$p"; done
```

Never `ps -p <remembered pid>` (PIDs are recycled, so it answers whether *a* process holds that
number) and never a task registry (a Monitor is a background process and does not appear in one,
so it reports "no watcher" for a watcher that is running — which sends you to start a second).

**THE TAKEOVER HAS ALREADY HAPPENED. The outgoing session holds no watch and writes nothing.**
An incoming session announced itself on the channel as `S#150` (2026-07-30 19:12), having read the
peer's file to `W#152` and this side's to `S#149`. It owns `set-core.md` from that entry onward.

**And the outgoing session got the handover itself wrong, in the way worth writing down.** Its
Monitor reported `exit 144` mid-handoff. That read as the documented silent-death failure — the
one that once cost five days — so it re-armed. It should not have: the incoming session had
**killed that watcher on purpose, by PID**, precisely to avoid two watchers on one file. So the
re-arm recreated the exact duplicate this document warns about, and it was stopped as soon as the
channel tail was read.

**The rule that follows, and it is not in any of the older notes:** *before treating a dead watch
as a failure, check whether someone TOOK OVER.* A deliberate kill and a spontaneous death produce
the same evidence — a non-zero exit and no notifications — and they need opposite responses. The
channel's own tail answers it in one read, because a takeover announces itself there.

The general form is already in this repo's rule book under another name: **a signal that two
different causes produce identically is not evidence for either.** The discriminator is never the
signal; it is the cheap second observation that separates the causes.

**Do NOT add a cron fallback.** One was armed and deleted the same evening: it is session-scoped
too, so it cannot witness the death it guards, while its cost is real — it fires on a timer and
the harness requires a visible reply, so "say nothing when there is nothing to do" cannot be
honoured and the user mutes it. The external witness is the **peer**, who has been asked to prod
after 24 h of silence on an entry that concerns this side.

---

## 3. Where the bus stands on bugfixes — the substance you are taking over

### 3a. What is already agreed and measured

**The consumer's user approved the wiring (their `Q1`).** Their session relayed this; note that
the approval reached *their* session, not this one, and this side deliberately keeps "the contract
shape is measured" and "the human approval behind it is relayed" as two separate facts. Do not
collapse them.

**The framework half is finished and archived.** `bugfix-lane-with-a-real-delta` is archived as
`openspec/changes/archive/2026-07-30-bugfix-lane-with-a-real-delta/`, and its capability spec lives
at `openspec/specs/change-lane-profiles/spec.md`. Nothing is left to build here for the lane
itself.

**The wiring is TWO declarations in the CONSUMER's tree, not framework code:**

- `set/lane-signals.json` — a signal carrying
  `answer: {command: "bugs", field: "laneSignals.fixedWithoutRegressionTest"}`
- `set/change-type-lanes.json` — `{"bugfix": ["<that signal's name>"]}`

Both were verified against a live producer through the framework's own reader; the delegation
shape is exercised end-to-end by `tests/unit/test_bugfix_lane_entry.py::
test_the_signal_the_entry_accepts_is_the_signal_the_gate_then_RUNS`.

### 3b. Four things you will be wrong about if you skip them

1. **The first run will report "did not fire", and that is NOT an all-clear.** Both of the
   producer's lists are empty today (a clean tree, the regression baseline down to zero). Both
   sides have this as a rule — an empty result set is a measurement, never silence — so read it
   consistently and do not let anyone report it as "everything is fine".

2. **The producer's list already subtracts its own baseline.** Their field is
   `fixed && !covered && !baseline`, with the known debt in a separate field. Therefore **this
   side's `baseline` declaration for that signal must stay EMPTY** — declaring it twice would
   double-count and the growth check would raise a false alarm. This is their measurement, not an
   inference from it.

3. **ENFORCE severity is not the same statement as "this blocks."** `require_exit_obligation`
   requires the mapped signal to be able to *fail a gate*, via one of three routes: a declared
   `answer` (the route in use here), a registered condition handler (the table is empty by design
   in this version), or the project declaring `sole_enforcement`. This was a real hole in the
   first implementation and it failed in the safe direction — refusing a discount that had been
   paid — which is why it was invisible from inside and found by the peer.

4. **The delegated `field` must resolve to a LIST OF BARE IDENTIFIERS.** A per-row boolean inside
   a list of objects is refused (`lane_gate.py:151-168`), and a projection inside `field` is
   forbidden by design — that would be the producer's rule re-expressed in this framework's
   syntax, which is the second implementation the delegation exists to prevent. The producer
   already publishes the decided list; nothing needs inventing.

### 3c. What is NOT yours

- **The `caveats` thread** (envelope key, additive `"*"` + per-field). Shape settled, framework
  side partly built (`status-contract-caveats`, 26/30 tasks). Not a bugfix matter.
- **The status-table work** (`status-table-structured-cells-and-controls`). Not a bugfix matter.
- **A deferred message about giving the `source` column a structure** — see §4.

---

## 4. Deferred, and deliberately not sent

The user asked for a status surface where a source says *when* and *who* instead of an opaque
identifier. **The message asking the producer for that structure has NOT been sent** — the user
chose to build the framework's half first and deferred the ask.

Do not send it as part of the bugfix handover. It is a separate thread, and mixing it into a
bugfix entry is how a channel loses the ability to answer `re:` anything.

The content, when it is time: the producer publishes `source` as a structure
(`{ref, kind, date, participants[]}`) rather than a slug. The framework cannot derive it — measured
on a real answer, three of five source values embed a date and two do not, so a parser would
succeed on some rows and fail silently on the rest.

---

## 5. Before you write your first entry

- **Announce the takeover** in this side's file: one `TÉNY` saying the session changed, which
  entry number you have read up to, and that you now own this file. The peer must know who they
  are answering — they have their own multi-session problem (§0).
- **Number continuously.** The last entry on this side at handover is `S#149`. Do not restart.
- **A word like "measured" obliges you to show the evidence** — the command, its output, a
  `file:line`, a PID. Without one the honest word is "assumption", and the other side must not
  write it into a rule book. A plausible guess crossed this bus once, was reasonably taken for a
  measurement, and reached both projects' rules before anyone ran the one-line check that
  disproved it.
- **Nothing durable lives in the channel.** The negotiated agreements are in
  `docs/integration/consumer-integration.md` on this side and in the producer's planning document
  on theirs. Read the record to learn what was decided; read the channel to rebuild the contact.
