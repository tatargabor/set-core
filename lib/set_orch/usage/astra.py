"""The ChatGPT/Codex plan as a usage source, beside the claude.ai accounts and GLM.

The machine may run its agents on a ChatGPT plan through a local Anthropic-format
gateway. When it does, that plan's rolling quota is the one the operator runs out
of first, so it belongs on the same strip as everything else that can stop the
work — and until this existed, the fleet header showed the Anthropic accounts and
GLM while the third provider was simply absent.

## The upstream, measured 2026-09-08

`GET https://chatgpt.com/backend-api/wham/usage`, authenticated with the OAuth
**access token** as a `Bearer` credential plus a `chatgpt-account-id` header.
Two sibling endpoints were probed at the same time and both answered `403`
(`/backend-api/codex/usage`, `/backend-api/codex/rate_limits`) — this is the one
that answers, and the transport test pins the header shape so an edit cannot
quietly change what is being asked.

The answer carries `rate_limit.primary_window` and `rate_limit.secondary_window`,
each with `used_percent`, `limit_window_seconds` and `reset_at` in **epoch
seconds**. Measured live: primary 18 000 s (five hours) and secondary 604 800 s
(seven days) — the same two-window shape the other sources already produce, so
nothing downstream needs a new concept.

**The group is derived from the window's own length, never from its position.**
`primary`/`secondary` are names for slots, and a plan that reorders them or adds
a third would otherwise silently relabel a weekly window as a session one.

## Severity is banded here, because the upstream states none

Exactly as in `glm.py`, and with the same constants, so one screen teaches one
reading. The upstream does report `limit_reached`, which is stronger than any
band — when it is true the window is critical whatever the percentage says.

## The credential is the Codex login, not the provider's gateway token

The provider entry for this gateway carries a LOCAL token for a loopback
endpoint; it authenticates nothing upstream. The account's real credential is
the OAuth token the Codex login wrote. Reading the provider's token here would
send a meaningless secret to a real host — so discovery goes to the login file
and the provider declaration is not consulted at all.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .accounts import Account
from .client import (
    OUTCOME_MEASURED,
    OUTCOME_UNMEASURED,
    OUTCOME_UNREACHABLE,
    AccountUsage,
    UsageWindow,
    _as_float,
)

logger = logging.getLogger(__name__)

__all__ = [
    "KIND_ASTRA",
    "USAGE_URL",
    "AstraUsageClient",
    "auth_path",
    "discover_astra_account",
]

KIND_ASTRA = "astra"

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"

#: The account's display name. A fixed label rather than the email the response
#: carries: the strip already shows two accounts BY email, and the plan is
#: identified by what it is. The email is never persisted here in any case.
ACCOUNT_NAME = "ChatGPT"

#: Windows are grouped by their measured LENGTH, so a reordered or added window
#: cannot be relabelled by its slot. Anything else keeps its length and gets a
#: group naming it, rather than being dropped or guessed into one of these.
_SESSION_MAX_SECONDS = 24 * 3600
GROUP_SESSION = "session"
GROUP_WEEKLY = "weekly"

#: The same band the GLM source documents, for a source whose upstream states
#: no severity of its own. One pair of numbers across the screen.
WARNING_PERCENT = 70.0
CRITICAL_PERCENT = 90.0

#: Below this, a reset stamp is more plausibly seconds than milliseconds.
_MILLIS_THRESHOLD = 100_000_000_000

_TIMEOUT = 15
_USER_AGENT = "codex-cli"


def auth_path() -> Path:
    """Where the Codex login keeps its tokens. `CODEX_HOME` wins if set."""
    override = os.environ.get("CODEX_HOME")
    base = Path(override) if override else Path.home() / ".codex"
    return base / "auth.json"


def discover_astra_account(path: Optional[Path] = None) -> List[Account]:
    """The ChatGPT account, if this machine carries a Codex login.

    An absent or unreadable login file is NOT an account and NOT a warning: this
    runs once a minute, and a machine that has never signed in would otherwise
    warn forever. Debug level, and an empty list — the same shape the GLM source
    uses for a machine with no GLM credential.

    An API-key login is deliberately excluded: it bills per token and has no
    plan quota to report, so it has no rolling window this strip could draw.
    """
    src = path or auth_path()
    try:
        document = json.loads(src.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("no ChatGPT account: %s (%s)", type(exc).__name__, src)
        return []

    tokens = document.get("tokens") if isinstance(document, dict) else None
    if not isinstance(tokens, dict):
        logger.debug("Codex login carries no tokens block — no ChatGPT account")
        return []
    access = tokens.get("access_token")
    if not access:
        logger.debug("Codex login carries no access token — no ChatGPT account")
        return []

    account = Account(name=ACCOUNT_NAME, kind=KIND_ASTRA, credential=str(access))
    # The account id travels beside the credential, not inside it: the upstream
    # wants it as its own header, and packing two values into one string is how
    # a credential ends up in a field nobody expected it in.
    setattr(account, "account_id", str(tokens.get("account_id") or ""))
    return [account]


class AstraUsageClient:
    """Reads the ChatGPT plan's rolling windows from the usage endpoint.

    `transport` exists for tests, as in the other clients: a fake that records
    the request is how the header shape is *asserted* rather than believed.
    """

    def __init__(self, transport=None):
        self._transport = transport or self._default_transport

    # ---- transport -------------------------------------------------------

    def _default_transport(self, url: str, token: str, account_id: str) -> Optional[Any]:
        """curl → urllib, the same order and the same fall-through as GLM's."""
        cmd = [
            "curl", "-s",
            "-H", f"Authorization: Bearer {token}",
            "-H", f"chatgpt-account-id: {account_id}",
            "-H", "Accept: application/json",
            "-H", f"User-Agent: {_USER_AGENT}",
            "--max-time", str(_TIMEOUT),
            url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT + 5)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError) as exc:
            logger.debug("curl transport failed: %s", type(exc).__name__)

        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "chatgpt-account-id": account_id,
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
            })
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, OSError) as exc:
            logger.debug("urllib transport failed: %s", type(exc).__name__)
        return None

    # ---- upstream shape --------------------------------------------------

    @staticmethod
    def _group_for(length: Optional[int], slot: str) -> str:
        """The group, from the window's LENGTH — never from which slot it sat in.

        A plan that reorders the two windows, or adds a third, would otherwise
        have a weekly window rendered under the session label, which is a false
        value in the field a reader uses to decide whether to start more work.
        """
        if length is None:
            return slot
        return GROUP_SESSION if length <= _SESSION_MAX_SECONDS else GROUP_WEEKLY

    @staticmethod
    def _resets_at(value: Any) -> Optional[str]:
        """Epoch seconds (or milliseconds) → ISO UTC. Unparseable → None."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        seconds = value / 1000 if value >= _MILLIS_THRESHOLD else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _severity(utilization: Optional[float], limit_reached: bool) -> Optional[str]:
        """The band — and the upstream's own stop, which outranks any threshold."""
        if limit_reached:
            return "critical"
        if utilization is None:
            return None
        if utilization >= CRITICAL_PERCENT:
            return "critical"
        if utilization >= WARNING_PERCENT:
            return "warning"
        return None

    def _parse(self, account: Account, document: Any) -> AccountUsage:
        if not isinstance(document, dict):
            return AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, [])

        rate = document.get("rate_limit")
        if not isinstance(rate, dict):
            # Answered, with nothing in it. Distinct from "did not answer":
            # folding them together would report a live account as broken.
            return AccountUsage(account.name, account.kind, OUTCOME_UNMEASURED, [])

        limit_reached = bool(rate.get("limit_reached"))
        windows: List[UsageWindow] = []
        for slot in ("primary_window", "secondary_window"):
            entry = rate.get(slot)
            if not isinstance(entry, dict):
                continue
            length = entry.get("limit_window_seconds")
            length = int(length) if isinstance(length, (int, float)) and not isinstance(length, bool) else None
            utilization = _as_float(entry.get("used_percent"))
            windows.append(UsageWindow(
                group=self._group_for(length, slot),
                kind=slot,
                utilization=utilization,
                resets_at=self._resets_at(entry.get("reset_at")),
                severity=self._severity(utilization, limit_reached),
                scope=None,
                window_seconds=length,
            ))

        outcome = OUTCOME_MEASURED if any(w.measured for w in windows) else OUTCOME_UNMEASURED
        return AccountUsage(account.name, account.kind, outcome, windows)

    # ---- public ----------------------------------------------------------

    def fetch_document(self, account: Account) -> Optional[Dict[str, Any]]:
        return self._transport(USAGE_URL, account.credential,
                               getattr(account, "account_id", "") or "")

    def fetch(self, account: Account) -> AccountUsage:
        usage = self._parse(account, self.fetch_document(account))
        logger.debug(
            "ChatGPT account measured: outcome=%s windows=%d", usage.outcome, len(usage.windows)
        )
        return usage

    def fetch_all(self, accounts: List[Account]) -> List[AccountUsage]:
        """Every account, independently — one failing removes no other.

        Required by the poller: a source whose client lacks this raises an
        AttributeError that the poller reports against the source's DISCOVER
        name, which points a reader at the wrong half of the source entirely.
        """
        out: List[AccountUsage] = []
        for account in accounts:
            try:
                out.append(self.fetch(account))
            except Exception as exc:  # noqa: BLE001 — one account never removes another
                logger.warning(
                    "ChatGPT account read raised: %s — reporting unreachable", type(exc).__name__
                )
                out.append(AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, []))
        return out
