## Context

The usage poller measures three sources: Claude (browser session cookies and CLI tokens), GLM
and ChatGPT. The fleet header draws one compact mark per measured account. Browser cookies come
from a Chrome scan that so far only the desktop Control Center could run.

## Goals / Non-Goals

**Goals:** one mark per subscription; labels that tell accounts apart; a pooled Claude 7-day
figure against time; a rescan the owner can press on the fleet screen.

**Non-Goals:** weighting by plan size (not reported by any source); a scheduled rescan; changing
what the poller measures; touching the CLI account store.

## Decisions

**Same subscription = Claude kind (`web` or `cc`) and the same name, case-folded.** The name is
the account email on both sides. The merged row keeps the best outcome (measured, then
unmeasured, then unreachable). On a tie it keeps the CLI row, whose token is the live one. The
merge is done in the browser, over the snapshot. That keeps the API shape and the purge identity
`(kind, name)` unchanged. The detail still lists the kinds the merged row came from.

**Labels are made distinct over all Claude accounts in the measurement**, so a label does not change when a neighbour goes silent. The base label stays the domain's first
part. Where two or more names share that base, the tokens of the local part that the group does
not share are appended (`acme`, `acme team`). A collision that still remains falls back to the
whole local part. Vendor prefixes go away for Claude rows: the pool mark in front says "Claude"
once for the group, and a merged row cannot be "Claude" and "Claude Code" at once.

**Pool = each subscription's account-wide 7-day window, equal shares.** Only rows with a measured
weekly window (no model scope) and a known elapsed share are counted. Consumed = the mean of the
utilizations. Elapsed = the mean of the elapsed shares. The number is Σ consumed / Σ elapsed, the
share of the pro-rata budget spent so far. Plan sizes are not known, so every subscription counts
as one equal share, and the tooltip says so. The tooltip also names the Claude rows left out and
why. The existing ? and ⊘ counts still carry those rows on the header. Tone: above 100 % is amber
(ahead of time), otherwise sky. Red stays reserved for a window the source reports as critical,
and a pool is not reported by any source.

**The scan moves to `lib/set_orch/usage/chrome_scan.py`.** The dashboard's interpreter has
`pycookiecheat` and `curl_cffi`, and it lacks `gi`, whose subprocess fallback to the system Python
works. Importing the GUI package from the server would pull Qt workers in, so the module moves to
core and `gui/workers/chrome_cookies.py` re-exports it and keeps its QThread wrapper. Its tests
patch module attributes, so they are pointed at the core module.

**Keyring: attribute lookup first.** `Secret.password_lookup_sync` with `application=chrome`,
ignoring the schema name. The old walk stays as the fallback, with each item read inside its own
try, so one dangling item cannot sink it.

**Rescan route.** `POST /api/usage/accounts/rescan` runs synchronously in the threadpool, under a
non-blocking lock (a second press while one runs answers 409). It merges with the existing rule
(manual entries kept, scanned ones replaced), writes atomically with mode 0600, then calls
`poller.refresh()` and returns `{found: [names], snapshot}`. No session key appears in the answer
or the logs. When pycookiecheat is missing or Chrome is not found, it answers 200 with
`found: []` and a reason. In that case the store is not written, so a failed scan cannot wipe
working cookies.

## Risks / Trade-offs

- Equal shares misstate the pool when the plans differ in size. The tooltip says so, and an
  honest equal-share figure beats an invented weight.
- A scan with zero results leaves the store untouched. An account that really logged out
  therefore lingers until purged. That is the existing purge's job.
