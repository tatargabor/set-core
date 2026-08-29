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
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .accounts import discover_accounts
from .client import AccountUsage, UsageClient

logger = logging.getLogger(__name__)

__all__ = ["UsagePoller", "UsageSource", "DEFAULT_INTERVAL_SECONDS"]

#: One minute. At three accounts this is 3 upstream calls a minute once the
#: organization uuids are cached, and the windows it measures move in hours.
DEFAULT_INTERVAL_SECONDS = 60


@dataclass
class UsageSource:
    """One independent upstream the poller measures.

    `discover` yields the source's accounts; `client` needs only `fetch_all`.
    Each source lives inside its own failure boundary in `refresh()` — a
    source whose discovery or read cannot proceed removes no other source's
    accounts from the answer, which is the rule the poller already held per
    account, held one level up.
    """

    discover: Any
    client: Any


class UsagePoller:
    """Refreshes account usage on its own schedule and serves the last answer."""

    def __init__(self, interval: int = DEFAULT_INTERVAL_SECONDS,
                 client: UsageClient | None = None, discover=discover_accounts,
                 sources: List[UsageSource] | None = None):
        self._interval = interval
        #: `sources=None` keeps the pre-source behaviour byte for byte: one
        #: Claude source, built from `discover` and `client`. The indirection
        #: through the attributes is load-bearing — a test may reassign
        #: `poller._discover` after construction, and the source must follow.
        #: The GLM source is injected by the server, never defaulted here — a
        #: default would make every existing poller read this machine's real
        #: provider configuration, which carries a live credential.
        self._discover = discover
        self._client = client or UsageClient()
        if sources is None:
            sources = [UsageSource(discover=lambda: self._discover(), client=self._client)]
        self._sources = sources
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        #: Per-source retention: the figures each source last successfully
        #: measured, aligned with `self._sources`. A source that fails keeps
        #: its slot; the union is what the snapshot serves.
        self._by_source: List[List[AccountUsage]] = [[] for _ in self._sources]
        self._measured_at: Optional[str] = None
        self._last_error: Optional[str] = None

    # ---- measurement ----------------------------------------------------

    def refresh(self) -> None:
        """Take one measurement. Never raises; a failure keeps the last answer.

        The boundary is per source. A source that fails to discover keeps
        whatever figures it last measured and the failure is recorded, while
        the sources that did measure still stamp a fresh `measured_at` — so a
        machine with an unreadable provider configuration does not lose its
        Claude accounts because of it. A source that measured zero accounts is
        a success: an empty measurement is still a measurement.
        """
        errors: List[str] = []
        measured_any = False
        new_groups = list(self._by_source)
        for index, source in enumerate(self._sources):
            try:
                accounts = source.discover()
                new_groups[index] = source.client.fetch_all(accounts)
                measured_any = True
            except Exception as exc:
                errors.append(type(exc).__name__)
                logger.warning("usage source failed (%s): %s — keeping its previous measurement",
                               getattr(source.discover, '__name__', 'source'), type(exc).__name__)

        with self._lock:
            if measured_any:
                stamp = datetime.now(timezone.utc).isoformat()
                self._by_source = new_groups
                self._measured_at = stamp
                self._last_error = "; ".join(errors) or None
                logger.debug("usage refreshed: %d account(s) at %s",
                             sum(len(g) for g in new_groups), stamp)
            else:
                # Every source failed. The previous figures keep their ORIGINAL
                # timestamp — a true-but-old measurement beats no measurement.
                self._last_error = "; ".join(errors) or "refresh-failed"

    def snapshot(self) -> Dict[str, Any]:
        """The last completed measurement. Reading this makes no upstream call.

        `measured_at` is `None` before the first refresh completes, and that is a
        distinct state from an empty account list: one means nobody has looked
        yet, the other means there is nothing to look at.
        """
        with self._lock:
            return {
                "accounts": [
                    a.to_dict() for group in self._by_source for a in group
                ],
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
