"""Reading an account's rolling usage windows from the upstream account API.

## What the upstream actually answers

Measured 2026-08-27 against three configured accounts (all `200`, 0.64–0.71 s
each), the usage document carries the same figures twice:

- `five_hour` / `seven_day` — `{utilization, resets_at, limit_dollars: null, …}`,
  and **either may be `null` on an account that answered perfectly well**
- `limits` — the same figures already banded by the service:
  `{kind, group, percent, severity, resets_at, scope, is_active}`, including
  `weekly_scoped` entries that name one model

`limits` is preferred because it carries the **severity**, and a threshold chosen
here would be a second opinion about somebody else's limit — one that drifts
silently the day theirs moves. Measured the same day: a 96 % weekly window
arrived already labelled `critical` without anyone here picking 96.

## Three outcomes, and why they are three

`unreachable` (no transport got an answer), `unmeasured` (an answer with no
figures in it), and `measured` are distinct states, not shades of failure. The
middle one is the reason: an account that answers with both windows `null` is
reachable, healthy, and unknown. Folded into either neighbour it tells the reader
something false — that the account is broken, or that it has consumed nothing.
"""

import json
import logging
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .accounts import Account

try:  # pragma: no cover - import guard, exercised by absence not by tests
    from curl_cffi import requests as cffi_requests
except ImportError:  # pragma: no cover
    cffi_requests = None

logger = logging.getLogger(__name__)

__all__ = [
    "AccountUsage",
    "UsageClient",
    "UsageWindow",
    "WindowScope",
    "OUTCOME_MEASURED",
    "OUTCOME_UNMEASURED",
    "OUTCOME_UNREACHABLE",
]

API_BASE = "https://claude.ai/api"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) set-core/1.0"
_TIMEOUT = 15

OUTCOME_MEASURED = "measured"
OUTCOME_UNMEASURED = "unmeasured"
OUTCOME_UNREACHABLE = "unreachable"

#: How long each window group runs. The browser needs this to draw the elapsed
#: stripe, and deriving it there would put the constant in two places.
_WINDOW_SECONDS = {"session": 5 * 3600, "weekly": 7 * 24 * 3600}


@dataclass
class WindowScope:
    """What a scoped window applies to. Carried verbatim, never synthesised."""

    model: Optional[str] = None
    surface: Optional[str] = None


@dataclass
class UsageWindow:
    """One rolling window.

    `utilization` is `None` when the upstream carried no figure — the state this
    whole module exists to keep distinct from `0.0`.
    """

    #: `session` or `weekly` — the group the upstream states.
    group: str
    #: The upstream's own `kind`, kept because `weekly_all` and `weekly_scoped`
    #: share a group and must stay tellable apart.
    kind: str
    utilization: Optional[float] = None
    resets_at: Optional[str] = None
    severity: Optional[str] = None
    scope: Optional[WindowScope] = None
    window_seconds: Optional[int] = None

    @property
    def measured(self) -> bool:
        return self.utilization is not None


