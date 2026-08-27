"""Keeping one measurement fresh, so that reading never costs a network call.

Reading is a screen refresh. Measuring is a rate-limited request against
somebody else's service. Collapsing the two would tie the number of upstream
calls to the number of open browsers — the coupling that turns a dashboard into
a self-inflicted rate limit.

So the poller owns the clock: a background thread refreshes on an interval, and
every reader is answered from the last COMPLETED measurement, whatever is in
flight. Two consequences worth stating, because both are behaviour and not
implementation detail:

- **A failed refresh does not erase a good one.** The previous figures stay, with
  their ORIGINAL timestamp — a true-but-old measurement beats no measurement, and
  the timestamp is what lets a reader tell which they are looking at.
- **Every answer carries `measured_at`.** A screen that cannot say how old its
  numbers are is indistinguishable from one that is up to date, which is the
  failure that reads as calm.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .accounts import discover_accounts
from .client import AccountUsage, UsageClient

logger = logging.getLogger(__name__)

__all__ = ["UsagePoller", "DEFAULT_INTERVAL_SECONDS"]

#: One minute. At three accounts this is 3 upstream calls a minute once the
#: organization uuids are cached, and the windows it measures move in hours.
DEFAULT_INTERVAL_SECONDS = 60


class UsagePoller:
    """Refreshes account usage on its own schedule and serves the last answer."""

    def __init__(self, interval: int = DEFAULT_INTERVAL_SECONDS, client: UsageClient | None = None,
                 discover=discover_accounts):
        self._interval = interval
        self._client = client or UsageClient()
        self._discover = discover
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._accounts: List[AccountUsage] = []
        self._measured_at: Optional[str] = None
        self._last_error: Optional[str] = None

    # ---- measurement ----------------------------------------------------

    def refresh(self) -> None:
        """Take one measurement. Never raises; a failure keeps the last answer."""
        try:
            accounts = self._discover()
            results = self._client.fetch_all(accounts)
        except Exception as exc:
            with self._lock:
                self._last_error = type(exc).__name__
            logger.warning("usage refresh failed: %s — keeping the previous measurement",
                           type(exc).__name__)
            return

        stamp = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._accounts = results
            self._measured_at = stamp
            self._last_error = None
        logger.debug("usage refreshed: %d account(s) at %s", len(results), stamp)

    def snapshot(self) -> Dict[str, Any]:
        """The last completed measurement. Reading this makes no upstream call.

        `measured_at` is `None` before the first refresh completes, and that is a
        distinct state from an empty account list: one means nobody has looked
        yet, the other means there is nothing to look at.
        """
        with self._lock:
            return {
                "accounts": [a.to_dict() for a in self._accounts],
                "measured_at": self._measured_at,
                "interval_seconds": self._interval,
                "last_error": self._last_error,
            }

    # ---- lifecycle ------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(self._interval)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="usage-poller", daemon=True)
        self._thread.start()
        logger.info("usage poller started: interval=%ss", self._interval)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=5)
        logger.info("usage poller stopped")
