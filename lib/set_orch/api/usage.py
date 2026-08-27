from __future__ import annotations

"""What this machine's accounts have spent of their rolling quota.

One GET, answered from the poller the server started at boot. The endpoint reads
a snapshot and nothing else — no upstream call happens on this path, which is the
point of the poller existing at all.

## The three states this route must keep apart

An empty `accounts` list means **no account is configured**. An account with
`outcome: "unreachable"` means it did not answer. An account with
`outcome: "unmeasured"` — or a window whose `utilization` is `null` — means it
answered and carried no figure. Measured 2026-08-27, one of three live accounts
was in exactly that third state, and folding it into either neighbour tells the
reader something untrue: that the account is broken, or that nothing was spent.

`measured_at: null` is a fourth thing again: nobody has looked yet.

## What never appears in this response

The session keys and bearer tokens the poller used. They live in the account
records the client holds; the shape returned here has no field they could occupy,
and a test asserts it on every account state rather than trusting that.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/usage/accounts")
def usage_accounts(request: Request) -> Dict[str, Any]:
    """The last completed measurement of every configured account.

    Answers 200 even when nothing could be measured: an unreachable account and
    an absent poller are both states the screen has to be able to draw, and an
    error status would make the header's usage strip indistinguishable from a
    broken server.
    """
    poller = getattr(request.app.state, "usage_poller", None)
    if poller is None:
        logger.debug("usage read with no poller running")
        return {
            "accounts": [],
            "measured_at": None,
            "interval_seconds": None,
            "last_error": "poller-not-running",
        }
    return poller.snapshot()
