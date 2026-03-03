"""
Chrome Cookie Scanner Tests - Profile discovery, name resolution, and error handling.

These tests mock the filesystem and pycookiecheat to avoid requiring
a real Chrome installation or keyring access.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# --- Profile discovery tests ---


def test_discover_profiles_finds_default_and_numbered(tmp_path):
    """Discovers Default and Profile N directories with Preferences files."""
    from gui.workers.chrome_cookies import _discover_profiles

    # Create valid profiles
    for name in ("Default", "Profile 1", "Profile 2"):
        d = tmp_path / name
        d.mkdir()
        (d / "Preferences").write_text("{}")

    # Create non-profile directories (should be ignored)
    (tmp_path / "Crashpad").mkdir()
    (tmp_path / "Local State").touch()

    profiles = _discover_profiles(tmp_path)
    names = [p.name for p in profiles]
    assert names == ["Default", "Profile 1", "Profile 2"]


def test_discover_profiles_skips_without_preferences(tmp_path):
    """Skips profile directories that don't have a Preferences file."""
    from gui.workers.chrome_cookies import _discover_profiles

    (tmp_path / "Default").mkdir()  # No Preferences file
    p1 = tmp_path / "Profile 1"
    p1.mkdir()
    (p1 / "Preferences").write_text("{}")

    profiles = _discover_profiles(tmp_path)
    assert len(profiles) == 1
    assert profiles[0].name == "Profile 1"


def test_discover_profiles_empty_dir(tmp_path):
    """Returns empty list for a directory with no profiles."""
    from gui.workers.chrome_cookies import _discover_profiles

    profiles = _discover_profiles(tmp_path)
    assert profiles == []


# --- Profile name resolution tests ---


def test_resolve_name_google_account(tmp_path):
    """Uses Google account full_name when available."""
    from gui.workers.chrome_cookies import _resolve_profile_name

    profile = tmp_path / "Profile 1"
    profile.mkdir()
    (profile / "Preferences").write_text(json.dumps({
        "account_info": [{"full_name": "John Doe"}],
        "profile": {"name": "Work"},
    }))

    name = _resolve_profile_name(profile)
    assert name == "John Doe (Profile 1)"


def test_resolve_name_chrome_profile_fallback(tmp_path):
    """Falls back to Chrome profile name when no Google account."""
    from gui.workers.chrome_cookies import _resolve_profile_name

    profile = tmp_path / "Default"
    profile.mkdir()
    (profile / "Preferences").write_text(json.dumps({
        "profile": {"name": "Personal"},
    }))

    name = _resolve_profile_name(profile)
    assert name == "Personal"


def test_resolve_name_directory_fallback(tmp_path):
    """Falls back to directory name when no name in Preferences."""
    from gui.workers.chrome_cookies import _resolve_profile_name

    profile = tmp_path / "Profile 3"
    profile.mkdir()
    (profile / "Preferences").write_text("{}")

    name = _resolve_profile_name(profile)
    assert name == "Profile 3"


def test_resolve_name_broken_preferences(tmp_path):
    """Falls back to directory name when Preferences is invalid JSON."""
    from gui.workers.chrome_cookies import _resolve_profile_name

    profile = tmp_path / "Default"
    profile.mkdir()
    (profile / "Preferences").write_text("not json")

    name = _resolve_profile_name(profile)
    assert name == "Default"


def test_resolve_name_empty_account_info(tmp_path):
    """Falls back when account_info is empty list."""
    from gui.workers.chrome_cookies import _resolve_profile_name

    profile = tmp_path / "Profile 1"
    profile.mkdir()
    (profile / "Preferences").write_text(json.dumps({
        "account_info": [],
        "profile": {"name": "Fallback"},
    }))

    name = _resolve_profile_name(profile)
    assert name == "Fallback"


# --- Cookie extraction tests ---


