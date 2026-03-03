"""
Chrome Cookie Scanner - Extract Claude session cookies from Chrome profiles

Discovers all local Chrome profiles, resolves profile names,
and extracts sessionKey cookies for claude.ai using pycookiecheat.

On Linux, Chrome encrypts cookies with a key stored in the system keyring.
This module retrieves that key via gi.repository.Secret (direct import),
falling back to a subprocess call to system Python when gi is not available
in the current interpreter (e.g. conda environments).
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

__all__ = ["scan_chrome_sessions", "is_pycookiecheat_available", "ChromeScanWorker"]

logger = logging.getLogger("wt-control.chrome-cookies")


def is_pycookiecheat_available() -> bool:
    """Check if pycookiecheat is installed and importable."""
    try:
        import pycookiecheat  # noqa: F401
        return True
    except Exception as e:
        logger.info("pycookiecheat not importable: %s: %s", type(e).__name__, e)
        return False


def _get_chrome_data_dir() -> Path | None:
    """Get the platform-specific Chrome user data directory."""
    if sys.platform == "linux":
        path = Path.home() / ".config" / "google-chrome"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    else:
        return None

    return path if path.is_dir() else None


def _get_chrome_password() -> str | None:
    """Get Chrome Safe Storage password from the system keyring.

    Tries gi.repository.Secret directly, then falls back to subprocess
    calling system Python (for conda/venv where gi is unavailable).
    On macOS, pycookiecheat handles keyring access internally.
    """
    if sys.platform == "darwin":
        return None  # macOS uses Keychain, handled by pycookiecheat

    # Try direct gi import
    try:
        import gi
        gi.require_version("Secret", "1")
        from gi.repository import Secret

        service = Secret.Service.get_sync(Secret.ServiceFlags.LOAD_COLLECTIONS)
        collections = service.get_collections()
        unlocked = service.unlock_sync(collections).unlocked

        for collection in unlocked:
            for item in collection.get_items():
                if item.get_label() == "Chrome Safe Storage":
                    attrs = item.get_attributes()
                    if attrs.get("application") == "chrome":
                        item.load_secret_sync()
                        return item.get_secret().get_text()
    except Exception:
        logger.debug("gi.repository.Secret not available, trying subprocess")

    # Fallback: call system Python to read the keyring
    script = (
        "import gi; gi.require_version('Secret','1'); "
        "from gi.repository import Secret; "
        "s=Secret.Service.get_sync(Secret.ServiceFlags.LOAD_COLLECTIONS); "
        "cs=s.get_collections(); us=s.unlock_sync(cs).unlocked\n"
        "for c in us:\n"
        " for i in c.get_items():\n"
        "  if i.get_label()=='Chrome Safe Storage' "
        "and i.get_attributes().get('application')=='chrome':\n"
        "   i.load_secret_sync(); print(i.get_secret().get_text()); raise SystemExit\n"
    )
    for python in ("/usr/bin/python3", "/usr/bin/python"):
        try:
            result = subprocess.run(
                [python, "-c", script],
                capture_output=True, text=True, timeout=10,
            )
            password = result.stdout.strip().split("\n")[0]
            if password:
                return password
        except Exception:
            continue

    logger.warning("Could not retrieve Chrome keyring password")
    return None


def _discover_profiles(chrome_dir: Path) -> list[Path]:
    """Discover Chrome profile directories containing a Preferences file."""
    profiles = []
    for entry in sorted(chrome_dir.iterdir()):
        if not entry.is_dir():
            continue
        # Chrome profiles are "Default", "Profile 1", "Profile 2", etc.
        if entry.name == "Default" or entry.name.startswith("Profile "):
            if (entry / "Preferences").exists():
                profiles.append(entry)
    return profiles


def _resolve_profile_name(profile_dir: Path) -> str:
    """Resolve a human-readable name from a Chrome profile's Preferences."""
    try:
        with open(profile_dir / "Preferences") as f:
            prefs = json.load(f)
    except Exception:
        return profile_dir.name

    # Try Google account name first
    account_info = prefs.get("account_info")
    if isinstance(account_info, list) and account_info:
        full_name = account_info[0].get("full_name", "")
        if full_name:
            return f"{full_name} ({profile_dir.name})"

    # Fallback to Chrome profile display name
    profile_name = prefs.get("profile", {}).get("name", "")
    if profile_name:
        return profile_name

    # Last resort: directory name
    return profile_dir.name


def _extract_session_cookie(profile_dir: Path, password: str | None = None) -> str | None:
    """Extract the sessionKey cookie for claude.ai from a Chrome profile."""
    try:
        from pycookiecheat import chrome_cookies
    except ImportError:
        return None

    cookie_file = profile_dir / "Cookies"
    if not cookie_file.exists():
        return None

    try:
        kwargs: dict = {
            "url": "https://claude.ai",
            "cookie_file": str(cookie_file),
        }
        if password is not None:
            kwargs["password"] = password
        cookies = chrome_cookies(**kwargs)
        return cookies.get("sessionKey") or None
    except Exception as e:
        logger.debug("Failed to extract cookie from %s: %s", profile_dir.name, e)
        return None


