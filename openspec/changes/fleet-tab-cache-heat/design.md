## Context

A fleet tab reports whether an agent is running and nothing about what it costs to type into it.
That cost swings by a factor of twenty: a live prompt cache is read at 0.1× the base input price,
an expired one is rewritten at 2×. Measured on this machine on 2026-08-27, live sessions held
between 15 044 and 195 889 tokens, so one keystroke costs between $0.008 and $1.96 — a spread the
surface is silent about.

Nothing needs to be instrumented to fix that. Claude Code already writes, per assistant turn, the
request's start timestamp and a usage block carrying `cache_read_input_tokens`,
`cache_creation_input_tokens`, and a `cache_creation` breakdown naming the lifetime written.
`discovery.py` already resolves the transcript path (`_session_log_for`). The work is reading one
record, carrying it to the surface, and marking it.

Three rounds of design with the user (2026-08-27) settled the mark itself. This document records
the decisions and, more usefully, the alternatives that lost — because each of them is the obvious
thing to reach for next time.

Verified against platform.claude.com on 2026-08-27, not recalled: cache read is 0.1× base input,
the five-minute write is 1.25×, the one-hour write is 2×, a read refreshes the entry at no cost,
and the lifetime is measured from the START of the request that wrote or read it. Claude Code
writes the one-hour lifetime — measured, `ephemeral_1h_input_tokens` non-zero and
`ephemeral_5m_input_tokens` zero across every session sampled.

## Goals / Non-Goals

**Goals:**

- A reader glancing at the screen — **in any view mode** — can tell which seats are still cheap to
  use and which are not. *Widened 2026-08-27, after the user reported the mark was reachable only
  by full-screening into the tabbed view; this line previously said "the tab strip", which named
  a surface rather than the goal and was met while the goal was not.*
- A reader deciding between two seats can see which one stands to lose more.
- PM mode's ordering stops guessing at the cost it says it is following.
- The absence of a measurement is visible as absence.

**Non-Goals:**

- Warming, preserving, or scheduling around a cache. The surface reports; it does not act.
- Any second data path. If the transcript cannot answer it, the answer is "unmeasured".
- Subagent caches. A tab stands for the session the reader types into.
- Billing accuracy beyond the input-cache arithmetic — no output tokens, no invoice reconciliation.

## Decisions

### The transcript is the source, and the only one

**Chosen:** read the last assistant record of the session's own transcript.
**Alternatives:** a `PostToolUse` hook recording usage per turn; a wrapper around the session; a
sidecar store fed by the runtime.

Every alternative builds a second place where the truth lives, and a second place is a place that
can disagree with the first, go missing, or need migrating. The transcript is written whether or
not this feature exists, is already located by code in this repo, and carries strictly more than
the alternatives would. The hook design also fails on a seat that started before the hook was
installed, which is exactly the seat a reader is most likely to be looking at.

### The lifetime is read from the record, never assumed

**Chosen:** take the TTL from which `cache_creation.ephemeral_*` bucket holds tokens.
**Alternative:** a constant, since Claude Code writes one hour today.

Five minutes is the API's default and one hour is what this client currently requests; the
documented behaviour is that a client may use either, and this session's own records show the
choice is per-request. A constant would be right until the day it silently was not, and the failure
would be invisible: every tab would simply be wrong about when it goes cold. Reading it costs one
dictionary lookup.

### The bar fills with the cooling; it does not drain with the remaining time

**Chosen:** empty when fresh, full when expired, and it STAYS full.
**Rejected:** a countdown bar that starts full and empties.

Rendered side by side, the countdown spends its whole visual budget on the healthy state — a fresh
tab wore a full-width green bar, the same weight as an alarm — and then vanishes at the moment the
tab becomes expensive, leaving a cold seat looking identical to an unmeasured one. Filling with the
cooling inverts both: silence while healthy, a persistent mark once cold.

### Thickness carries the stake

**Chosen:** bar thickness scales with cache size (1px–5px), **logarithmically between
20 000 tokens and 1 000 000**.

*Revised 2026-08-27, after the implementation was looked at on the running dashboard.* This
section originally specified a LINEAR scale against a fixed 200k ceiling, and the Open Question
below left "fixed vs. scaled-to-the-fleet" unresolved. The measurement settled both, and it is
recorded here because the unit tests were green throughout and could not have caught it: the
fourteen live sessions on this machine held between 190 994 and 554 959 tokens, so **every
real seat pinned the 200k ceiling and all five tabs drew at maximum thickness**. The tests
asserted that 15k drew thinner than 195k — true, and over a range no seat occupies. That is the
check-verifies-the-mechanism shape, not a wrong assertion.

The bounds are chosen rather than picked: the ceiling is the model's **context window**, so full
thickness means "as large as this can get"; the floor is where the stake stops mattering (20 000
tokens is about twenty cents to rewrite). Checked against the real fleet, they produce four
distinct thicknesses where the linear scale produced one and a 10k floor produced three.

**Fixed range, not scaled to the fleet** — the Open Question below is answered: scaling to the
current largest seat makes one tab's thickness change because a DIFFERENT tab changed, which is
a mark that moves without its subject moving.
**Rejected, with reasons worth keeping:**