def test_extract_cookie_success(tmp_path):
    """Extracts sessionKey cookie when pycookiecheat returns it."""
    profile = tmp_path / "Default"
    profile.mkdir()
    (profile / "Cookies").touch()

    mock_chrome_cookies = MagicMock(return_value={"sessionKey": "sk-ant-test123"})
    mock_module = MagicMock()
    mock_module.chrome_cookies = mock_chrome_cookies
    with patch.dict("sys.modules", {"pycookiecheat": mock_module}):
        import importlib
        import gui.workers.chrome_cookies as mod
        importlib.reload(mod)

        result = mod._extract_session_cookie(profile, password="testpass")

    assert result == "sk-ant-test123"
    mock_chrome_cookies.assert_called_once()
    call_kwargs = mock_chrome_cookies.call_args
    assert call_kwargs.kwargs.get("password") == "testpass" or call_kwargs[1].get("password") == "testpass"


def test_extract_cookie_no_cookies_file(tmp_path):
    """Returns None when Cookies file doesn't exist."""
    from gui.workers.chrome_cookies import _extract_session_cookie

    profile = tmp_path / "Default"
    profile.mkdir()
    # No Cookies file

    result = _extract_session_cookie(profile)
    assert result is None


def test_extract_cookie_no_session_key(tmp_path):
    """Returns None when pycookiecheat returns no sessionKey."""
    profile = tmp_path / "Default"
    profile.mkdir()
    (profile / "Cookies").touch()

    mock_chrome_cookies = MagicMock(return_value={"other_cookie": "value"})
    mock_module = MagicMock()
    mock_module.chrome_cookies = mock_chrome_cookies
    with patch.dict("sys.modules", {"pycookiecheat": mock_module}):
        import importlib
        import gui.workers.chrome_cookies as mod
        importlib.reload(mod)

        result = mod._extract_session_cookie(profile)

    assert result is None


def test_extract_cookie_no_password(tmp_path):
    """Works without password parameter (macOS or fallback)."""
    profile = tmp_path / "Default"
    profile.mkdir()
    (profile / "Cookies").touch()

    mock_chrome_cookies = MagicMock(return_value={"sessionKey": "sk-test"})
    mock_module = MagicMock()
    mock_module.chrome_cookies = mock_chrome_cookies
    with patch.dict("sys.modules", {"pycookiecheat": mock_module}):
        import importlib
        import gui.workers.chrome_cookies as mod
        importlib.reload(mod)

        result = mod._extract_session_cookie(profile, password=None)

    assert result == "sk-test"
    call_kwargs = mock_chrome_cookies.call_args[1]
    assert "password" not in call_kwargs


# --- Chrome data dir tests ---


def test_get_chrome_data_dir_linux(tmp_path, monkeypatch):
    """Returns correct path on Linux."""
    from gui.workers import chrome_cookies as mod

    monkeypatch.setattr(sys, "platform", "linux")
    chrome_dir = tmp_path / ".config" / "google-chrome"
    chrome_dir.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = mod._get_chrome_data_dir()
    assert result == chrome_dir


def test_get_chrome_data_dir_missing(tmp_path, monkeypatch):
    """Returns None when Chrome dir doesn't exist."""
    from gui.workers import chrome_cookies as mod

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = mod._get_chrome_data_dir()
    assert result is None


# --- Full scan tests ---


def test_scan_raises_without_pycookiecheat(monkeypatch):
    """scan_chrome_sessions raises ImportError when pycookiecheat is missing."""
    from gui.workers import chrome_cookies as mod

    monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: False)

    with pytest.raises(ImportError):
        mod.scan_chrome_sessions()


def test_scan_returns_empty_no_chrome(monkeypatch):
    """Returns empty list when Chrome data dir is not found."""
    from gui.workers import chrome_cookies as mod

    monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: True)
    monkeypatch.setattr(mod, "_get_chrome_data_dir", lambda: None)

    result = mod.scan_chrome_sessions()
    assert result == []


