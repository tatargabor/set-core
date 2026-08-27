"""Which accounts this machine can measure, and how each one authenticates.

Two credential stores exist and they are not interchangeable. The browser store
holds session cookies harvested from a logged-in Chrome profile; the CLI store
holds OAuth bearer tokens. Both grant access to the same account API, but they
fail differently: a scanned cookie expires with no notice and no event, a token
does not. A caller that cannot see which kind it is holding cannot tell which
failure it is looking at, so the kind travels with the account.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

__all__ = ["Account", "discover_accounts", "config_dir"]

#: The two authentication kinds, named the same way everywhere downstream.
KIND_WEB = "web"
KIND_CC = "cc"


def config_dir() -> Path:
    """Where the credential stores live.

    Honours `WT_CONFIG_DIR` for the same reason the desktop side does: a test
    must be able to point both readers at a fixture directory, and two different
    override names would let them drift apart.
    """
    override = os.environ.get("WT_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".config" / "set-core"


@dataclass
class Account:
    """One measurable account.

    `credential` is here because the client needs it and nothing else does. It is
    kept out of `repr` so a stray log line or an exception rendering of this
    object cannot print it — the leak path that needs no decision to happen.
    """

    name: str
    kind: str
    credential: str = field(repr=False)
    #: Only meaningful for CC accounts: whether the CLI is currently using it.
    active: bool = False

    @property
    def is_oauth(self) -> bool:
        return self.kind == KIND_CC


def _load_json(path: Path):
    try:
        if not path.exists():
            return None
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("credential store unreadable: %s (%s)", path.name, type(exc).__name__)
        return None


def _web_accounts(data) -> List[Account]:
    """Browser-derived session keys.

    Two on-disk shapes exist — a list under `accounts`, and an older single
    `sessionKey` — and both are still found in the wild. Deduplication prefers a
    manually entered key over a scanned one when both carry the same value,
    because the scanned copy is the one that disappears when the profile is
    cleared.
    """
    if not isinstance(data, dict):
        return []

    entries = data.get("accounts")
    if isinstance(entries, list):
        by_key = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = entry.get("sessionKey")
            if not key:
                continue
            if key not in by_key or entry.get("source") != "chrome-scan":
                by_key[key] = entry
        return [
            Account(
                name=entry.get("name") or "unknown",
                kind=KIND_WEB,
                credential=entry["sessionKey"],
            )
            for entry in by_key.values()
        ]

    legacy = data.get("sessionKey")
    if legacy:
        return [Account(name="Default", kind=KIND_WEB, credential=legacy)]
    return []


def _cc_accounts(data) -> List[Account]:
    """OAuth-token accounts written by the CLI account manager."""
    if not isinstance(data, dict):
        return []

    active_name = data.get("active")
    out: List[Account] = []
    for entry in data.get("accounts") or []:
        if not isinstance(entry, dict):
            continue
        oauth = (entry.get("credentials") or {}).get("claudeAiOauth") or {}
        token = oauth.get("accessToken")
        if not token:
            continue
        name = entry.get("email") or entry.get("name") or "unknown"
        out.append(
            Account(
                name=name,
                kind=KIND_CC,
                credential=token,
                active=(name == active_name),
            )
        )
    return out


def discover_accounts(directory: Path | None = None) -> List[Account]:
    """Every account with a usable credential, browser-derived ones first.

    An entry with no credential is not an account: reporting it would make the
    list longer without making anything measurable, and a row that can never
    carry a figure is indistinguishable on screen from one that failed today.
    """
    base = directory or config_dir()
    web = _web_accounts(_load_json(base / "claude-session.json"))
    cc = _cc_accounts(_load_json(base / "cc-accounts.json"))
    logger.debug("discovered %d account(s): %d web, %d cc", len(web) + len(cc), len(web), len(cc))
    return web + cc
