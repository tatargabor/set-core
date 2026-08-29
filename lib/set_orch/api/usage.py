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

The list is additive in `kind` — `web` and `cc` (claude.ai accounts) and `glm`
(the provider credential's plan) — and it is the union of independent sources,
not one measurement with more rows. Every state rule above applies per account,
whichever source it came from.

## What never appears in this response

The session keys and bearer tokens the poller used. They live in the account
records the client holds; the shape returned here has no field they could occupy,
and a test asserts it on every account state rather than trusting that.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..usage.accounts import purge_accounts

logger = logging.getLogger(__name__)

router = APIRouter()


class PurgeTarget(BaseModel):
    kind: str
    name: str


class PurgeRequest(BaseModel):
    accounts: List[PurgeTarget]


@router.post("/api/usage/accounts/purge")
def purge_dead_accounts(request: Request, body: PurgeRequest) -> Dict[str, Any]:
    """Remove accounts that did not answer, and their stored credentials.

    The unreachable-only guard is enforced HERE, against the live poller
    snapshot — not in the button. A screen that has gone stale cannot delete a
    healthy account's credential, because the server re-checks what is dead at
    the moment of the removal, which is the only moment it matters. Every
    target is applied independently: one refusal never stops the others, and
    the answer names what was removed, what was refused, and why — with no
    credential in any field, this being exactly the moment a secret is in hand.
    """
    poller = getattr(request.app.state, "usage_poller", None)
    if poller is None:
        logger.warning("purge requested with no poller running — refusing everything")
        return {
            "results": [
                {"kind": t.kind, "name": t.name, "outcome": "refused",
                 "reason": "no measurement is running, so nothing can be confirmed dead"}
                for t in body.accounts
            ],
            "removed": 0,
            "refused": len(body.accounts),
        }

    snapshot = poller.snapshot()
    outcome_by_identity = {
        (a.get("kind"), a.get("name")): a.get("outcome")
        for a in snapshot.get("accounts", [])
    }

    allowed = [
        {"kind": t.kind, "name": t.name}
        for t in body.accounts
        if outcome_by_identity.get((t.kind, t.name)) == "unreachable"
    ]
    guard_refused = [
        {"kind": t.kind, "name": t.name, "outcome": "refused",
         "reason": "the current measurement does not show this account as dead"
         if (t.kind, t.name) in outcome_by_identity
         else "the current measurement carries no account by this kind and name"}
        for t in body.accounts
        if outcome_by_identity.get((t.kind, t.name)) != "unreachable"
    ]

    store_answer = purge_accounts(allowed) if allowed else {"results": [], "removed": 0, "refused": 0}
    results = store_answer["results"] + guard_refused
    removed = store_answer["removed"]
    refused = len(results) - removed
    logger.info("purge: %d removed, %d refused", removed, refused)
    return {"results": results, "removed": removed, "refused": refused}


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
