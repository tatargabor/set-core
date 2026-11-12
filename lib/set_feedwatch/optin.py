"""The per-account opt-in for the scheduled pane — stored outside every repository.

`<set-core config dir>/feed-watch.json`:

    {"projects": {"<project root>": {"enabled": true, "account": "<e-mail>",
                                     "times": ["08:30", "18:30"]}}}

The pane is active only where an entry is enabled AND its account is the account the
Claude session runs as — so a shared machine, or a second account, never gets asked.
`on` also adds set-core's pane plugin to the user's own `CLAUDE_CODE_PLUGIN_DIRS`
(with a backup of the settings file); nothing is written into the project's tree.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMES = ["08:30", "18:30"]
HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "feed-watch-pane"


def config_dir() -> Path:
    from set_orch.local_config import config_dir as _cd
    return _cd()


def optin_path() -> Path:
    return config_dir() / "feed-watch.json"


def state_path() -> Path:
    return config_dir() / "feed-watch.state.json"


def claude_dir() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(d) if d else Path.home() / ".claude"


def claude_json() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(d) / ".claude.json" if d else Path.home() / ".claude.json"


def account_email() -> str:
    try:
        acct = json.loads(claude_json().read_text(encoding="utf-8")).get("oauthAccount") or {}
        return str(acct.get("emailAddress") or "").strip()
    except (OSError, ValueError):
        return ""


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load() -> dict:
    data = read_json(optin_path(), {})
    if not isinstance(data, dict) or not isinstance(data.get("projects"), dict):
        data = {"projects": {}}
    return data


def entry(root: Path) -> Optional[dict]:
    return _load()["projects"].get(str(root))


def set_entry(root: Path, **fields) -> dict:
    data = _load()
    old = dict(data["projects"].get(str(root)) or {})
    new = {**old, **fields}
    data["projects"][str(root)] = new
    write_json(optin_path(), data)
    logger.info("feed-watch opt-in for %s: %s -> %s", root,
                {k: old.get(k) for k in fields}, {k: new.get(k) for k in fields})
    return new


def parse_times(raw: Optional[str], fallback: List[str]) -> List[str]:
    times = [t.strip() for t in (raw or ",".join(fallback)).split(",") if t.strip()]
    bad = [t for t in times if not HHMM.fullmatch(t)]
    if bad or not times:
        raise ValueError(f"invalid time(s) {bad or times}: HH:MM expected")
    return sorted(set(times))


def is_active(e: Optional[dict], email: str) -> bool:
    return bool(e and e.get("enabled") is True and e.get("account") and email
                and str(e["account"]).lower() == email.lower())


# ---------------------------------------------------------------- plugin loading

def _settings_path() -> Path:
    return claude_dir() / "settings.json"


def plugin_dirs() -> List[str]:
    raw = ((read_json(_settings_path(), {}) or {}).get("env") or {}).get("CLAUDE_CODE_PLUGIN_DIRS", "")
    return [d for d in raw.split(os.pathsep) if d]


def _set_plugin_dirs(dirs: List[str]) -> Path:
    sp = _settings_path()
    settings = read_json(sp, {}) or {}
    backup = None
    if sp.exists():
        backup = sp.with_name(f"settings.json.bak.feed-watch-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(sp, backup)
    env = settings.setdefault("env", {})
    if dirs:
        env["CLAUDE_CODE_PLUGIN_DIRS"] = os.pathsep.join(dirs)
    else:
        env.pop("CLAUDE_CODE_PLUGIN_DIRS", None)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("CLAUDE_CODE_PLUGIN_DIRS updated in %s (backup: %s)", sp, backup)
    return sp


def load_plugin() -> bool:
    """Add the pane plugin to the user's plugin dirs. True when it was added now."""
    dirs = plugin_dirs()
    if str(PLUGIN_DIR) in dirs:
        return False
    _set_plugin_dirs(dirs + [str(PLUGIN_DIR)])
    return True


def unload_plugin() -> bool:
    dirs = plugin_dirs()
    if str(PLUGIN_DIR) not in dirs:
        return False
    _set_plugin_dirs([d for d in dirs if d != str(PLUGIN_DIR)])
    return True


def import_from(root: Path, source: Path) -> dict:
    """Copy enabled/account/times from an existing opt-in file. The source is only read."""
    raw = read_json(source, None)
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: not a readable JSON object")
    account = str(raw.get("account") or raw.get("user") or "").strip()
    if not account:
        raise ValueError(f"{source}: no account recorded (expected 'account' or 'user')")
    times = parse_times(",".join(raw.get("times") or []) or None, DEFAULT_TIMES)
    return set_entry(root, enabled=raw.get("enabled") is True, account=account, times=times)
