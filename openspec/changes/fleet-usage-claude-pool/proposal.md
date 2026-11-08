## Why

The usage strip on the fleet header names the wrong things and cannot heal itself. Measured on
2026-11-08 against `GET /api/usage/accounts`:

- The same Claude subscription arrives twice: once as a browser session (`web`) and once as a
  CLI account (`cc`), same email, same 22 % weekly figure. The strip draws it twice ("Claude
  itline", "Claude Code itline"), which reads as two subscriptions.
- Two different subscriptions on one email domain get the same short label, because the label
  is the domain's first part alone.
- A browser session whose cookie expired answers nothing and drops out of the bars. The only
  way to refresh the cookies was the desktop Control Center's "Scan Chrome Sessions" button.
  The owner asked for it on the fleet screen (*"hianyzik a rescan opcio hogy ne kelljen
  belepni a set-control python appba"*).
- The scan itself fails from the dashboard's process. It walks every item in the login keyring
  to find Chrome's password, and one dangling item in that collection makes the walk raise, so
  no cookie can be decrypted. A lookup by attribute finds the password.

The owner also asked for one combined Claude figure (*"kellene claude-ra egy közös mutató hogy
összevonva őket hány %-on állunk 7 napos időarányosan"*): across all Claude subscriptions, how
far the week's spending is ahead of or behind the time that has passed.

## What Changes

- One subscription is one mark: a `web` and a `cc` account with the same name are drawn once.
- Labels are made distinct across the Claude accounts. When two emails share a domain
  label, the part of the local name that differs is added.
- A Claude pool mark leads the Claude bars. It shows the pooled 7-day consumption against the
  pooled elapsed time, plus one number: consumption as a share of the pro-rata budget so far.
- The Chrome session scan moves into the core usage package, so the dashboard can run it. The
  Control Center keeps using it through its old module. The keyring password is looked up by
  attribute first.
- `POST /api/usage/accounts/rescan` runs the scan, merges the result into the browser session
  store (manual entries kept, file written 0600), and measures again at once.
- The strip's detail gets a "rescan Chrome" control that reports what it found, by name.

## Capabilities

### New Capabilities
- `usage-chrome-rescan`: rescanning the browser's Claude sessions from the dashboard.

### Modified Capabilities
- `fleet-usage-bars`: one mark per subscription, labels that tell accounts apart, the Claude
  pool mark, and the rescan control in the detail.

## Impact

- Core: `lib/set_orch/usage/chrome_scan.py` (new, moved from `gui/workers/chrome_cookies.py`),
  `lib/set_orch/api/usage.py`.
- Control Center: `gui/workers/chrome_cookies.py` becomes a re-export plus its QThread worker.
- Web: `web/src/lib/fleetUsageBars.ts`, `web/src/components/FleetUsageStrip.tsx`.
- Tests: `tests/gui/test_17_chrome_cookies.py` targets the moved module; new unit tests for
  the rescan route and for the strip.
