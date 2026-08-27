## Why

A fleet tab says whether an agent is running. It says nothing about what it
costs to type into it — and that cost varies by a factor of twenty. A session's
prompt cache is read at 0.1× the base input price while it lives, and rewritten
at 2× once it expires; on this machine the live sessions hold between 15 044 and
195 889 tokens, so the same keystroke costs anywhere from $0.008 to $1.96
depending on a number nothing on screen reports.

The measurement is already on disk. Every assistant record in the native
transcript carries the request's start timestamp, `cache_read_input_tokens`,
`cache_creation_input_tokens`, and which TTL was written
(`cache_creation.ephemeral_1h_input_tokens` / `ephemeral_5m_input_tokens`). No
hook, no new instrumentation, no second store — `discovery.py` already resolves
the transcript path it needs.

## What Changes

- **A fleet agent record gains a cache field**: the last request's start
  timestamp, the TTL read from the record, the cache size in tokens, and the
  estimated cost to rewrite it. Absent when there is no transcript or no usage
  record — **never zero**, because the surface must be able to tell *we do not
  know* from *it is cold*.
- **The tab carries the heat**: a bar along its bottom edge that fills
  left-to-right as the cache COOLS (empty when fresh, full when expired and
  staying there), coloured green / amber / red by that same fraction, its
  THICKNESS encoding the cache size. Once cold, the tab's name turns red and the
  rewrite price appears beside it. The exact minutes and price live in the hover
  title. A seat with no measurement shows `?`, not a bar.
- **PM mode's order stops using a proxy**: `attention.py` orders by how recently
  a blockage began and says in its own docstring that it is following cache heat
  without asserting a lifetime. It gains the measurement: order by the money a
  prompt answer still saves — `size × (2× − 0.1×)` while warm, zero once cold —
  and falls back to today's freshness ordering where nothing was measured.
- **Prices live in one dated table**, not scattered constants, because a
  published price is a measurement with a date and this one will go stale.

## Capabilities

### New Capabilities

- `fleet-cache-heat`: reading a session's prompt-cache state from the native
  transcript, exposing it on the fleet agent record, and marking it on the tab —
  including what the surface must do when the measurement is absent.

### Modified Capabilities

- `agent-fleet-attention-queue`: the ordering rule changes from a freshness
  proxy to measured recoverable cost, with freshness kept as the fallback.
  ⚠ This capability's spec currently lives in the **unarchived** `fleet-pm-mode`
  change (125/126 tasks done), not in `openspec/specs/`. The delta here assumes
  that change archives first; if it does not, this delta has no base to apply to.

## Impact

- `lib/set_orch/fleet/discovery.py` — reads the last usage record per session.
- `lib/set_orch/fleet/attention.py` — ordering rule.
- A new pricing table module (multipliers + per-model input price, dated).
- The fleet API payload gains an optional `cache` object per agent.
- `web/src/pages/Fleet.tsx` (tab rendering) and its unit tests.
- **Confidentiality**: cache figures are read from consumer sessions too. They
  are displayed at runtime and persisted nowhere — not into this repo, not into
  a committed artifact, not into any cache or debug dump.
- **Accepted risk**: red is a reserved meaning here (`failed`). On a twelve-tab
  strip after a weekend, seven names can be red at once, which weakens the
  colour for an agent that genuinely failed. The user saw this rendered and
  chose it. The exits, if it grates in use, are a dimmed name or a muted red —
  neither touches the geometry.