def _fetch_org_name(session_key: str) -> str | None:
    """Fetch the Claude organization name using a session key."""
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(
            "https://claude.ai/api/organizations",
            cookies={"sessionKey": session_key},
            impersonate="chrome",
            timeout=10,
        )
        orgs = r.json()
    except Exception:
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "10",
                 "-b", f"sessionKey={session_key}",
                 "https://claude.ai/api/organizations"],
                capture_output=True, text=True, timeout=15,
            )
            orgs = json.loads(result.stdout)
        except Exception:
            return None

    if isinstance(orgs, list) and orgs:
        name = orgs[0].get("name", "")
        # Strip common suffixes for shorter display names
        for suffix in ("'s Organization", "'s Individual Org"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return name or None
    return None



def scan_chrome_sessions(force_refresh: bool = False, existing_accounts: list[dict] | None = None) -> list[dict]:
    """Scan all Chrome profiles for Claude session cookies.

    Args:
        force_refresh: If True, always re-fetch org names from the API.
            If False, use cached org_name when sessionKey hasn't changed.
        existing_accounts: Current accounts list for cache lookup.
            Only accounts with source="chrome-scan" are considered for caching.

    Returns a list of {"name": str, "sessionKey": str, "org_name": str|None, "source": "chrome-scan"} dicts,
    one per profile that has a valid sessionKey cookie.
    Returns empty list if Chrome is not found or no sessions exist.
    Raises ImportError if pycookiecheat is not installed.
    """
    if not is_pycookiecheat_available():
        raise ImportError("pycookiecheat is not installed")

    chrome_dir = _get_chrome_data_dir()
    if not chrome_dir:
        logger.info("Chrome data directory not found")
        return []

    profiles = _discover_profiles(chrome_dir)
    if not profiles:
        logger.info("No Chrome profiles found in %s", chrome_dir)
        return []

    # Build cache: sessionKey -> org_name from existing chrome-scan accounts
    cache: dict[str, str] = {}
    if not force_refresh and existing_accounts:
        for acct in existing_accounts:
            if acct.get("source") == "chrome-scan" and acct.get("org_name") and acct.get("sessionKey"):
                cache[acct["sessionKey"]] = acct["org_name"]

    # Get keyring password once for all profiles
    password = _get_chrome_password()

    results = []
    seen_names: set[str] = set()
    for profile_dir in profiles:
        session_key = _extract_session_cookie(profile_dir, password=password)
        if not session_key:
            logger.debug("No Claude session in profile: %s", profile_dir.name)
            continue

        # Use cached org name if available, otherwise fetch from API
        org_name = cache.get(session_key)
        if org_name:
            logger.debug("Using cached org name for profile: %s", profile_dir.name)
        else:
            org_name = _fetch_org_name(session_key)

        name = org_name if org_name else _resolve_profile_name(profile_dir)

        # Deduplicate by name (same account from multiple Chrome profiles)
        if name in seen_names:
            logger.debug("Duplicate account %s in profile: %s", name, profile_dir.name)
            continue
        seen_names.add(name)

        results.append({
            "name": name,
            "sessionKey": session_key,
            "org_name": org_name,
            "source": "chrome-scan",
        })
        logger.info("Found session: %s", name)

    return results


def merge_scan_results(scan_results: list[dict], existing_accounts: list[dict]) -> list[dict]:
    """Merge scan results with existing accounts.

    Preserves manual accounts, updates/adds chrome-scan accounts.
    """
    # Keep all manual accounts
    merged = [a for a in existing_accounts if a.get("source") != "chrome-scan"]
    # Add scan results
    merged.extend(scan_results)
    return merged


try:
    from PySide6.QtCore import QThread, Signal

    class ChromeScanWorker(QThread):
        """Background thread for Chrome session scanning."""
        scan_finished = Signal(list)
        scan_error = Signal(str)

        def __init__(self, force_refresh: bool = False, existing_accounts: list[dict] | None = None):
            super().__init__()
            self._force_refresh = force_refresh
            self._existing_accounts = existing_accounts

        def run(self):
            try:
                results = scan_chrome_sessions(
                    force_refresh=self._force_refresh,
                    existing_accounts=self._existing_accounts,
                )
                self.scan_finished.emit(results)
            except Exception as e:
                self.scan_error.emit(str(e))

except ImportError:
    # PySide6 not available (e.g. in tests without Qt)
    ChromeScanWorker = None  # type: ignore[assignment, misc]
