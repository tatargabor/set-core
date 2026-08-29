"""Account usage measurement — headless, and deliberately free of any GUI import.

The rolling 5-hour and 7-day quota was measured on this machine long before this
package existed, but only inside a `QThread` in the desktop Control Center, which
means only where PySide6 loads. The fleet screen — where somebody decides whether
to start another agent — had no way to reach it.

What lives here is the measurement and nothing else: who the accounts are
(`accounts`), what the upstream says about them (`client`), and a poller that
keeps one answer fresh so a reader never triggers a network call (`poller`).
Rendering belongs to whoever is reading — the desktop strip, the fleet header,
a CLI.

Two rules run through all three modules and are worth stating once:

- **A missing figure is never a zero.** An account can answer `200` and carry no
  window at all; measured 2026-08-27, one of three configured accounts did
  exactly that. Reported as `0` it reads as "nothing consumed", which is the
  opposite of what is known.
- **The credential does not travel.** `Account` holds it because the client needs
  it; `AccountUsage` — the thing every caller gets — has no field that could
  carry it.
"""

from .accounts import Account, discover_accounts
from .glm import KIND_GLM, GlmUsageClient, discover_glm_account
from .poller import DEFAULT_INTERVAL_SECONDS, UsagePoller, UsageSource
from .client import (
    AccountUsage,
    UsageClient,
    UsageWindow,
    WindowScope,
)


def default_sources() -> list:
    """The sources this machine measures: the Claude accounts, then GLM.

    Injected at the server rather than defaulted in `UsagePoller`, so a bare
    constructor — every existing test — stays hermetic and never reads this
    machine's provider configuration, which carries a live credential.
    """
    return [
        UsageSource(discover=discover_accounts, client=UsageClient()),
        UsageSource(discover=discover_glm_account, client=GlmUsageClient()),
    ]


__all__ = [
    "Account",
    "discover_accounts",
    "KIND_GLM",
    "GlmUsageClient",
    "discover_glm_account",
    "AccountUsage",
    "UsageClient",
    "UsageWindow",
    "WindowScope",
    "UsagePoller",
    "UsageSource",
    "default_sources",
    "DEFAULT_INTERVAL_SECONDS",
]
