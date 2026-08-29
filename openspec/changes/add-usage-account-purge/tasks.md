# Tasks: add-usage-account-purge

## 1. Store removal

- [x] 1.1 `lib/set_orch/usage/accounts.py`: `purge_accounts(directory=None, targets) -> dict`
      — targets `[{kind, name}]`; web store: read `claude-session.json` (both shapes), drop
      matching entries, atomic write back in `{"accounts": [...]}` shape, owner-only
      permissions preserved; cc store: remove through `set_router.AccountPool.remove`
      semantics (last account refused, `active` moved to a survivor); per-target
      application — one refusal never stops the others; the answer separates removed from
      refused, carries names/counts/reasons and never a credential; unknown entry reported
      as not found, not removed
- [x] 1.2 `kind: glm` is refused with an answer naming `providers.json` as the place the
      credential is managed; `providers.json` untouched
- [x] 1.3 `tests/unit/test_usage_accounts.py` (or a sibling `test_usage_purge.py`): web
      store both shapes; permissions preserved; unknown entry; last cc account refused;
      active cc account moves the role; glm refused; mixed request removes and refuses
      independently; no credential in the answer

## 2. Endpoint

- [x] 2.1 `lib/set_orch/api/usage.py`: `POST /api/usage/accounts/purge`, body
      `{accounts: [{kind, name}]}`; guard against the live poller snapshot — only
      `unreachable` accounts are purgeable, measured/unmeasured/unknown are refused by
      name; response: removed + refused lists, counts, no credential
- [x] 2.2 Extend `tests/unit/test_usage_api.py`: route registered before project
      wildcards; dead account purged; healthy account refused; unknown refused; glm
      refused; no poller → explicit failure, nothing removed; no credential in any
      response

## 3. Strip affordance

- [x] 3.1 `web/src/components/FleetUsageStrip.tsx`: purge action on the "did not answer"
      line, present only while silentCount > 0; confirmation naming the accounts and
      stating credentials will be deleted; wording says "did not answer", never "expired";
      on success, refetch immediately
- [x] 3.2 Extend `web/tests/unit/fleetUsageStrip.test.tsx`: button present when something
      is silent; absent when nothing is; confirmation text names the accounts; successful
      purge triggers a refetch; failed purge keeps the state
- [x] 3.3 `web/src/lib/fleetUsageBars.ts`: expose the silent accounts' kind/name pairs for
      the confirm text, if the strip state does not already carry them

## 4. Verify

- [x] 4.1 pytest: new and touched suites set-diffed against a freshly run baseline
- [x] 4.2 vitest: the touched suites
- [x] 4.3 Visual check in the browser: button appears on the live strip's "did not answer"
      line, confirmation lists the dead accounts, a confirmed purge removes the rows on
      the spot. If the browser cannot be reached, this task stays open
- [x] 4.4 Commit with the spec artifacts
