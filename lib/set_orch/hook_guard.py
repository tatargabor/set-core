"""Keep a command run inside a worktree from rewiring the HOST repository's git hooks.

WHY THIS EXISTS. A git worktree does not have its own hooks. It shares one `.git`
directory, and with it `core.hooksPath` and the hook scripts themselves. So a command run
inside a throwaway worktree can silently re-point the *main* checkout's hooks — and the
usual way that happens is not malice or even a hook installer being called directly. It is
a dependency install:

    pnpm install            (in a worktree)
      └─ package.json "prepare": "husky install" / "lefthook install"
           └─ writes hook dispatchers containing an ABSOLUTE path into the worktree

When the worktree is later removed — which orchestration does as a matter of course — the
host repository's hooks point at a path that no longer exists. Everything they were
enforcing stops running.

**Three properties make this the worst kind of breakage**, and they are why this module
exists rather than a comment:

- **It is invisible to git.** Hook managers ship a `.gitignore` containing `*` inside their
  own directory, so a polluted hook layer never shows up in `git status`. A clean working
  tree says nothing about it.
- **It fails silent and open.** A hook that cannot run does not error; it simply does not
  run. Every gate hanging off it reports nothing at all, which reads exactly like a gate
  that passed.
- **It outlives the cause by weeks.** The worktree is gone, so nothing on disk points back
  at what did it. It was measured on a real repository ten days after the fact, and only
  because someone went looking for an unrelated reason.

Two defences, because neither is sufficient alone:

`hook_safe_env()` is PREVENTION: the documented opt-out switches for the common installers,
so the `prepare` script does nothing instead of doing damage. It names specific tools, which
is a compromise — but the alternative, `--ignore-scripts`, also disables the legitimate
postinstall work a build needs.

`capture_hook_wiring()` / `hook_wiring_changes()` is DETECTION, and it is the part that does
not depend on knowing the tool. It compares the host's hook wiring before and after, so an
installer nobody has heard of is still caught. Prevention that only covers what we thought
of is exactly the shape this module is here to stop trusting.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

#: Documented opt-outs for hook installers commonly wired into a `prepare` script. The
#: value is what the tool itself treats as "do nothing"; this is not a set-core invention.
#: Extend it when another installer turns up — and keep the detection below as the reason
#: it is safe for this list to be incomplete.
HOOK_INSTALLER_OPT_OUTS: Dict[str, str] = {
    "HUSKY": "0",
    "LEFTHOOK": "0",
}


def hook_safe_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Environment additions that stop a `prepare` script from installing git hooks.

    Merge-friendly: returns only the additions, since `run_command` merges with the
    ambient environment itself. An explicit value in `extra` wins, because an operator
    asking for an installer to run knows something this module does not.
    """
    env = dict(HOOK_INSTALLER_OPT_OUTS)
    if extra:
        env.update(extra)
    return env


def _hooks_path(repo_root: str | Path) -> Optional[str]:
    """The repository's configured `core.hooksPath`, or None when it is unset."""
    try:
        proc = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("hook_guard: cannot read core.hooksPath (%s)", type(exc).__name__)
        return None
    value = proc.stdout.strip()
    return value or None


def _git_common_dir(repo_root: str | Path) -> Optional[Path]:
    """The shared `.git` directory — the same one every worktree writes through."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (Path(repo_root) / path).resolve()


def capture_hook_wiring(repo_root: str | Path) -> Dict[str, str]:
    """A fingerprint of everything that decides which hooks this repository runs.

    Covers both halves, because either alone can be rewritten: the `core.hooksPath`
    setting, and the content of every executable in whichever directory it points at
    (default `.git/hooks`). Content, not mtime — a reinstall that produces an identical
    file is not damage, and an identical timestamp with different bytes is.

    Returns an empty mapping when git cannot be consulted. That is deliberate: no
    information must not read as "nothing changed", so `hook_wiring_changes` treats an
    empty *before* as "cannot say" rather than as a clean baseline.
    """
    wiring: Dict[str, str] = {}
    hooks_path = _hooks_path(repo_root)
    wiring["core.hooksPath"] = hooks_path or ""

    if hooks_path:
        hooks_dir = Path(hooks_path)
        if not hooks_dir.is_absolute():
            hooks_dir = Path(repo_root) / hooks_dir
    else:
        common = _git_common_dir(repo_root)
        if common is None:
            return {}
        hooks_dir = common / "hooks"

    if not hooks_dir.is_dir():
        wiring["<hooks-dir>"] = "absent"
        return wiring

    for entry in sorted(hooks_dir.rglob("*")):
        if not entry.is_file():
            continue
        # `.sample` files ship with git and are never wired to anything.
        if entry.name.endswith(".sample"):
            continue
        try:
            digest = hashlib.sha256(entry.read_bytes()).hexdigest()[:16]
        except OSError:
            digest = "<unreadable>"
        wiring[str(entry.relative_to(hooks_dir))] = digest
    return wiring


def hook_wiring_changes(
    before: Dict[str, str], after: Dict[str, str],
) -> List[str]:
    """What changed between two fingerprints, in words an operator can act on.

    An empty *before* returns no findings — see `capture_hook_wiring`: absence of a
    baseline is absence of information, and reporting "unchanged" from it would be the
    false-absence shape this whole area keeps producing.
    """
    if not before:
        return []
    findings: List[str] = []

    if before.get("core.hooksPath", "") != after.get("core.hooksPath", ""):
        findings.append(
            "core.hooksPath changed from "
            f"{before.get('core.hooksPath') or '<unset>'} to "
            f"{after.get('core.hooksPath') or '<unset>'}"
        )

    for name in sorted(set(before) | set(after)):
        if name == "core.hooksPath":
            continue
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        if old is None:
            findings.append(f"hook added: {name}")
        elif new is None:
            findings.append(f"hook removed: {name}")
        else:
            findings.append(f"hook rewritten: {name}")
    return findings


def guard_host_hooks(repo_root: str | Path, before: Dict[str, str], *, context: str) -> List[str]:
    """Compare against a baseline and report loudly. Returns the findings.

    Deliberately does NOT repair. Restoring would mean writing into a repository this
    process was not asked to modify — the exact class of action the surrounding safety
    work exists to prevent — and a wrong restore is indistinguishable from the damage.
    Reporting is enough, because the failure's whole problem was that it was silent.
    """
    findings = hook_wiring_changes(before, capture_hook_wiring(repo_root))
    if findings:
        logger.error(
            "HOST GIT HOOKS CHANGED by %s in %s — a command run in a worktree rewrote the "
            "shared hook wiring, which git does not show and which stops enforcing "
            "SILENTLY once the worktree is gone. Changes: %s",
            context, repo_root, "; ".join(findings),
        )
    return findings
