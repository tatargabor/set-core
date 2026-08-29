## Why

Accounts whose stored credentials have died — the usual case being a browser session
cookie that expired silently — stay on the usage strip forever as "did not answer".
The measurement is honest about them, but nothing can remove them: the stores they live
in have editors only in the desktop Control Center and a CLI account manager, so a
headless machine accumulates dead rows that cannot be cleaned from the screen where
they are visible.

## What Changes

- A purge endpoint is added beside the usage read: it removes accounts from the
  credential stores this machine keeps, by kind and name, and reports what it removed.
- The endpoint removes only accounts whose current measurement is `unreachable` — a
  stale screen cannot delete a healthy account's credential.
- A `glm` account is refused: its credential lives in `providers.json`, a hand-edited
  data file by design (adding or removing a provider is a data edit, never framework
  code).
- The strip's "N accounts did not answer" line gains a purge button, behind a
  confirmation naming the accounts and stating that their stored credentials will be
  deleted. The wording says "did not answer", never "expired" — unreachable is also
  what a network failure looks like.

## Capabilities

### New Capabilities

- `usage-account-purge`: removing dead usage accounts from this machine's credential
  stores through one guarded endpoint — the unreachable-only guard, the per-store
  removal semantics (browser session store and CLI OAuth store, including the
  last-account and active-account rules), the `glm` refusal, and the rule that no
  credential ever appears in a request answer or log line.

### Modified Capabilities

- `fleet-usage-bars`: the strip's detail layer gains the purge affordance on the
  "did not answer" line — an action on an aggregate the strip already draws, so the
  requirement that owns that line carries the button's presence, confirmation, and
  the wording constraint.

## Impact

- `lib/set_orch/usage/accounts.py` — new `purge_accounts()` (headless: no import from
  `gui/`; atomic writes; 0600 preserved).
- `lib/set_orch/api/usage.py` — new POST route in the existing router (registered
  before the project wildcards — route ordering, finding CB-16, is now in scope).
- `web/src/components/FleetUsageStrip.tsx` — the button, its confirmation, and the
  refetch after a successful purge.
- `lib/set_router/__init__.py` — consumed, not modified: cc-store removal reuses
  `AccountPool.remove` semantics (refuses the last account, moves `active`).
