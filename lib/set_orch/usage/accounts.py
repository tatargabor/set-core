"""Which accounts this machine can measure, and how each one authenticates.

Two credential stores exist and they are not interchangeable. The browser store
holds session cookies harvested from a logged-in Chrome profile; the CLI store
holds OAuth bearer tokens. Both grant access to the same account API, but they
fail differently: a scanned cookie expires with no notice and no event, and so
— *corrected 2026-09-07, measured* — does the CLI token's snapshot: the CLI
rotates its access token during ordinary use, so the copy in `cc-accounts.json`
drifts out of date within hours (the itline account answered 403 at the
organization lookup all day while the live CLI store answered 200). Discovery
therefore takes the active account's token from the live CLI store; see
`_cc_accounts`. A caller that cannot see which kind it is holding cannot tell
which failure it is looking at, so the kind travels with the account.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "Account",
    "discover_accounts",
    "config_dir",
    "purge_accounts",
    "KIND_WEB",
    "KIND_CC",
]

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


#: The Claude CLI's own credential store — the credential actually in use on
#: this machine right now. Read here, never written: writing it is the router's
#: job, with its own ownership check and file lock.
LIVE_CC_STORE = Path.home() / ".claude" / ".credentials.json"


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


def _cc_accounts(data, live_token: Optional[str] = None) -> List[Account]:
    """OAuth-token accounts written by the CLI account manager.

    The stored access token is a SNAPSHOT of a credential the CLI keeps
    rotating. Measured 2026-09-07: the store's token and the live CLI store's
    token had drifted apart, and the account answered 403 at the organization
    lookup for hours while the live store answered — so where the store names
    an active account, that account's token comes from the live store at
    discovery time. The poller re-discovers on every refresh, so the figure
    rides the rotation instead of chasing it.

    Matching is by the `active` name, deliberately not by token shape: a
    rotated token shares nothing with its predecessor. If the live file is
    actually holding a different account, the result is a 403 and an
    `unreachable` minute — a wrong figure is not possible, only a missing one,
    and the next poll re-reads.
    """
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
        if live_token and name == active_name:
            token = live_token
        out.append(
            Account(
                name=name,
                kind=KIND_CC,
                credential=token,
                active=(name == active_name),
            )
        )
    return out


def discover_accounts(directory: Path | None = None,
                      live_path: Path | None = None) -> List[Account]:
    """Every account with a usable credential, browser-derived ones first.

    An entry with no credential is not an account: reporting it would make the
    list longer without making anything measurable, and a row that can never
    carry a figure is indistinguishable on screen from one that failed today.

    `live_path` exists for tests: the live CLI store is machine state, and a
    fixture must be able to stand in for it the same way `directory` stands in
    for the owned stores.
    """
    base = directory or config_dir()
    live = _load_json(live_path or LIVE_CC_STORE)
    live_token = (live or {}).get("claudeAiOauth", {}).get("accessToken") or None
    web = _web_accounts(_load_json(base / "claude-session.json"))
    cc = _cc_accounts(_load_json(base / "cc-accounts.json"), live_token)
    logger.debug("discovered %d account(s): %d web, %d cc", len(web) + len(cc), len(web), len(cc))
    return web + cc


# ---- purging -------------------------------------------------------------

#: A credential that lives in the provider configuration, not in a store this
#: module owns. `providers.json` is a hand-edited data file by design — removing
#: a provider credential is a deliberate configuration act, never a button.
PROVIDER_KIND = "glm"


def _purge_web(path: Path, name: str) -> Dict[str, Any]:
    """Drop every entry named `name` from the browser session store.

    Removal is by the name the strip displays, because that is the identity the
    operator confirmed; entries sharing it go together. The survivors are
    written back atomically, always in the current multi-account shape, with
    owner-only permissions — the store never regresses to the legacy
    single-key form a purge could otherwise reintroduce.
    """
    data = _load_json(path)
    if data is None:
        return {"outcome": "refused", "reason": "no browser session store exists"}
    if isinstance(data, dict) and isinstance(data.get("accounts"), list):
        entries = data["accounts"]
    elif isinstance(data, dict) and data.get("sessionKey"):
        # Legacy single-key shape: the sole entry discovered as "Default".
        entries = [{"name": "Default", "sessionKey": data["sessionKey"]}]
    else:
        return {"outcome": "refused", "reason": "browser session store is unreadable"}

    keep = [e for e in entries if not (isinstance(e, dict) and e.get("name") == name)]
    dropped = len(entries) - len(keep)
    if dropped == 0:
        return {"outcome": "refused", "reason": f"no entry named {name!r} in the browser session store"}

    try:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as fh:
            json.dump({"accounts": keep}, fh, indent=2)
        tmp.replace(path)
        os.chmod(path, 0o600)
    except OSError as exc:
        logger.warning("browser session store purge failed to write: %s", type(exc).__name__)
        return {"outcome": "refused", "reason": "the store could not be written"}
    logger.info("purged %d browser session account(s) named %r", dropped, name)
    return {"outcome": "removed", "removed": dropped}


def purge_accounts(targets, directory: Path | None = None, pool=None) -> Dict[str, Any]:
    """Remove named accounts from this machine's credential stores.

    `targets` is a list of `{kind, name}` — the same identity the usage
    snapshot carries. Each target is applied independently: one refusal never
    stops the others, and the answer separates what was removed from what was
    refused, by name, with a reason. No credential travels in the answer — a
    removal is exactly the moment a secret is in hand.
    """
    base = directory or config_dir()
    results: List[Dict[str, Any]] = []

    for target in targets:
        if not isinstance(target, dict):
            continue
        kind = target.get("kind")
        name = target.get("name")
        if not kind or not name:
            results.append({"kind": kind, "name": name,
                            "outcome": "refused", "reason": "a target needs a kind and a name"})
            continue

        if kind == PROVIDER_KIND:
            results.append({
                "kind": kind, "name": name, "outcome": "refused",
                "reason": ("a provider credential lives in providers.json, which is edited "
                           "by hand — remove it there, not here"),
            })
            continue

        if kind == KIND_WEB:
            outcome = _purge_web(base / "claude-session.json", name)
            results.append({"kind": kind, "name": name, **outcome})
            continue

        if kind == KIND_CC:
            if pool is None:
                from set_router import AccountPool  # local: keeps the CLI import off this module's load
                pool = AccountPool()
            try:
                detail = pool.remove(name)
            except KeyError:
                results.append({"kind": kind, "name": name, "outcome": "refused",
                                "reason": f"no CLI account named {name!r}"})
                continue
            except ValueError as exc:
                results.append({"kind": kind, "name": name, "outcome": "refused",
                                "reason": str(exc)})
                continue
            logger.info("purged CLI account %r: %s", name, detail)
            results.append({"kind": kind, "name": name, "outcome": "removed", "detail": detail})
            continue

        results.append({"kind": kind, "name": name, "outcome": "refused",
                        "reason": f"unknown account kind {kind!r}"})

    removed = sum(1 for r in results if r.get("outcome") == "removed")
    return {"results": results, "removed": removed, "refused": len(results) - removed}