@dataclass
class AccountUsage:
    """What a caller gets. There is no field here a credential could travel in."""

    name: str
    kind: str
    outcome: str
    windows: List[UsageWindow] = field(default_factory=list)
    #: Only meaningful for CC accounts.
    active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _as_float(value: Any) -> Optional[float]:
    """A number or nothing. `0` stays `0.0`; anything unusable becomes `None`."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class UsageClient:
    """Fetches usage for accounts, one organization lookup per account per process.

    The organization uuid does not change between polls, so caching it halves the
    upstream traffic: at three accounts and a 60-second poll that is 3 calls a
    minute instead of 6. A rejected usage read drops the cached uuid once, so an
    account that moved organizations re-resolves instead of failing forever.

    `transport` exists for tests. A fake transport can count calls, which is how
    "reading never causes a request" is proved — timing would prove nothing.
    """

    def __init__(self, transport=None):
        self._transport = transport or self._default_transport
        self._org_cache: Dict[str, str] = {}
        self._cffi_warned = False

    # ---- transports -----------------------------------------------------

    def _default_transport(self, url: str, account: Account) -> Optional[Any]:
        """curl_cffi → curl → urllib, in that order.

        The first impersonates a browser's TLS fingerprint, which is what gets
        past the Cloudflare front; the other two are there so a machine without
        it degrades to unreachable rather than to a crash.
        """
        headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
        if account.is_oauth:
            headers["Authorization"] = f"Bearer {account.credential}"
            cookies = None
        else:
            cookies = {"sessionKey": account.credential}

        if cffi_requests is not None:
            try:
                resp = cffi_requests.get(
                    url,
                    headers={k: v for k, v in headers.items() if k != "User-Agent"},
                    cookies=cookies,
                    impersonate="chrome",
                    timeout=_TIMEOUT,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.debug("usage read rejected: status=%s kind=%s", resp.status_code, account.kind)
            except Exception as exc:
                logger.debug("curl_cffi transport failed: %s", type(exc).__name__)
        elif not self._cffi_warned:
            self._cffi_warned = True
            logger.warning("curl_cffi not installed — the usage API may be unreachable")

        cmd = ["curl", "-s", "-H", "Accept: application/json", "-H", f"User-Agent: {_USER_AGENT}"]
        if account.is_oauth:
            cmd += ["-H", f"Authorization: Bearer {account.credential}"]
        else:
            cmd += ["-H", f"Cookie: sessionKey={account.credential}"]
        cmd += ["--max-time", str(_TIMEOUT), url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT + 5)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError) as exc:
            logger.debug("curl transport failed: %s", type(exc).__name__)

        try:
            req = urllib.request.Request(url, headers=headers)
            if cookies:
                req.add_header("Cookie", f"sessionKey={account.credential}")
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
            logger.debug("urllib transport failed: %s", type(exc).__name__)

        return None

    # ---- upstream shape -------------------------------------------------

    @staticmethod
    def _cache_key(account: Account) -> str:
        """`(kind, name)`, and the pairing is load-bearing.

        Keyed on the name alone this cache silently hands one account's
        organization uuid to a different account. It is not hypothetical: the
        first live run of this module resolved three OAuth accounts against the
        uuids their same-named browser accounts had just cached, so a lookup that
        should have failed on an expired token instead proceeded with somebody
        else's organization. It failed one step later, which is exactly the shape
        that hides a cause — the log named the usage read, and the defect was in
        the lookup before it.
        """
        return f"{account.kind}:{account.name}"

    def _organization(self, account: Account) -> Optional[str]:
        cached = self._org_cache.get(self._cache_key(account))
        if cached:
            return cached
        orgs = self._transport(f"{API_BASE}/organizations", account)
        if not isinstance(orgs, list) or not orgs:
            return None
        chosen = None
        for org in orgs:
            if isinstance(org, dict) and "claude_max" in (org.get("capabilities") or []):
                chosen = org.get("uuid")
                break
        if not chosen and isinstance(orgs[0], dict):
            chosen = orgs[0].get("uuid")
        if chosen:
            self._org_cache[self._cache_key(account)] = chosen
        return chosen

    @staticmethod
    def _windows_from_limits(document: Dict[str, Any]) -> List[UsageWindow]:
        """The banded form, which is the only one carrying severity and scope."""
        out: List[UsageWindow] = []
        for entry in document.get("limits") or []:
            if not isinstance(entry, dict):
                continue
            group = entry.get("group") or entry.get("kind") or "unknown"
            raw_scope = entry.get("scope")
            scope = None
            if isinstance(raw_scope, dict):
                model = (raw_scope.get("model") or {}).get("display_name")
                surface = raw_scope.get("surface")
                if model or surface:
                    scope = WindowScope(model=model, surface=surface)
            out.append(
                UsageWindow(
                    group=group,
                    kind=entry.get("kind") or group,
                    utilization=_as_float(entry.get("percent")),
                    resets_at=entry.get("resets_at"),
                    severity=entry.get("severity"),
                    scope=scope,
                    window_seconds=_WINDOW_SECONDS.get(group),
                )
            )
        return out

    @staticmethod
    def _windows_from_legacy(document: Dict[str, Any]) -> List[UsageWindow]:
        """The plain pair, used when `limits` is absent.

        A window the document names but does not fill is still emitted — as an
        unmeasured one. Dropping it would leave the reader unable to tell a
        window that exists and is unknown from one this plan does not have.
        """
        out: List[UsageWindow] = []
        for key, group, kind in (
            ("five_hour", "session", "session"),
            ("seven_day", "weekly", "weekly_all"),
        ):
            if key not in document:
                continue
            block = document.get(key)
            block = block if isinstance(block, dict) else {}
            out.append(
                UsageWindow(
                    group=group,
                    kind=kind,
                    utilization=_as_float(block.get("utilization")),
                    resets_at=block.get("resets_at"),
                    severity=None,
                    scope=None,
                    window_seconds=_WINDOW_SECONDS.get(group),
                )
            )
        return out

    def _parse(self, account: Account, document: Any) -> AccountUsage:
        if not isinstance(document, dict):
            return AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, [], account.active)

        windows = self._windows_from_limits(document)
        if not windows:
            windows = self._windows_from_legacy(document)

        outcome = OUTCOME_MEASURED if any(w.measured for w in windows) else OUTCOME_UNMEASURED
        return AccountUsage(account.name, account.kind, outcome, windows, account.active)

    # ---- public ---------------------------------------------------------

    def fetch(self, account: Account) -> AccountUsage:
        """One account's usage. Never raises for an upstream problem."""
        org = self._organization(account)
        if not org:
            logger.warning("account unreachable at organization lookup: kind=%s", account.kind)
            return AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, [], account.active)

        document = self._transport(f"{API_BASE}/organizations/{org}/usage", account)
        if document is None:
            # The uuid may be the stale half. Drop it so the next poll re-resolves
            # rather than repeating a request that cannot succeed.
            self._org_cache.pop(self._cache_key(account), None)
            logger.warning("account unreachable at usage read: kind=%s", account.kind)
            return AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, [], account.active)

        usage = self._parse(account, document)
        logger.debug("account measured: kind=%s outcome=%s windows=%d",
                     account.kind, usage.outcome, len(usage.windows))
        return usage

    def fetch_all(self, accounts: List[Account]) -> List[AccountUsage]:
        """Every account, independently.

        One account failing removes no other account from the answer — a shorter
        list would read as "that account is not configured", which is a different
        fact from "that account did not answer today".
        """
        out: List[AccountUsage] = []
        for account in accounts:
            try:
                out.append(self.fetch(account))
            except Exception as exc:
                logger.warning("account read raised: kind=%s %s", account.kind, type(exc).__name__)
                out.append(
                    AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, [], account.active)
                )
        return out
