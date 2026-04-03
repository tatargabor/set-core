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

logger = logging.getLogger("set-control.chrome-cookies")


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


def _validate_session(session_key: str) -> tuple[str, str | None]:
    """Validate a Claude session key and fetch the organization name.

    Returns:
        ("valid", org_name) — session is active, org name resolved
        ("expired", None) — definitive auth failure (401/403 or invalid response)
        ("error", None) — network issue, can't determine status
    """
    got_auth_error = False

    # Try curl-cffi first (Chrome TLS fingerprint, bypasses Cloudflare)
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(
            "https://claude.ai/api/organizations",
            cookies={"sessionKey": session_key},
            impersonate="chrome",
            timeout=10,
        )
        if r.status_code in (401, 403):
            logger.debug("Session expired (HTTP %d) via curl_cffi", r.status_code)
            return ("expired", None)
        if r.status_code == 200:
            try:
                orgs = r.json()
            except Exception:
                logger.debug("Session expired (invalid JSON response) via curl_cffi")
                return ("expired", None)
            return _parse_org_response(orgs)
        # Other HTTP errors (5xx, etc.) — try fallback
    except ImportError:
        pass
    except Exception as e:
        logger.debug("curl_cffi network error: %s", e)

    # Fallback: try curl subprocess with HTTP status code extraction
    try:
        result = subprocess.run(
            ["curl", "-s", "-m", "10", "-w", "\n%{http_code}",
             "-b", f"sessionKey={session_key}",
             "https://claude.ai/api/organizations"],
            capture_output=True, text=True, timeout=15,
        )
        lines = result.stdout.rsplit("\n", 1)
        body = lines[0] if len(lines) > 1 else result.stdout
        status_str = lines[-1].strip() if len(lines) > 1 else ""
        status_code = int(status_str) if status_str.isdigit() else 0

        if status_code in (401, 403):
            logger.debug("Session expired (HTTP %d) via curl", status_code)
            return ("expired", None)
        if status_code == 200 and body.strip():
            try:
                orgs = json.loads(body)
            except json.JSONDecodeError:
                logger.debug("Session expired (invalid JSON response) via curl")
                return ("expired", None)
            return _parse_org_response(orgs)
    except Exception as e:
        logger.debug("curl subprocess error: %s", e)

    return ("error", None)


def _parse_org_response(orgs) -> tuple[str, str | None]:
    """Parse the organizations API response into a validation result."""
    if isinstance(orgs, list) and orgs:
        name = orgs[0].get("name", "")
        for suffix in ("'s Organization", "'s Individual Org"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return ("valid", name or None)
    # Empty list or non-list response (e.g. HTML login page) = expired
    logger.debug("Session expired (empty or invalid org list)")
    return ("expired", None)



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

        # Use cached org name if available, otherwise validate via API
        cached_org = cache.get(session_key)
        if cached_org:
            logger.debug("Using cached org name for profile: %s", profile_dir.name)
            status, org_name = "valid", cached_org
        else:
            status, org_name = _validate_session(session_key)

        # Expired sessions are excluded
        if status == "expired":
            logger.info("Excluding expired session from profile: %s", profile_dir.name)
            continue

        entry: dict = {
            "sessionKey": session_key,
            "source": "chrome-scan",
        }

        if status == "valid" and org_name:
            entry["name"] = org_name
            entry["org_name"] = org_name
        else:
            # Network error — include but mark as unverified
            entry["name"] = _resolve_profile_name(profile_dir)
            entry["org_name"] = None
            entry["verified"] = False

        # Deduplicate by name (same account from multiple Chrome profiles)
        if entry["name"] in seen_names:
            logger.debug("Duplicate account %s in profile: %s", entry["name"], profile_dir.name)
            continue
        seen_names.add(entry["name"])

        results.append(entry)
        logger.info("Found session: %s (status=%s)", entry["name"], status)

    return results


def merge_scan_results(scan_results: list[dict], existing_accounts: list[dict]) -> list[dict]:
    """Merge scan results with existing accounts.

    Preserves only explicitly manual accounts. Legacy accounts (no source field)
    and chrome-scan accounts are replaced by fresh scan results.
    """
    # Keep only explicitly manual accounts
    merged = [a for a in existing_accounts if a.get("source") == "manual"]
    # Add scan results, but skip if sessionKey already exists in manual accounts
    manual_keys = {a.get("sessionKey") for a in merged}
    for sr in scan_results:
        if sr.get("sessionKey") not in manual_keys:
            merged.append(sr)
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
