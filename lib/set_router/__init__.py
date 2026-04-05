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
    """Manages a pool of Claude Code OAuth credentials.

    Accounts are identified by email address (from CC /stats → Email field).
    """

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
        os.chmod(CC_ACCOUNTS_FILE, stat.S_IRUSR | stat.S_IWUSR)

    @property
    def accounts(self) -> list[dict]:
        return self._data.get("accounts", [])

    @property
    def active_email(self) -> str | None:
        return self._data.get("active")

    def _email(self, acct: dict) -> str:
        """Get the email identifier from an account entry (supports old 'name' format)."""
        return acct.get("email", acct.get("name", ""))

    def get(self, email: str) -> dict | None:
        for acct in self.accounts:
            if self._email(acct) == email:
                return acct
        return None

    def add(self, email: str) -> str:
        """Add current ~/.claude/.credentials.json under the given email.

        Returns a status message.
        """
        if not CC_CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                "No Claude Code credentials found. Run `claude login` first."
            )

        with open(CC_CREDENTIALS_FILE) as f:
            creds = json.load(f)

        oauth = creds.get("claudeAiOauth", {})
        for field in _REQUIRED_CRED_FIELDS:
            if not oauth.get(field):
                raise ValueError(
                    f"Credentials missing '{field}'. Run `claude login` to get valid credentials."
                )

        existing = self.get(email)
        entry = {
            "email": email,
            "credentials": creds,
            "source": "manual",
            "added_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing:
            for i, acct in enumerate(self._data["accounts"]):
                if self._email(acct) == email:
                    self._data["accounts"][i] = entry
                    break
            self._save()
            return f"Updated account '{email}'"

        self._data["accounts"].append(entry)
        if not self._data.get("active"):
            self._data["active"] = email
        self._save()
        return f"Added account '{email}'"

    def remove(self, email: str) -> str:
        """Remove an account by email. Returns a status message."""
        if not self.get(email):
            raise KeyError(f"Account '{email}' not found")

        if len(self.accounts) <= 1:
            raise ValueError("Cannot remove the last account")

        self._data["accounts"] = [a for a in self.accounts if self._email(a) != email]

        if self._data.get("active") == email:
            self._data["active"] = self._email(self._data["accounts"][0])
            self._swap_credentials(self._data["active"])
            self._save()
            return f"Removed '{email}'. Switched to '{self._data['active']}'"

        self._save()
        return f"Removed account '{email}'"

    def switch(self, email: str) -> str:
        """Switch active CC account. Returns status message.

        Before swapping, saves the current credentials file back to the
        active account's pool entry — CC may have refreshed the token.
        """
        if not self.get(email):
            raise KeyError(f"Account '{email}' not found")

        if self._data.get("active") == email:
            return f"'{email}' is already the active account."

        self._save_current_credentials()
        self._swap_credentials(email)
        self._data["active"] = email
        self._save()
        return f"Switched to '{email}'. New CC instances will use this account."

    def _save_current_credentials(self):
        """Read ~/.claude/.credentials.json and update the active account's stored credentials.

        Verifies the live token belongs to the active account before saving,
        by comparing token suffixes.
        """
        active = self._data.get("active")
        if not active or not CC_CREDENTIALS_FILE.exists():
            return
        try:
            with open(CC_CREDENTIALS_FILE) as f:
                current_creds = json.load(f)
            live_token = current_creds.get("claudeAiOauth", {}).get("accessToken", "")
            if not live_token:
                return

            acct = self.get(active)
            if not acct:
                return

            stored_token = acct.get("credentials", {}).get("claudeAiOauth", {}).get("accessToken", "")

            if stored_token and live_token[-20:] != stored_token[-20:]:
                owner = None
                for a in self.accounts:
                    a_token = a.get("credentials", {}).get("claudeAiOauth", {}).get("accessToken", "")
                    if a_token and live_token[-20:] == a_token[-20:]:
                        owner = self._email(a)
                        break

                if owner:
                    logger.warning(
                        "Live credentials belong to '%s', not active '%s'. Saving to '%s'.",
                        owner, active, owner)
                    for i, a in enumerate(self._data["accounts"]):
                        if self._email(a) == owner:
                            self._data["accounts"][i]["credentials"] = current_creds
                            break
                else:
                    logger.warning(
                        "Live credentials don't match any stored account (token ...%s). "
                        "Run `set-router add <email>` to register it.", live_token[-15:])
                return

            for i, a in enumerate(self._data["accounts"]):
                if self._email(a) == active:
                    self._data["accounts"][i]["credentials"] = current_creds
                    logger.info("Saved refreshed credentials for '%s'", active)
                    break
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not save current credentials: %s", e)

    def _swap_credentials(self, email: str):
        """Write the account's credentials to ~/.claude/.credentials.json with file locking."""
        acct = self.get(email)
        if not acct:
            raise KeyError(f"Account '{email}' not found")

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
                "email": self._email(acct),
                "active": self._email(acct) == self.active_email,
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
        """Return active account info."""
        if not self.active_email:
            return None
        acct = self.get(self.active_email)
        if not acct:
            return None
        oauth = acct.get("credentials", {}).get("claudeAiOauth", {})
        return {
            "email": self.active_email,
            "subscription_type": oauth.get("subscriptionType"),
            "rate_limit_tier": oauth.get("rateLimitTier"),
            "expires_at": oauth.get("expiresAt"),
        }