- *A shorter lane for a smaller cache* (the bar's track scaled by size). Ambiguous: a half-filled
  long lane and a full short lane draw the same length of red, so time and stake become
  unreadable from each other.
- *The price on every tab, always.* On a twelve-tab strip that is twelve numbers, and the warm
  figure decides nothing — it is what the reader pays regardless.
- *Fading the tab name with heat.* The surface already fades text for "not connected"; a second
  meaning on the same visual weight spoils both.

Thickness wins because length is already spoken for by the cooling fraction, and the two do not
interfere.

### The mark hangs off the agent, not off the tab strip

**Chosen:** every surface that presents an agent as a unit — its tab AND its tile header — draws the
mark, from one `mark()` call.

*Added 2026-08-27, from a defect rather than from foresight.* The first implementation put the mark
on the tab strip only, which looked like the whole surface and is not: the strip is drawn in one
view mode, and only where a project holds more than one agent. Measured on the day it was reported,
across twelve live agents, the strip could carry a mark for **seven** — the other five, including
every seat alone on its project, showed nothing at all.

Two things this cost, both worth keeping because neither is visible from inside a passing suite:

- **The unit tests for `mark()` were green throughout and could not have caught it.** They decide
  what a cache state MEANS; the defect was in which surfaces ask. That is the mechanism-versus-result
  split again, one layer up: every check verified that the mark is computed correctly, and none
  asked where it is drawn.
- **A test written against the tab passes VACUOUSLY on the case that matters.** A project with one
  agent renders no `[data-fleet-agent-tab]` at all, so an assertion over tabs finds nothing and
  reports success. The test for this now drives a single-agent project deliberately.

**Rejected:** duplicating the mark's logic per surface. Two expressions are two chances to disagree
— the same argument the single-condition decision below makes within one tab, which does not stop
being true at the surface boundary.

**Where the surfaces differ, they differ only in room, never in content.** The tile has space a tab
does not, and spends it on saying the same fact unambiguously: the unmeasured mark reads `cache ?`
there and a bare `?` on a tab, because the tile header already carries an amber `?` for an
unconfirmed binding and two identical glyphs touching would be one mark with two meanings.

### One condition drives every cold mark

**Chosen:** a single `cold` boolean, computed once, drives the full bar, the red name and the price.

Three marks computed from three expressions are three chances to disagree, and a tab whose bar is
full while its name is not leaves the reader unable to tell which mark to trust. This is cheap to
get right at construction and expensive to notice when wrong.

### Absence is a state, not a value

**Chosen:** cache state is optional end to end — absent in the record, absent in the payload,
rendered as an explicit unmeasured mark.

Rendering an unmeasured seat as cold tells the reader to avoid a tab for a cost nobody computed;
rendering it as fresh invites a bill nobody predicted. Both are worse than saying so.

### Prices live in one dated table

**Chosen:** one module holding the multipliers and per-model input prices, carrying the date its
figures were verified; a model absent from the table degrades to showing tokens.

The transcript names the model, not its price, so a table is unavoidable. Making it dated makes its
staleness legible instead of silent, and degrading to tokens means a new model produces a less
precise tab rather than a confidently wrong one.

### PM mode orders by recoverable money

**Chosen:** `size × (rewrite − read)` while live, zero once cold, freshness as the fallback where
nothing was measured.

`attention.py` already says in its own docstring that freshness is a stand-in for cache heat and
that it "asserts no particular cache lifetime". The proxy is blind twice: to the stake (equal
freshness, thirteenfold difference in tokens) and to the threshold (past expiry there is nothing
left to save, so ordering is no longer a cost question). The fallback stays because an unmeasured
seat must not be silently sorted last.

### Reading the record is a backward scan

The last record with a usage block is wanted, transcripts reach megabytes, and this runs for every
discovered agent on every poll. Reading forward to the end would make the fleet endpoint's cost
scale with total transcript size. Scan backward from the end and stop at the first usage block.

## Risks / Trade-offs

- **Red is a reserved meaning (`failed`), and this spends it** → The user saw a twelve-tab strip
  with seven red names rendered and chose it anyway. Recorded rather than quietly absorbed: if it
  grates in use, the exits are a dimmed name or a muted red, and neither touches the geometry, the
  data, or the spec.
- **The price table goes stale** → It carries its verification date, and an unknown model degrades
  to tokens rather than to a wrong number.
- **The `agent-fleet-attention-queue` delta has no base in `openspec/specs/`** → That capability's
  spec lives in the unarchived `fleet-pm-mode` change (125/126 tasks done). If this change archives
  first, its MODIFIED block has nothing to apply to. Mitigation: archive `fleet-pm-mode` first, or
  re-target the delta at whatever lands there.
- **A session mid-generation reads colder than it is** → The record is written when the response
  completes, so a long turn hides its own start for a few minutes. The error is bounded by turn
  length and runs in the safe direction (a tab looks nearer expiry than it is).
- **Per-poll file reads for every agent** → Backward scan with an early stop; the read is one
  `seek`-and-scan per session, not a parse of the file.
- **A tab is a session, but a project can hold several** → Each tab reports its own session, which
  is the thing the reader types into. No aggregation is attempted.

## Migration Plan

Additive throughout. The payload field is optional, so an older web build ignores it and a newer
one renders "unmeasured" against an older backend. PM ordering changes behaviour but keeps its
previous rule as the fallback path, so a fleet where nothing can be measured orders exactly as it
does today. Rollback is reverting the commit; nothing is written, so nothing has to be undone.

## Open Questions

- **Subagents.** They build their own caches and write their own transcripts. Excluded for now, on
  the grounds that a tab is what the reader types into — but a session whose subagents hold more
  cache than it does is not obviously reported correctly by this rule.
- ~~**Whether the strip should scale thickness to the fleet or to a fixed ceiling.**~~
  **ANSWERED 2026-08-27 by measurement, see "Thickness carries the stake" above:** fixed range,
  and logarithmic rather than linear. The fixed ceiling was kept — a mark must not move because
  a different tab moved — but 200k was measured to be *below* the whole live fleet, so the
  ceiling became the context window and the scale became logarithmic.
