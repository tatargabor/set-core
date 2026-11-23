"""The per-project `auto-clear` check (auto-clear-default-install, `machine-doctor`).

Auto-clear belongs in every deployed project (owner decision 2026-11-23). The check reads the
project tree, its settings and the user's systemd units, and reports ONE record: `ok`, `skip`
(opted out), or `warn` naming every gap with the command that closes the first one. It never
`fail`s — a missing watcher costs a compact, not correctness.

The handoff package itself (`set-claude-handoff`) is resolved through the project registry like
every other sibling; what counts as "current" is the package checkout's HEAD.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

PACKAGE = "set-claude-handoff"
# What `init --auto-clear` writes under .claude/hooks/, mapped to its source in the package.
# One list, here, until the package exposes a manifest (asked on the bus 2026-11-23).
HOOK_FILES = {
    "clear-gate.mjs": "templates/clear-gate.mjs",
    "handoff-reinject-clear.mjs": "templates/hooks/handoff-reinject-clear.mjs",
    "watch-auto-clear.sh": "templates/watch-auto-clear.sh",
    "presence.mjs": "templates/presence.mjs",
    "turn-state.mjs": "templates/turn-state.mjs",
    "handoff-arm.mjs": "templates/handoff-arm.mjs",
    "keep-going.mjs": "templates/keep-going.mjs",
}
WATCHER = ".claude/hooks/watch-auto-clear.sh"
THRESHOLD_FLAGS = ("--threshold", "--compact-threshold")


def _git(cwd: str, *args) -> str:
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("auto-clear: git %s in %s failed: %s", args[0], cwd, type(e).__name__)
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def package_path(registry: Optional[dict]) -> Optional[str]:
    entry = (registry or {}).get(PACKAGE) or {}
    p = os.path.expanduser(str(entry.get("path") or ""))
    return p if p and os.path.isdir(p) else None


def package_default_threshold(pkg: str) -> Optional[int]:
    """DEFAULT_THRESHOLD as the package's gate declares it (`400_000` → 400000)."""
    try:
        text = open(os.path.join(pkg, "templates", "clear-gate.mjs"), encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"export const DEFAULT_THRESHOLD\s*=\s*([\d_]+)", text)
    return int(m.group(1).replace("_", "")) if m else None