def test_scan_end_to_end(tmp_path, monkeypatch):
    """Full scan with mocked pycookiecheat discovers profiles and extracts cookies."""
    from gui.workers import chrome_cookies as mod

    # Create two profiles
    p1 = tmp_path / "Default"
    p1.mkdir()
    (p1 / "Preferences").write_text(json.dumps({
        "account_info": [{"full_name": "Alice"}],
    }))
    (p1 / "Cookies").touch()

    p2 = tmp_path / "Profile 1"
    p2.mkdir()
    (p2 / "Preferences").write_text(json.dumps({
        "profile": {"name": "Work"},
    }))
    (p2 / "Cookies").touch()

    # Profile with no Claude cookie
    p3 = tmp_path / "Profile 2"
    p3.mkdir()
    (p3 / "Preferences").write_text(json.dumps({
        "profile": {"name": "Kids"},
    }))
    (p3 / "Cookies").touch()

    def mock_chrome_cookies(url, cookie_file=None, password=None, **kwargs):
        cookie_file = cookie_file or ""
        if "Default" in cookie_file:
            return {"sessionKey": "sk-alice"}
        elif "Profile 1" in cookie_file:
            return {"sessionKey": "sk-work"}
        else:
            return {}

    monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: True)
    monkeypatch.setattr(mod, "_get_chrome_data_dir", lambda: tmp_path)
    monkeypatch.setattr(mod, "_get_chrome_password", lambda: "mock-password")

    mock_module = MagicMock()
    mock_module.chrome_cookies = mock_chrome_cookies
    with patch.dict("sys.modules", {"pycookiecheat": mock_module}):
        import importlib
        importlib.reload(mod)
        monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: True)
        monkeypatch.setattr(mod, "_get_chrome_data_dir", lambda: tmp_path)
        monkeypatch.setattr(mod, "_get_chrome_password", lambda: "mock-password")

        result = mod.scan_chrome_sessions(force_refresh=True)

    assert len(result) == 2
    assert result[0]["name"] == "Alice (Default)"
    assert result[0]["sessionKey"] == "sk-alice"
    assert result[0]["source"] == "chrome-scan"
    assert result[1]["name"] == "Work"
    assert result[1]["sessionKey"] == "sk-work"
    assert result[1]["source"] == "chrome-scan"


# --- Org name caching tests ---


def test_scan_uses_cached_org_name(tmp_path, monkeypatch):
    """Scan skips _fetch_org_name when cache has valid org_name for same sessionKey."""
    from gui.workers import chrome_cookies as mod

    p1 = tmp_path / "Default"
    p1.mkdir()
    (p1 / "Preferences").write_text(json.dumps({"profile": {"name": "Fallback"}}))
    (p1 / "Cookies").touch()

    def mock_chrome_cookies(url, cookie_file=None, password=None, **kwargs):
        return {"sessionKey": "sk-cached"}

    monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: True)
    monkeypatch.setattr(mod, "_get_chrome_data_dir", lambda: tmp_path)
    monkeypatch.setattr(mod, "_get_chrome_password", lambda: None)

    fetch_calls = []
    original_fetch = mod._fetch_org_name
    def tracking_fetch(sk):
        fetch_calls.append(sk)
        return original_fetch(sk)
    monkeypatch.setattr(mod, "_fetch_org_name", tracking_fetch)

    existing = [{"name": "Cached Org", "sessionKey": "sk-cached", "org_name": "Cached Org", "source": "chrome-scan"}]

    mock_module = MagicMock()
    mock_module.chrome_cookies = mock_chrome_cookies
    with patch.dict("sys.modules", {"pycookiecheat": mock_module}):
        import importlib
        importlib.reload(mod)
        monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: True)
        monkeypatch.setattr(mod, "_get_chrome_data_dir", lambda: tmp_path)
        monkeypatch.setattr(mod, "_get_chrome_password", lambda: None)
        monkeypatch.setattr(mod, "_fetch_org_name", tracking_fetch)

        result = mod.scan_chrome_sessions(force_refresh=False, existing_accounts=existing)

    assert len(result) == 1
    assert result[0]["name"] == "Cached Org"
    assert result[0]["org_name"] == "Cached Org"
    assert fetch_calls == []  # _fetch_org_name was NOT called


