# Design: add-usage-account-purge

## Context

The usage strip reports accounts whose stored credentials no longer answer — usually
browser session cookies that expired silently — and nothing can remove them from a
headless machine. The stores have editors today only in the desktop Control Center
(`gui/workers/usage.py`, web store) and the CLI account manager
(`lib/set_router/__init__.py`, CLI OAuth store). The strip knows which accounts are
dead; it is the one surface where they are visible by name.

## Goals / Non-Goals

**Goals:** remove dead accounts from the screen and the store in one act, guarded
server-side; reuse the store rules that already exist; keep the strip honest about what
it knows ("did not answer", not "expired").

**Non-Goals:** any write to `providers.json` (a `glm` credential is refused by design);
automatic or scheduled purging; per-account UI beyond the aggregate action; credential
creation or rotation.

## Decisions

**D1 — Guard at the store boundary, from the live snapshot.** The endpoint removes only
accounts whose outcome in the *current poller snapshot* is `unreachable`. A stale screen
cannot delete a healthy credential, because the server — not the button — holds the
guard. An unknown kind/name is refused the same way.

**D2 — Headless removal in `usage/accounts.py`, not a `gui/` import.** The usage package
is documented free of GUI imports. `purge_accounts(directory=None, targets)` reads
`claude-session.json` (both shapes), drops the named web entries, and writes the
survivors back atomically in the current `{"accounts": [...]}` shape with owner-only
permissions. The GUI's own editor keeps working off the same file.

**D3 — The CLI OAuth store is removed through `AccountPool`, not beside it.**
`set_router.AccountPool.remove(email)` already enforces the rules that make removing an
OAuth account safe — refuse the last account, move `active` to a survivor, atomic 0600
save — and duplicating them would drift. `set_router` has no `set_orch` dependency, so
the import direction is clean; if that ever inverts, the store logic moves into
`usage/accounts.py` and `set_router` keeps the CLI.

**D4 — One aggregate action, confirmed by name.** The detail layer deliberately does not
list unreachable accounts as rows, so per-account buttons would first require listing
them. The button sits on the "N accounts did not answer" line; the confirmation names
the accounts. The decision the confirm models is a human one — unreachable is also what
a network failure looks like — so the wording refuses to say "expired".

**D5 — Same router, registered before the wildcards.** `POST /api/usage/accounts/purge`
joins the existing usage router, whose include order already precedes the
`/api/{project}/...` families (finding CB-16). Mixed requests are applied per account:
one refusal never stops the others.

## Risks / Trade-offs

- [A transient network failure makes a healthy account look dead] → the confirmation
  names the accounts and states that credentials will be deleted; the operator decides
  with more knowledge than the strip has.
- [Two accounts sharing a name in one store] → removal is by kind and name, the same
  identity the strip displays; all entries under that identity are removed together,
  which is what the confirmation offered.
- [The purge endpoint becomes a general deletion API] → the unreachable-only guard and
  the `glm` refusal are the boundary; both are server-enforced and test-asserted.

## Migration Plan

Purely additive. Rollback is removing the route and the button; the stores' formats are
unchanged.

## Open Questions

None.
