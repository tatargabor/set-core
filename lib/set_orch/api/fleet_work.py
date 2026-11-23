"""The work-agent sweep — fleet-work-agent-done's safety net, run beside the desk sweep.

Decisions are in `fleet/work_close.py`; this module only reads the inventory, stops
through the owner, and ends the mandate with `work-idle`. The mandate is ended only
after the owner confirms it FOUND the agent, so a failed stop leaves the record open.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..fleet import mandate as fleet_mandate
from ..fleet import work_close
from ..fleet.owner_client import OwnerClient, OwnerClientError, OwnerUnavailable

logger = logging.getLogger(__name__)


def sweep_work_agents() -> Dict[str, Any]:
    from .fleet_mandate import _live_rows  # the same inventory read the desk sweep uses

    out: Dict[str, Any] = {"stopped": [], "kept": [], "measured": True}
    rows = _live_rows()
    if rows is None:
        out["measured"] = False
        return out
    try:
        bound = work_close.work_bound_seconds()
    except ValueError as exc:
        logger.warning("fleet work sweep: not run — %s", exc)
        out["measured"] = False
        return out
    for row in rows:
        if not work_close.is_work_agent(row):
            continue
        label = row.get("terminal_label")
        verdict, why = work_close.decision(row, bound=bound)
        if verdict != work_close.STOP:
            out["kept"].append({"label": label, "why": why})
            continue
        try:
            result = OwnerClient().stop(label)
        except (OwnerUnavailable, OwnerClientError) as exc:
            logger.warning("fleet work sweep: %s (pid %s) was not stopped (%s)",
                           label, row.get("pid"), type(exc).__name__)
            out["kept"].append({"label": label, "why": "stop-failed"})
            continue
        if result.get("found"):
            fleet_mandate.MandateStore().end(row["mandate"]["id"], "work-idle")
            logger.info("fleet work sweep: stopped %s (pid %s, mandate %s) after %.0f s without movement",
                        label, row.get("pid"), row["mandate"]["id"],
                        float(row.get("last_movement_seconds") or 0))
            out["stopped"].append(label)
    return out
