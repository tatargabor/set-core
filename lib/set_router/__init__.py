"""
set-router — Claude Code account manager

Manual account management for multiple Claude Code OAuth credentials.
NOT an automatic rotation system. All switching is user-initiated.
"""

import fcntl
import json
import logging
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("set-router")

_config_override = os.environ.get("SET_CONFIG_DIR")
CONFIG_DIR = Path(_config_override) if _config_override else Path.home() / ".config" / "set-core"
CC_ACCOUNTS_FILE = CONFIG_DIR / "cc-accounts.json"
CC_CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"

_REQUIRED_CRED_FIELDS = ("accessToken", "refreshToken")


class AccountPool:
    """Manages a pool of Claude Code OAuth credentials."""

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        try:
            if CC_ACCOUNTS_FILE.exists():
                with open(CC_ACCOUNTS_FILE) as f:
                    data = json.load(f)
                if isinstance(data.get("accounts"), list):
                    return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s: %s", CC_ACCOUNTS_FILE, e)
        return {"accounts": [], "active": None}

    def _save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CC_ACCOUNTS_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
        tmp.replace(CC_ACCOUNTS_FILE)
        # Enforce 600 permissions
        os.chmod(CC_ACCOUNTS_FILE, stat.S_IRUSR | stat.S_IWUSR)

    @property
    def accounts(self) -> list[dict]:
        return self._data.get("accounts", [])

    @property
    def active_name(self) -> str | None:
        return self._data.get("active")

    def get(self, name: str) -> dict | None:
        for acct in self.accounts:
            if acct["name"] == name:
                return acct
        return None

    def add(self, name: str) -> str:
        """Add current ~/.claude/.credentials.json as a named account.

        Returns a status message.
        """
        if not CC_CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                "No Claude Code credentials found. Run `claude login` first."
            )

        with open(CC_CREDENTIALS_FILE) as f:
            creds = json.load(f)

        # Validate required fields
        oauth = creds.get("claudeAiOauth", {})
        for field in _REQUIRED_CRED_FIELDS:
            if not oauth.get(field):
                raise ValueError(
                    f"Credentials missing '{field}'. Run `claude login` to get valid credentials."
                )

        existing = self.get(name)
        entry = {
            "name": name,
            "credentials": creds,
            "source": "manual",
            "added_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing:
            # Update in place
            for i, acct in enumerate(self._data["accounts"]):
                if acct["name"] == name:
                    self._data["accounts"][i] = entry
                    break
            self._save()
            return f"Updated existing account '{name}'"

        self._data["accounts"].append(entry)
        if not self._data.get("active"):
            self._data["active"] = name
        self._save()
        return f"Added account '{name}'"

    def remove(self, name: str) -> str:
        """Remove a named account. Returns a status message."""
        if not self.get(name):
            raise KeyError(f"Account '{name}' not found")

        if len(self.accounts) <= 1:
            raise ValueError("Cannot remove the last account")

        self._data["accounts"] = [a for a in self.accounts if a["name"] != name]

        # If we removed the active account, switch to the first remaining
        if self._data.get("active") == name:
            self._data["active"] = self._data["accounts"][0]["name"]
            self._swap_credentials(self._data["active"])
            self._save()
            return f"Removed '{name}'. Switched to '{self._data['active']}'"

        self._save()
        return f"Removed account '{name}'"

    def switch(self, name: str) -> str:
        """Switch active CC account by swapping credentials file. Returns status message.

        Before swapping, saves the current credentials file back to the
        active account's pool entry — CC may have refreshed the token
        since the last switch.
        """
        if not self.get(name):
            raise KeyError(f"Account '{name}' not found")

        if self._data.get("active") == name:
            return f"'{name}' is already the active account."

        # Save current credentials back to the outgoing account
        self._save_current_credentials()

        self._swap_credentials(name)
        self._data["active"] = name
        self._save()
        return f"Switched to '{name}'. New CC instances will use this account."

    def _save_current_credentials(self):
        """Read ~/.claude/.credentials.json and update the active account's stored credentials."""
        active = self._data.get("active")
        if not active or not CC_CREDENTIALS_FILE.exists():
            return
        try:
            with open(CC_CREDENTIALS_FILE) as f:
                current_creds = json.load(f)
            # Only update if the file has valid OAuth data
            if not current_creds.get("claudeAiOauth", {}).get("accessToken"):
                return
            for i, acct in enumerate(self._data["accounts"]):
                if acct["name"] == active:
                    self._data["accounts"][i]["credentials"] = current_creds
                    logger.info("Saved refreshed credentials for '%s'", active)
                    break
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not save current credentials: %s", e)

    def _swap_credentials(self, name: str):
        """Write the named account's credentials to ~/.claude/.credentials.json with file locking."""
        acct = self.get(name)
        if not acct:
            raise KeyError(f"Account '{name}' not found")

        creds_dir = CC_CREDENTIALS_FILE.parent
        creds_dir.mkdir(parents=True, exist_ok=True)

        with open(CC_CREDENTIALS_FILE, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                f.truncate()
                json.dump(acct["credentials"], f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def list_accounts(self) -> list[dict]:
        """Return account summaries for display."""
        result = []
        for acct in self.accounts:
            result.append({
                "name": acct["name"],
                "active": acct["name"] == self.active_name,
                "source": acct.get("source", "manual"),
                "added_at": acct.get("added_at"),
                "subscription_type": acct.get("credentials", {})
                    .get("claudeAiOauth", {})
                    .get("subscriptionType"),
                "rate_limit_tier": acct.get("credentials", {})
                    .get("claudeAiOauth", {})
                    .get("rateLimitTier"),
            })
        return result

    def status(self) -> dict | None:
        """Return active account info for quick status display."""
        if not self.active_name:
            return None
        acct = self.get(self.active_name)
        if not acct:
            return None
        oauth = acct.get("credentials", {}).get("claudeAiOauth", {})
        return {
            "name": self.active_name,
            "subscription_type": oauth.get("subscriptionType"),
            "rate_limit_tier": oauth.get("rateLimitTier"),
            "expires_at": oauth.get("expiresAt"),
        }
