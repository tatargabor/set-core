## Context

The fleet payload already carries, per agent, a `cache` block holding `tokens` (cache read +
cache creation of the last request) and `model` (what the runtime reports). Nothing renders the
fraction those two imply.

Two facts from the running dashboard constrain every decision below, and both were measured
rather than assumed:

- A live agent carried `provider: {"recorded": false, "provider": null, "model": null}` while
  its `cache.model` was `claude-opus-5`. **The record is frequently absent; the measurement is
  not.**
- The machine now declares three providers whose windows differ by more than four times:
  `anthropic` (200 000, with 1M variants), `glm` (900 000), `astra` (272 000, confirmed from
  the clodex gateway's own `/v1/models`).

The neighbouring capability `fleet-usage-bars` forbids a per-tab quota mark, for a reason that
does not transfer: account quota has no per-seat identity to join on. Context is read from the
agent's own transcript and needs no join.

## Goals / Non-Goals

**Goals:**
- One fill mark per live agent, each against its own model's window.
- One source of truth for the window and the fraction, so the screen and the payload cannot
  disagree.
- Every not-a-number state visible as itself, never as an empty bar.
- A header that stays a fixed size as the fleet grows, without hiding the agent worth seeing.

**Non-Goals:**
- Predicting when an agent will compact (see the Decisions — the threshold is not reliably
  resolvable).
- Any new upstream call, credential, or poller.
- Replacing or re-scoping the account quota bars or the cache-heat marks.

## Decisions

### The window is resolved from the MEASURED model, not the recorded provider

`provider.recorded` is `false` on real agents right now, so a provider-keyed lookup would
return nothing for them. On a strip made of bars, "nothing" is read as "consumed nothing" —
the false-absence class this repo already names. `cache.model` exists wherever a request has
been made, which is exactly the population that has a context worth drawing.

*Alternative considered:* resolve from `providers.json` per agent's recorded provider, giving
the operator's own `CLAUDE_CODE_MAX_CONTEXT_TOKENS`. Rejected as the primary source for the
reason above; it also keys on the wrong thing — the window is a property of the MODEL, and one
provider serves several models with different windows.

### A model→window table, in Python, with unmeasured as the fall-through

The table is matched against the measured model name. **An unmatched model resolves to
unmeasured, never to a default.** A default window would be a plausible wrong number attached
to an unfamiliar model — precisely the case a reader cannot check — whereas `?` is a true
statement that costs nothing to act on.

The fail direction is what makes this safe: a new model ships and shows `?` until the table
learns it. The opposite arrangement fails silently and looks correct.

### The fill is computed server-side and published in the payload

The browser renders what the payload states and derives no fraction of its own. Two tables are
two chances to disagree, and a header contradicting the payload leaves the reader unable to
tell which to believe. This is the rule `cache_heat.py` already follows for `cooled`/`cold`.

*Alternative considered:* a client-side map in `web/src/lib/`. Rejected — it would have to be
kept in step with the Python table by hand, and the divergence would surface as a wrong
percentage rather than as an error.

### A new `context` block, not more fields on `cache`

`cache` answers "what does a keystroke cost here" and is consumed by the cache-heat marks.
Context fill is a different question that happens to share an input. Overloading `cache` would
couple two marks that must be able to change independently.

### The bar is drawn against the WINDOW, not against the compact threshold

This is the subtlety worth stating, because the compact point is arguably the more actionable
number: with `--autocompact 200k` on Astra's 272 000 window, an agent compacts near **73 %**, so
a full bar will essentially never be seen.

It is still the wrong denominator here. The threshold lives in the provider's `args` in
`providers.json` — reachable only through the **recorded provider**, which is the source this
design just rejected as frequently absent. Drawing against a threshold we can resolve for some
agents and not others would produce two incomparable scales on one strip, which is worse than
one honest scale.

Compromise: the window is the denominator; the mark's description carries the raw token count
and the window, so a reader who knows their own autocompact setting can apply it. Revisit if
the compact threshold ever becomes measurable per agent — noted in Open Questions.

### Bands reuse the values the GLM source already uses

70 % warning, 90 % critical. No upstream states a severity for context fill, so the band is
set-core's own opinion — the same position `usage/glm.py` documents for its own bands. Reusing
the numbers means one screen teaches one reading; inventing a second pair would make two marks
disagree about what "amber" means.

### The cap orders by fullness

At most a fixed number of marks, chosen by descending fill, with a count for the remainder.
Ordering by fullness is what makes the cap safe rather than merely tidy: everything hidden is
emptier than everything shown, so the visible marks alone justify the conclusion that nothing
worse is behind the count. A cap ordered by name or by start time would let the fullest agent
be the hidden one — a place a failure can sit while the screen looks calm.

## Risks / Trade-offs

- **[`cache.tokens` is a proxy, not a context measurement]** → It is the cache read + creation of
  the last request, which tracks context closely but is not the same quantity. Mitigated by
  stating it in the mark's description rather than implying precision; the spec requires it.
- **[A stale model table silently under-reports coverage]** → Unmatched models show `?`, which
  is visible rather than wrong. The count of unmeasured agents is shown, so a table falling
  behind reality announces itself as a rising `?` count.
- **[The window is a property of a model name that vendors change]** → Matching is on
  normalised names with explicit entries; a rename produces `?`, not a wrong denominator.
- **[Header crowding as the fleet grows]** → The cap bounds the width; the overflow count keeps
  the hidden population visible.
- **[Two marks on one line could be confused with the quota bars]** → They are visually distinct
  and separately labelled; the detail view names which measurement is which.

## Open Questions

- Should the compact threshold become the denominator if it is ever resolvable per agent
  without the recorded provider? It is the more actionable number; today it is not measurable
  for the population that needs it.
- What is the right cap? A number is chosen in tasks and checked by looking at the real header;
  the correct value is a layout measurement, not a decision that can be made in advance.
- ~~Should an agent whose fill exceeds its window clamp at 100 % or render as its own state?~~
  **Answered 2026-09-08 by the live fleet, and neither option was right.** 3 of 7 agents exceeded
  their window — every one a million-token session whose recorded model name drops the `[1m]`
  marker, and whose true window is not in the process cmdline or environment either. A context
  cannot exceed its own window, so the figure is evidence the WINDOW is wrong, and the agent is
  reported UNMEASURED. Clamping would have shown a full red bar for an agent nowhere near its
  limit; raising the family default to a million fails the other way, which is worse — a genuine
  190 000-token session would read as a calm 19 % in the moments before it compacts.
