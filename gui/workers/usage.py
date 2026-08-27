"""
Usage Worker - Background thread for fetching Claude usage data

Primary: Local JSONL parsing (cross-platform, no auth needed)
Secondary: Claude.ai API with session key (optional, for exact data)
Supports multiple accounts with per-account usage fetching.

The transport, the authentication and the organization lookup live in
`set_orch.usage` — one measurement path shared with the web dashboard, so a fix
to either reaches both. What stays here is this window's own MAPPING of the
answer (`session_pct`, the burn rates, `has_weekly`), because that mapping is a
shipped requirement of `usage-display` with its own scenarios. Moving the
plumbing must not move the meaning.
"""

import json
import logging
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

from ..constants import CONFIG_DIR, CLAUDE_SESSION_FILE
from ..usage_calculator import UsageCalculator

from set_orch.usage.accounts import Account, KIND_CC, KIND_WEB
from set_orch.usage.client import UsageClient

__all__ = ["UsageWorker", "load_accounts", "save_accounts", "load_cc_accounts"]

logger = logging.getLogger("set-control.workers.usage")



def load_accounts():
    """Load web accounts from claude-session.json.

    Handles both old format {"sessionKey": "..."} and new format
    {"accounts": [{"name": "...", "sessionKey": "..."}, ...]}.
    Returns list of {"name": str, "sessionKey": str, "type": "web"} dicts.
    """
    try:
        if not CLAUDE_SESSION_FILE.exists():
            return []
        with open(CLAUDE_SESSION_FILE) as f:
            data = json.load(f)
        # New format — deduplicate by sessionKey (prefer manual over chrome-scan)
        if "accounts" in data and isinstance(data["accounts"], list):
            seen_keys = {}
            for a in data["accounts"]:
                key = a.get("sessionKey")
                if not key:
                    continue
                if key not in seen_keys or a.get("source") != "chrome-scan":
                    seen_keys[key] = a
            accounts = list(seen_keys.values())
            for a in accounts:
                a.setdefault("type", "web")
            return accounts
        # Old format — auto-wrap
        if data.get("sessionKey"):
            return [{"name": "Default", "sessionKey": data["sessionKey"], "type": "web"}]
        return []
    except Exception:
        return []


def load_cc_accounts():
    """Load Claude Code accounts from cc-accounts.json.

    Returns list of {"name": str, "oauth_token": str, "type": "cc", "active": bool} dicts.
    """
    try:
        cc_file = CONFIG_DIR / "cc-accounts.json"
        if not cc_file.exists():
            return []
        with open(cc_file) as f:
            data = json.load(f)
        accounts = data.get("accounts", [])
        active_name = data.get("active")
        result = []
        for acct in accounts:
            oauth = acct.get("credentials", {}).get("claudeAiOauth", {})
            token = oauth.get("accessToken")
            if not token:
                continue
            email = acct.get("email", acct.get("name", "unknown"))
            result.append({
                "name": email,
                "oauth_token": token,
                "type": "cc",
                "active": email == active_name,
                "source": acct.get("source", "manual"),
            })
        return result
    except Exception:
        return []