def test_scan_force_refresh_ignores_cache(tmp_path, monkeypatch):
    """force_refresh=True always calls _fetch_org_name even with valid cache."""
    from gui.workers import chrome_cookies as mod

    p1 = tmp_path / "Default"
    p1.mkdir()
    (p1 / "Preferences").write_text(json.dumps({"profile": {"name": "Fallback"}}))
    (p1 / "Cookies").touch()

    def mock_chrome_cookies(url, cookie_file=None, password=None, **kwargs):
        return {"sessionKey": "sk-cached"}

    fetch_calls = []
    def mock_fetch(sk):
        fetch_calls.append(sk)
        return "Fresh Org"

    monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: True)
    monkeypatch.setattr(mod, "_get_chrome_data_dir", lambda: tmp_path)
    monkeypatch.setattr(mod, "_get_chrome_password", lambda: None)

    existing = [{"name": "Old", "sessionKey": "sk-cached", "org_name": "Old", "source": "chrome-scan"}]

    mock_module = MagicMock()
    mock_module.chrome_cookies = mock_chrome_cookies
    with patch.dict("sys.modules", {"pycookiecheat": mock_module}):
        import importlib
        importlib.reload(mod)
        monkeypatch.setattr(mod, "is_pycookiecheat_available", lambda: True)
        monkeypatch.setattr(mod, "_get_chrome_data_dir", lambda: tmp_path)
        monkeypatch.setattr(mod, "_get_chrome_password", lambda: None)
        monkeypatch.setattr(mod, "_fetch_org_name", mock_fetch)

        result = mod.scan_chrome_sessions(force_refresh=True, existing_accounts=existing)

    assert len(result) == 1
    assert result[0]["name"] == "Fresh Org"
    assert fetch_calls == ["sk-cached"]


# --- Merge logic tests ---


def test_merge_preserves_manual_accounts():
    """merge_scan_results keeps manual accounts and adds scan results."""
    from gui.workers.chrome_cookies import merge_scan_results

    existing = [
        {"name": "Manual", "sessionKey": "sk-manual", "source": "manual"},
        {"name": "Old Scan", "sessionKey": "sk-old", "source": "chrome-scan"},
    ]
    scan_results = [
        {"name": "New Scan", "sessionKey": "sk-new", "source": "chrome-scan"},
    ]

    merged = merge_scan_results(scan_results, existing)

    names = [a["name"] for a in merged]
    assert "Manual" in names      # manual preserved
    assert "Old Scan" not in names  # old chrome-scan replaced
    assert "New Scan" in names     # new scan added
    assert len(merged) == 2


# --- Platform module fix test ---


def test_stdlib_platform_not_shadowed():
    """Verify importing gui.platform doesn't break stdlib platform.system()."""
    import platform as stdlib_platform
    # gui.platform is already imported at this point via gui.workers imports
    import gui.platform  # noqa: F401

    # stdlib platform should still work
    system = stdlib_platform.system()
    assert system in ("Linux", "Darwin", "Windows")
    assert hasattr(stdlib_platform, "system")
    assert hasattr(stdlib_platform, "machine")


# --- Menu integration test (requires pytest-qt) ---

_has_pytest_qt = False
try:
    import pytest_qt  # noqa: F401
    _has_pytest_qt = True
except ImportError:
    pass


@pytest.mark.skipif(not _has_pytest_qt, reason="pytest-qt not installed")
def test_main_menu_has_scan_chrome_item(control_center, qtbot):
    """Main menu should contain 'Scan Chrome Sessions' item."""
    from PySide6.QtWidgets import QMenu

    captured_actions = []

    original_init = QMenu.__init__

    def patched_init(menu_self, *args, **kwargs):
        original_init(menu_self, *args, **kwargs)
        original_exec = menu_self.exec

        def non_blocking_exec(*a, **kw):
            captured_actions.extend(
                act.text() for act in menu_self.actions() if not act.isSeparator()
            )
            return None

        menu_self.exec = non_blocking_exec

    QMenu.__init__ = patched_init
    try:
        control_center.show_main_menu()
    finally:
        QMenu.__init__ = original_init

    assert "Scan Chrome Sessions" in captured_actions
