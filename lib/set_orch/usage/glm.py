"""The GLM Coding Plan as a usage source, measured against its monitor endpoint.

The machine may run its agents through GLM (`providers.json` declares the
`glm` provider with a credential), and its quota is then the one the operator
runs out of first — so it belongs on the same screen as the claude.ai accounts.

## The upstream, measured 2026-08-29

`GET {host}/api/monitor/usage/quota/limit`, where host is the scheme and host
of the credential's `base_url`. The credential authenticates as an
`Authorization` header carrying the **raw token — no `Bearer` prefix**. That
is not a style choice: z.ai's own plugin (`query-usage.mjs` in
`zai-org/zai-coding-plugins`) sends it bare, and the live probe answered `200`
to a bare token. A later edit that "fixes" the header into a Bearer form
changes what the endpoint answers; the transport test that asserts the exact
header is the guard against exactly that edit.

The answer is `data.limits[]` — today two `CREDIT_LIMIT` entries (unit 3 ×
number 5 = the five-hour credit pool, unit 6 × number 1 = the weekly pool) —
each carrying `percentage`, `usage`, `currentValue`, `remaining` and
`nextResetTime` in **epoch milliseconds**. The upstream states **no severity**.

## Severity is banded here, in this module, and nowhere else

z.ai states no severity, so the choice is a window at 96 % rendering calm or a
band chosen here. The band lives in exactly one place — `_severity` below —
because a threshold that scatters becomes five thresholds that disagree. It is
set-core's own opinion, stated in the spec as such, and it MUST NOT be applied
to any window whose upstream declared a severity of its own: there, preferring
ours over theirs is precisely the "second opinion" defect `client.py` warns
about. Everything downstream (tones, counts, marks) reads the reported
severity and stays untouched.

## The three outcomes stay three

`measured`, `unmeasured` (an answer with no figure in it) and `unreachable`
are distinct, as in the Claude client. One more absence matters here: a
machine with no GLM credential has **no account at all** — a different fact
from an account that did not answer — so discovery returns an empty list and
never a placeholder row.
"""

import json
import logging
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..providers import ProviderError
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
    "KIND_GLM",
    "GlmUsageClient",
    "discover_glm_account",
    "monitor_base_url",
    "QUOTA_PATH",
]

KIND_GLM = "glm"

QUOTA_PATH = "/api/monitor/usage/quota/limit"

#: The two unit codes the plan uses today, measured 2026-08-29. Unit 3 counts
#: hours and unit 6 weeks; `number` is how many of them the window spans. Any
#: other pairing is reported with its own group and no length, so the screen
#: draws no elapsed stripe rather than a guessed one.
_UNIT_HOURS = 3
_UNIT_WEEKS = 6

#: The group names downstream already labels — `WINDOW_LABEL` in the strip.
GROUP_SESSION = "session"
GROUP_WEEKLY = "weekly"

#: set-core's own band, applied only because the upstream states none. See the
#: module docstring: this constant pair is the one place it lives.
WARNING_PERCENT = 70.0
CRITICAL_PERCENT = 90.0

#: Below this many, a reset value is more plausibly seconds than milliseconds
#: (1e11 ms is March 1973; every real millisecond stamp is far larger).
_MILLIS_THRESHOLD = 100_000_000_000

_TIMEOUT = 15
_USER_AGENT = "Mozilla/5.0 set-core/1.0 usage-monitor"


def monitor_base_url(base_url: str) -> Optional[str]:
    """`scheme://host` of a credential's base URL, or None if it has neither.

    The monitor endpoints hang off the API host, not off the anthropic path
    the credential names, so only the origin is kept.
    """
    try:
        parts = urllib.parse.urlsplit(base_url)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def discover_glm_account(loader=None) -> List[Account]:
    """The GLM account, if this machine's provider configuration declares one.

    A configuration that cannot be read is not an account — and it must not be
    a warning either, because this runs once a minute: a machine that has
    simply never configured GLM would warn forever. Debug level, and empty.
    """
    from ..providers import load_or_legacy  # local: keeps import cost off the hot path

    load = loader or load_or_legacy
    try:
        config, _notice = load()
    except Exception as exc:  # noqa: BLE001 — any failure here means "no account",
        # never a crash: this runs once a minute, and the poller's per-source
        # boundary is the second net, not the first.
        logger.debug("no GLM account from provider configuration: %s", type(exc).__name__)
        return []

    provider: Any = config.providers.get("glm")
    if provider is None:
        logger.debug("no glm provider declared — no GLM account")
        return []
    credential = getattr(provider, "credential", None)
    if credential is None or not getattr(credential, "token", None):
        logger.debug("glm provider carries no usable credential — no GLM account")
        return []
    return [Account(name="GLM", kind=KIND_GLM, credential=credential.token)]