def native_trigger(home: str) -> Optional[int]:
    """0.9 x the compaction window the default model runs with (design D5).

    The per-model key wins over the top-level one (measured 2026-11-23: the top-level key read
    600000 while the per-model 400000 was the one that applied). The `model` setting may be an
    alias (`fable`); it resolves to the newest `claude-<alias>-*` key that sets a window.
    """
    try:
        s = json.load(open(os.path.join(home, ".claude", "settings.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None
    model = str(s.get("model") or "")
    per = {k: (v or {}).get("autoCompactWindow") for k, v in (s.get("modelSettings") or {}).items()}
    window = per.get(model)
    if not window and model:
        cands = sorted(k for k, w in per.items() if w and k.startswith(f"claude-{model}-"))
        window = per[cands[-1]] if cands else None
    window = window or s.get("autoCompactWindow")
    return int(window * 0.9) if isinstance(window, (int, float)) and window > 0 else None


def stale_templates(pkg: str, tree: str) -> tuple:
    """(missing, stale) file names under the tree's .claude/hooks/ against the package's HEAD."""
    missing, stale = [], []
    for name, src in HOOK_FILES.items():
        target = os.path.join(tree, ".claude", "hooks", name)
        if not os.path.isfile(target):
            missing.append(name)
            continue
        head = _git(pkg, "rev-parse", f"HEAD:{src}")
        mine = _git(tree, "hash-object", target)
        if head and mine and head != mine:
            stale.append(name)
    return missing, stale


def _settings_commands(tree: str) -> list:
    """[(event, matcher, command)] across the tree's settings.json and settings.local.json."""
    out = []
    for fn in ("settings.json", "settings.local.json"):
        try:
            data = json.load(open(os.path.join(tree, ".claude", fn), encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as e:
            logger.warning("auto-clear: unreadable %s/.claude/%s: %s", tree, fn, e)
            continue
        for event, entries in (data.get("hooks") or {}).items():
            for entry in entries or []:
                for h in entry.get("hooks") or []:
                    out.append((event, entry.get("matcher") or "", h.get("command") or ""))
    return out


def hooks_wired(tree: str) -> tuple:
    """(reload_wired, arm_wired, keep_going_thresholds) — the package's hook OR a project's own."""
    cmds = _settings_commands(tree)
    reload_ = any(ev == "SessionStart" and "clear" in m and "reinject" in c for ev, m, c in cmds)
    arm = any(ev == "PostToolUse" and "handoff-arm" in c for ev, m, c in cmds)
    kg = sorted({int(t) for ev, m, c in cmds if "keep-going" in c
                 for t in re.findall(r"--threshold\s+(\d+)", c)})
    return reload_, arm, kg


def watcher_units(home: str, tree: str) -> list:
    """[(unit name, ExecStart)] of user units that run THIS tree's watcher, whatever their name."""
    want = os.path.join(tree, WATCHER)
    out = []
    for f in sorted(glob.glob(os.path.join(home, ".config", "systemd", "user", "*.service"))):
        try:
            text = open(f, encoding="utf-8").read()
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("ExecStart=") and want in line:
                out.append((os.path.basename(f), line[len("ExecStart="):]))
    return out


def unit_active(unit: str, env: dict) -> Optional[bool]:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True,
                           timeout=10, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("auto-clear: systemctl is-active %s: %s", unit, type(e).__name__)
        return None
    return r.stdout.strip() == "active"


def check(name: str, entry: dict, tree: str, registry: Optional[dict], home: str, env: dict):
    """One Check for one project. Imported lazily by checks.check_project."""
    from set_doctor.checks import Check, sh

    def rec(status, detail, fix=None):
        return Check("project", "auto-clear", status, detail, fix)

    if entry.get("auto_clear") is False:
        return rec("skip", "opted out (auto_clear: false in the registry entry)")
    init_fix = sh(f"set-project init --project {name}")
    pkg = package_path(registry)
    if not pkg:
        return rec("warn", f"the {PACKAGE} checkout is not in the registry, so auto-clear cannot be installed "
                           "or checked", sh(f"set-project add {PACKAGE} <path-to-checkout>"))
    problems, fix = [], None
    missing, stale = stale_templates(pkg, tree)
    if missing:
        problems.append(f"templates missing: {', '.join(missing)}")
    if stale:
        problems.append(f"templates not current: {', '.join(stale)}")
    reload_, arm, kg = hooks_wired(tree)
    if not reload_:
        problems.append("no SessionStart clear reload hook (neither the package's nor the project's own)")
    if not arm:
        problems.append("no PostToolUse handoff-arm hook")
    if problems:
        fix = init_fix
    units = watcher_units(home, tree)
    default = package_default_threshold(pkg)
    native = native_trigger(home)

    def over(v: int) -> Optional[str]:
        """Why a pinned threshold is wrong, or None. An override above the package default
        drifts from the owner's setting; one above the native trigger can never fire."""
        why = []
        if default and v > default:
            why.append(f"above the package default {default}")
        if native and v > native:
            why.append(f"above the native compaction trigger ~{native}")
        return " and ".join(why) or None
    if not units:
        problems.append("no watcher unit runs this tree's watch-auto-clear.sh")
        fix = fix or init_fix
    for unit, cmd in units:
        active = unit_active(unit, env)
        if active is False:
            problems.append(f"{unit} is not active")
            fix = fix or sh(f"systemctl --user start {unit}")
        for flag in THRESHOLD_FLAGS:
            for v in re.findall(rf"{flag}\s+(\d+)", cmd):
                why = over(int(v))
                if why:
                    problems.append(f"{unit} passes {flag} {v}, {why}")
                    fix = fix or (f"remove `{flag} {v}` from ~/.config/systemd/user/{unit}, then "
                                  f"`systemctl --user daemon-reload && systemctl --user restart {unit}`")
    for v in kg:
        why = over(v)
        if why:
            problems.append(f"a keep-going hook in .claude/settings*.json passes --threshold {v}, {why}")
            fix = fix or f"set keep-going's --threshold to {default} in {tree}/.claude/settings.json"
    if problems:
        logger.info("auto-clear %s: %d problem(s): %s", name, len(problems), "; ".join(problems))
        return rec("warn", "; ".join(problems), fix)
    names = ", ".join(u for u, _ in units)
    return rec("ok", f"templates current, reload + arm wired, {names} active")