def save_accounts(accounts):
    """Save accounts list to claude-session.json in new format.

    Always writes {"accounts": [...]}, never the old single-key format.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CLAUDE_SESSION_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump({"accounts": accounts}, f, indent=2)
    tmp.replace(CLAUDE_SESSION_FILE)


class UsageWorker(QThread):
    """Background thread for fetching Claude usage data"""
    usage_updated = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, config=None):
        super().__init__()
        self._running = True
        self._config = config
        self._calculator = UsageCalculator()
        self._client = UsageClient()

    def _get_limit(self, key: str, default: int) -> int:
        """Get usage limit from config"""
        if self._config:
            return self._config.get("usage", key, default)
        return default

    def fetch_claude_api_usage(self, session_key=None, oauth_token=None):
        """Fetch usage from Claude.ai API using session key or OAuth token.

        The document comes from the shared client; the mapping below is this
        window's own and is unchanged.
        """
        try:
            account = self._account(session_key=session_key, oauth_token=oauth_token)
            document = self._client.fetch_document(account)
            if document is None:
                return None
            return self._map_document(document)
        except Exception:
            return None

    @staticmethod
    def _account(session_key=None, oauth_token=None) -> Account:
        """Wrap a bare credential in the shared client's account shape.

        The NAME matters: the client caches an organization uuid per
        `(kind, name)`, and two accounts sharing a key would share a uuid. The
        credential itself is the only identifier available at this call site and
        it is unique per account, so it is used as the name — it never leaves the
        object, whose `repr` omits it.
        """
        if oauth_token:
            return Account(name=oauth_token, kind=KIND_CC, credential=oauth_token)
        return Account(name=session_key or "", kind=KIND_WEB, credential=session_key or "")

    def _map_document(self, data):
        """Map the upstream document onto the fields this window renders."""
        five_hour = data.get("five_hour") or {}
        seven_day = data.get("seven_day") or {}

        session_pct = five_hour.get("utilization", 0) or 0
        session_reset = five_hour.get("resets_at")
        weekly_pct = seven_day.get("utilization", 0) or 0
        weekly_reset = seven_day.get("resets_at")

        session_burn = self._calculate_burn_rate(session_pct, session_reset, 5)
        weekly_burn = self._calculate_burn_rate(weekly_pct, weekly_reset, 7 * 24)

        return {
            "available": True,
            "session_pct": session_pct,
            "session_reset": session_reset,
            "session_burn": session_burn,
            "has_weekly": bool(data.get("seven_day")),
            "weekly_pct": weekly_pct,
            "weekly_reset": weekly_reset,
            "weekly_burn": weekly_burn,
            "source": "api",
            "is_estimated": False,
        }

    def _calculate_burn_rate(self, usage_pct, reset_time_str, window_hours):
        """Calculate burn rate based on time elapsed in window"""
        try:
            if not reset_time_str:
                return None

            reset_time = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)

            time_remaining = (reset_time - now).total_seconds() / 3600
            time_elapsed = window_hours - time_remaining

            if time_elapsed <= 0:
                return None

            expected_pct = (time_elapsed / window_hours) * 100
            if expected_pct <= 0:
                return None

            return (usage_pct / expected_pct) * 100
        except Exception:
            return None

    def fetch_local_usage(self):
        """Fetch usage from local JSONL files"""
        try:
            limit_5h = self._get_limit("estimated_5h_limit", 500_000)
            limit_weekly = self._get_limit("estimated_weekly_limit", 5_000_000)
            return self._calculator.get_usage_summary(
                limit_5h=limit_5h,
                limit_weekly=limit_weekly
            )
        except Exception as e:
            logger.error("local usage calculation error: %s", e)
            return None

    def _interruptible_sleep(self, ms):
        """Sleep in small increments so stop() takes effect quickly"""
        remaining = ms
        while remaining > 0 and self._running:
            chunk = min(remaining, 500)
            self.msleep(chunk)
            remaining -= chunk

    def run(self):
        while self._running:
            web_accounts = load_accounts()
            cc_accounts = load_cc_accounts()
            all_accounts = web_accounts + cc_accounts

            if all_accounts:
                logger.debug("polling %d accounts (%d web, %d cc)",
                             len(all_accounts), len(web_accounts), len(cc_accounts))
                results = []
                for account in all_accounts:
                    if not self._running:
                        return
                    acct_type = account.get("type", "web")
                    if acct_type == "cc":
                        api_data = self.fetch_claude_api_usage(oauth_token=account["oauth_token"])
                    else:
                        api_data = self.fetch_claude_api_usage(session_key=account["sessionKey"])
                    if api_data:
                        api_data["name"] = account["name"]
                        api_data["type"] = acct_type
                        if acct_type == "cc":
                            api_data["cc_active"] = account.get("active", False)
                        results.append(api_data)
                        logger.debug("account %s (%s): ok (source=%s)",
                                     account["name"], acct_type, api_data.get("source"))
                    else:
                        entry = {
                            "name": account["name"],
                            "available": False,
                            "source": "none",
                            "type": acct_type,
                        }
                        if acct_type == "cc":
                            entry["cc_active"] = account.get("active", False)
                        results.append(entry)
                        logger.warning("account %s (%s): all API fallbacks failed",
                                       account["name"], acct_type)
                self.usage_updated.emit(results)
                logger.debug("poll complete, sleeping 30s")
                self._interruptible_sleep(30000)
                continue

            # No accounts configured — fall back to local JSONL parsing
            local_data = self.fetch_local_usage()
            if local_data:
                logger.debug("local usage: ok (estimated=%s)", local_data.get("is_estimated"))
                self.usage_updated.emit([local_data])
                logger.debug("poll complete, sleeping 30s")
                self._interruptible_sleep(30000)
                continue

            # No data available
            logger.debug("no accounts and no local data, sleeping 30s")
            self.usage_updated.emit([{"available": False, "source": "none"}])
            self._interruptible_sleep(30000)

    def stop(self):
        self._running = False