class GlmUsageClient:
    """Reads the GLM account's rolling quota windows from the monitor endpoint.

    `transport` exists for tests, as in `UsageClient`: a fake that records the
    request is how "the header is the raw token" is *asserted* rather than
    believed.
    """

    def __init__(self, transport=None, resolve_base=None):
        self._transport = transport or self._default_transport
        #: `resolve_base(account) -> Optional[str]` — where the monitor host
        #: comes from. Injectable for the same reason the transport is: a test
        #: that exercises `fetch` must not read this machine's real provider
        #: configuration, which carries a live token.
        self._resolve_base = resolve_base or self._default_resolve_base

    @staticmethod
    def _default_resolve_base(account: Account) -> Optional[str]:
        from ..providers import load_or_legacy

        try:
            config, _notice = load_or_legacy()
        except (ProviderError, OSError) as exc:
            logger.debug("GLM credential unreachable at discovery: %s", type(exc).__name__)
            return None
        provider = config.providers.get("glm")
        credential = getattr(provider, "credential", None) if provider else None
        if credential is None:
            return None
        return monitor_base_url(credential.base_url)

    # ---- transport -------------------------------------------------------

    def _default_transport(self, url: str, token: str) -> Optional[Any]:
        """curl → urllib. No TLS impersonation: this is a plain JSON API, and
        the live probe answered through urllib untouched."""
        cmd = [
            "curl", "-s",
            "-H", f"Authorization: {token}",
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
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": token,
                    "Accept": "application/json",
                    "User-Agent": _USER_AGENT,
                },
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
            logger.debug("urllib transport failed: %s", type(exc).__name__)
        return None

    # ---- upstream shape --------------------------------------------------

    @staticmethod
    def _group_and_length(unit: Any, number: Any) -> tuple:
        """`(group, window_seconds)` from the upstream's own unit and number.

        The length is computed, not looked up, so a plan that changes the
        window length changes the answer rather than breaking a table.
        """
        try:
            unit_i = int(unit)
            number_i = int(number)
        except (TypeError, ValueError):
            return ("unknown", None)
        if unit_i == _UNIT_HOURS:
            return (GROUP_SESSION, number_i * 3600)
        if unit_i == _UNIT_WEEKS:
            return (GROUP_WEEKLY, number_i * 7 * 24 * 3600)
        return (f"unit{unit_i}x{number_i}", None)

    @staticmethod
    def _resets_at(value: Any) -> Optional[str]:
        """Epoch milliseconds → ISO UTC. Unparseable → None, never a guess."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        seconds = value / 1000 if value >= _MILLIS_THRESHOLD else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _severity(utilization: Optional[float]) -> Optional[str]:
        """The one band, for a source whose upstream states none."""
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
        if document.get("success") is False:
            # The upstream named its own failure: a rejection, not an empty
            # answer. Folded into unmeasured it would read as "answered and
            # carried no figure", which is not what happened.
            return AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, [])

        data = document.get("data")
        data = data if isinstance(data, dict) else {}
        raw_limits = data.get("limits")

        windows: List[UsageWindow] = []
        for entry in raw_limits or []:
            if not isinstance(entry, dict):
                continue
            group, length = self._group_and_length(entry.get("unit"), entry.get("number"))
            utilization = _as_float(entry.get("percentage"))
            windows.append(
                UsageWindow(
                    group=group,
                    # The upstream's own type, verbatim — CREDIT_LIMIT today,
                    # whatever z.ai adds later. Never dropped for being unknown.
                    kind=entry.get("type") or group,
                    utilization=utilization,
                    resets_at=self._resets_at(entry.get("nextResetTime")),
                    severity=self._severity(utilization),
                    scope=None,
                    window_seconds=length,
                )
            )

        outcome = OUTCOME_MEASURED if any(w.measured for w in windows) else OUTCOME_UNMEASURED
        return AccountUsage(account.name, account.kind, outcome, windows)

    # ---- public ----------------------------------------------------------

    def fetch_document(self, account: Account) -> Optional[Dict[str, Any]]:
        """The raw quota document, with the monitor host already resolved."""
        base = self._resolve_base(account)
        if not base:
            logger.warning("glm credential base_url has no host — cannot reach the monitor endpoint")
            return None
        return self._transport(f"{base}{QUOTA_PATH}", account.credential)

    def fetch(self, account: Account) -> AccountUsage:
        """One account's usage. Never raises for an upstream problem."""
        document = self.fetch_document(account)
        if document is None:
            return AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, [])
        usage = self._parse(account, document)
        logger.debug(
            "GLM account measured: outcome=%s windows=%d", usage.outcome, len(usage.windows)
        )
        return usage

    def fetch_all(self, accounts: List[Account]) -> List[AccountUsage]:
        """Every account, independently — one failing removes no other."""
        out: List[AccountUsage] = []
        for account in accounts:
            try:
                out.append(self.fetch(account))
            except Exception as exc:
                logger.warning(
                    "GLM account read raised: %s — reporting unreachable", type(exc).__name__
                )
                out.append(AccountUsage(account.name, account.kind, OUTCOME_UNREACHABLE, []))
        return out
