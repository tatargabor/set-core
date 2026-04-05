"""
Usage Worker - Background thread for fetching Claude usage data

Primary: Local JSONL parsing (cross-platform, no auth needed)
Secondary: Claude.ai API with session key (optional, for exact data)
Supports multiple accounts with per-account usage fetching.
"""

import json
import logging
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

from ..constants import CONFIG_DIR, CLAUDE_SESSION_FILE
from ..usage_calculator import UsageCalculator

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

__all__ = ["UsageWorker", "load_accounts", "save_accounts", "load_cc_accounts"]

logger = logging.getLogger("set-control.workers.usage")

_API_BASE = "https://claude.ai/api"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) set-core/1.0",
    "Accept": "application/json",
}


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
            result.append({
                "name": acct["name"],
                "oauth_token": token,
                "type": "cc",
                "active": acct["name"] == active_name,
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
        self._cffi_warned = False

    def _get_limit(self, key: str, default: int) -> int:
        """Get usage limit from config"""
        if self._config:
            return self._config.get("usage", key, default)
        return default

    def _api_get(self, url: str, session_key: str):
        """Make an API GET request with session key cookie.

        Tries curl-cffi first (Chrome TLS fingerprint, bypasses Cloudflare),
        falls back to curl subprocess, then urllib.
        Returns parsed JSON or None on failure.
        """
        # Try curl-cffi first (impersonates Chrome TLS fingerprint)
        if cffi_requests is not None:
            try:
                resp = cffi_requests.get(
                    url,
                    headers={"Accept": "application/json"},
                    cookies={"sessionKey": session_key},
                    impersonate="chrome",
                    timeout=15,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        elif not self._cffi_warned:
            self._cffi_warned = True
            print("curl-cffi not installed — usage API may be blocked by Cloudflare. "
                  "Install with: pip install curl-cffi")

        # Fallback: try curl subprocess
        try:
            result = subprocess.run(
                ["curl", "-s", "-H", f"Cookie: sessionKey={session_key}",
                 "-H", "Accept: application/json",
                 "-H", f"User-Agent: {_HEADERS['User-Agent']}",
                 "--max-time", "15", url],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        # Fallback: try urllib
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            req.add_header("Cookie", f"sessionKey={session_key}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            pass

        return None

    def _api_get_oauth(self, url: str, oauth_token: str):
        """Make an API GET request with OAuth Bearer token.

        Used for Claude Code accounts. Same fallback chain as _api_get
        but uses Authorization header instead of session cookie.
        Returns parsed JSON or None on failure.
        """
        auth_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {oauth_token}",
        }

        # Try curl-cffi first
        if cffi_requests is not None:
            try:
                resp = cffi_requests.get(
                    url, headers=auth_headers,
                    impersonate="chrome", timeout=15,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass

        # Fallback: curl subprocess
        try:
            result = subprocess.run(
                ["curl", "-s",
                 "-H", f"Authorization: Bearer {oauth_token}",
                 "-H", "Accept: application/json",
                 "-H", f"User-Agent: {_HEADERS['User-Agent']}",
                 "--max-time", "15", url],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        # Fallback: urllib
        try:
            req = urllib.request.Request(url, headers={**_HEADERS, **auth_headers})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            pass

        return None

    def fetch_claude_api_usage(self, session_key=None, oauth_token=None):
        """Fetch usage from Claude.ai API using session key or OAuth token."""
        try:
            getter = self._api_get_oauth if oauth_token else self._api_get
            auth = oauth_token or session_key
            orgs = getter(f"{_API_BASE}/organizations", auth)
            if not orgs or not isinstance(orgs, list):
                return None

            # Find the claude_max org (not api org)
            org_id = None
            for org in orgs:
                if 'claude_max' in org.get('capabilities', []):
                    org_id = org.get('uuid')
                    break
            if not org_id:
                org_id = orgs[0].get('uuid')

            if not org_id:
                return None

            return self._fetch_org_usage(org_id, session_key=session_key, oauth_token=oauth_token)
        except Exception:
            return None

    def _fetch_org_usage(self, org_id, session_key=None, oauth_token=None):
        """Fetch usage for specific organization"""
        try:
            getter = self._api_get_oauth if oauth_token else self._api_get
            auth = oauth_token or session_key
            data = getter(f"{_API_BASE}/organizations/{org_id}/usage", auth)
            if not data:
                return None

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
        except Exception:
            return None

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
