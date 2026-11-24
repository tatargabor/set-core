"""`/api/fleet/watchdog` — the set-watchdog's state for the fleet header (change fleet-watchdog).

A `/api/fleet/...` family, registered before the `/api/{project}/...` routers (CB-16). The
summary is read from the watchdog's local store on every request; nothing here runs a probe.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..fleet_watchdog import view

logger = logging.getLogger(__name__)

router = APIRouter()

_FP = re.compile(r"^[0-9a-f]{16}$")


class MuteBody(BaseModel):
    days: float = Field(default=7, gt=0, le=365)


def _check_fp(fp: str) -> None:
    if not _FP.match(fp):
        raise HTTPException(status_code=400, detail="not a watchdog fingerprint")


@router.get("/api/fleet/watchdog")
def watchdog_status() -> Dict[str, Any]:
    return view.summary()


@router.post("/api/fleet/watchdog/{fp}/mute")
def watchdog_mute(fp: str, body: MuteBody) -> Dict[str, Any]:
    _check_fp(fp)
    if not view.mute(fp, body.days):
        raise HTTPException(status_code=404, detail="no such finding")
    logger.info("watchdog api: %s muted for %s days", fp, body.days)
    return {"ok": True, "fp": fp, "days": body.days}


@router.post("/api/fleet/watchdog/{fp}/dispatch")
def watchdog_dispatch(fp: str) -> Dict[str, Any]:
    _check_fp(fp)
    result = view.dispatch_now(fp)
    logger.info("watchdog api: dispatch-now %s -> %s", fp, (result.get("dispatch") or {}).get("state")
                or result.get("reason"))
    if not result.get("ok") and result.get("reason") == "no open finding":
        raise HTTPException(status_code=404, detail="no open finding")
    return result
