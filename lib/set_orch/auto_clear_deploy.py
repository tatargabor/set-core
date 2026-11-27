"""`set-project init`'s auto-clear step (auto-clear-default-install, groups 1.2, 2, 4, 5).

Order (design D4): templates, then hooks, then the watcher unit — the unit starts only when a
reload hook is wired, because a watcher clearing sessions that cannot reload is the failure
the ordering prevents.

- Templates (D1): the handoff package's own installer runs in a scratch tree against an
  export of the checkout's committed HEAD, so the package stays the one owner of WHICH files
  exist and uncommitted edits never reach a consumer. Each file is copied into the project
  only when the target is absent or holds a version the package has shipped (blob hash, read
  from the checkout's git history). Anything else is kept and reported.
- Hooks (D2): `set-deploy-hooks --auto-clear`, which also writes the reload wiring stamp.
- Unit (D3): created from `templates/systemd/auto-clear.service` only where no unit runs this
  tree's watcher; an existing one is never rewritten, and its overriding flags are named.

Never fails init: a missing package checkout, node, or `systemctl --user` is a line, exit 0.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from set_doctor import auto_clear as ac

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
UNIT_TEMPLATE = ROOT / "templates" / "systemd" / "auto-clear.service"
OVERRIDING = ("--threshold", "--compact-threshold", "--background-work-blocks", "--compact-on-background")


def _run(cmd, cwd=None, env=None, timeout=120):
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("auto-clear deploy: %s failed: %s", cmd[0], type(e).__name__)
        return 127, ""
    return r.returncode, (r.stdout + r.stderr).rstrip()


def _git(pkg, *args):
    rc, out = _run(["git", "-C", str(pkg), *args])
    return out if rc == 0 else ""


def skip_reason(entry: dict) -> Optional[str]:
    if entry.get("archived"):
        return "archived"
    if entry.get("deploy") is False:
        return "data repository (deploy: false)"
    if entry.get("auto_clear") is False:
        return "opted out (auto_clear: false)"
    return None


# ── templates (D1) ───────────────────────────────────────────────────────────


def _export_head(pkg: Path, dest: Path) -> tuple:
    """Export the checkout's committed HEAD into dest (`git archive HEAD | tar -x`).

    Run as two subprocess calls rather than a shell pipeline: the archive is binary, so it
    must not travel through a text-mode pipe. Returns (rc, tail of stderr).
    """
    try:
        arch = subprocess.run(["git", "-C", str(pkg), "archive", "HEAD"], capture_output=True, timeout=120)
        if arch.returncode != 0:
            return arch.returncode, (arch.stderr or b"").decode("utf-8", "replace").strip()
        tar = subprocess.run(["tar", "-x", "-C", str(dest)], input=arch.stdout, capture_output=True, timeout=120)
        if tar.returncode != 0:
            return tar.returncode, (tar.stderr or b"").decode("utf-8", "replace").strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("auto-clear deploy: exporting %s's HEAD failed: %s", pkg, type(e).__name__)
        return 127, type(e).__name__
    return 0, ""


def produced_files(pkg: Path, env: dict) -> tuple:
    """Run the package installer from the checkout's COMMITTED HEAD, in a scratch tree.

    The installer must not see the working tree: uncommitted edits under templates/ would
    land in consumer projects while shipped_blobs() judges "shipped" from HEAD — the two
    must read the same thing, and that thing is HEAD.

    Returns (scratch dir, [relative paths], HEAD short sha), or (None, reason, "") when the
    step cannot run — a failure here is a line in the report, never a failed init. On the
    success path the scratch is handed to the caller, which removes it in its own finally;
    every other path (export failure, installer failure, exception) cleans up both temp
    dirs here.
    """
    if not shutil.which("node", path=env.get("PATH")):
        return None, "node is not on PATH", ""
    sha = _git(pkg, "rev-parse", "--short", "HEAD")
    if not sha:
        return None, f"git could not read the {ac.PACKAGE} checkout's HEAD", ""
    scratch = Path(tempfile.mkdtemp(prefix="set-auto-clear-"))
    export = Path(tempfile.mkdtemp(prefix="set-auto-clear-head-"))
    handed_off = False
    try:
        rc, err = _export_head(pkg, export)
        if rc != 0:
            return None, f"exporting the {ac.PACKAGE} checkout's HEAD failed ({err[-200:]})", ""
        rc, out = _run(["node", str(export / "bin" / "cli.mjs"), "init", "--auto-clear"], cwd=scratch, env=env)
        if rc != 0:
            return None, f"the package installer failed (rc={rc}): {out[-200:]}", ""
        files = sorted(str(p.relative_to(scratch)) for p in scratch.rglob("*") if p.is_file())
        handed_off = True
        return scratch, files, sha
    except Exception as e:  # noqa: BLE001 — init must never fail
        logger.warning("auto-clear deploy: producing templates from %s failed: %s: %s", pkg, type(e).__name__, e)
        return None, f"{type(e).__name__}: {e}", ""
    finally:
        shutil.rmtree(export, ignore_errors=True)
        if not handed_off:
            shutil.rmtree(scratch, ignore_errors=True)


def shipped_blobs(pkg: Path, blob: str) -> set:
    """Every blob the package has shipped at the path that holds `blob` at HEAD.

    The produced file is located in the package by content (its blob equals a HEAD blob), so
    no source map is kept here; the history walk follows renames. A file whose source is not
    found has only its own blob as known — the conservative side: a stale copy is kept.

    EVERY HEAD path holding the blob is walked, not the first one. The package checkout is
    itself a consumer: once its own `.claude/hooks/<f>` copy is committed at the current
    version, that path sorts before `templates/<f>` and holds the same blob — and its history
    has only the versions deployed INTO the package, not every version the package shipped.
    Measured 2026-11-24 on a fleet re-roll: after the package tree's own commit, two trees
    holding an older shipped version were reported "locally modified" and kept.

    `-m` makes the walk see MERGE commits. Without it `git log` prints no diff, and so no file
    name, for a merge, and a blob that a merge's resolution created is never read. Measured
    the same day: the package's watcher version that 38 trees held was born in a merge, and
    the next roll would have kept it as "locally modified" in every one of them.
    """
    known = {blob}
    srcs = []
    for line in _git(pkg, "ls-tree", "-r", "HEAD").splitlines():
        meta, _, path = line.partition("\t")
        if meta.split()[-1] == blob:
            srcs.append(path)
    if not srcs:
        logger.debug("shipped_blobs: blob %s not found at HEAD of %s", blob, pkg)
        return known
    for src in srcs:
        log = _git(pkg, "log", "--follow", "-m", "--format=C %H", "--name-only", "--", src)
        commit = None
        for line in log.splitlines():
            if line.startswith("C "):
                commit = line[2:]
            elif line.strip() and commit:
                b = _git(pkg, "rev-parse", f"{commit}:{line.strip()}")
                if b:
                    known.add(b)
    return known


def install_templates(pkg: Path, tree: Path, env: dict, dry_run: bool,
                      package_route: bool = False) -> list:
    """Copy the package's produced files into the tree (D1).

    On the package route (B-253) the watcher runs the package's own templates and a plugin
    wires the hooks, so a `.claude/hooks/` copy is written only where the tree's settings call
    it; every other hook copy is left out and named once.
    """
    lines = []
    called = {n for n in ac.HOOK_FILES for _, _, c in ac._settings_commands(str(tree)) if n in c}
    left_out = []
    scratch, files, sha = produced_files(pkg, env)
    if scratch is None:
        return [f"  auto-clear templates: skipped — {files}"]
    try:
        for rel in files:
            new = scratch / rel
            target = tree / rel
            if (package_route and rel.startswith(".claude/hooks/")
                    and os.path.basename(rel) not in called):
                left_out.append(os.path.basename(rel))
                continue
            new_blob = _git(pkg, "hash-object", str(new))
            if target.is_file():
                cur = _git(pkg, "hash-object", str(target))
                if cur == new_blob:
                    continue
                if cur not in shipped_blobs(pkg, new_blob):
                    lines.append(f"  auto-clear templates: kept {rel} (locally modified)")
                    continue
                verb = "would upgrade" if dry_run else "upgraded"
            else:
                verb = "would write" if dry_run else "wrote"
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(new, target)
            lines.append(f"  auto-clear templates: {verb} {rel}")
            logger.info("auto-clear template %s %s in %s", verb, rel, tree)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if left_out:
        logger.info("auto-clear templates: package route in %s, hook copies left out: %s", tree, left_out)
        lines.append(f"  auto-clear templates: package route — the watcher runs the package's own "
                     f"files, so {', '.join(sorted(left_out))} not copied")
    if lines and not all("package route" in l for l in lines):
        # Every line appended above means a file was written/upgraded (or planned to be)
        # or kept as locally modified — name where those templates came from, first.
        header = f"  auto-clear templates: from {ac.PACKAGE} {sha}"
        if _git(pkg, "status", "--porcelain", "--", "templates", "bin", "skills"):
            header += " (uncommitted changes in the checkout are not shipped)"
            logger.warning("auto-clear templates: %s's checkout has uncommitted changes "
                           "under templates/bin/skills; HEAD %s is what ships", ac.PACKAGE, sha)
        lines.insert(0, header)
        logger.info("auto-clear templates installed from %s HEAD %s into %s", ac.PACKAGE, sha, tree)
    return lines


# ── hooks (D2) ───────────────────────────────────────────────────────────────


def merge_hooks(tree: Path, dry_run: bool) -> list:
    cmd = ["bash", str(ROOT / "bin" / "set-deploy-hooks"), "--auto-clear", "--quiet"]
    rc, out = _run(cmd + (["--dry-run"] if dry_run else []) + [str(tree)])
    if rc != 0:
        return [f"  auto-clear hooks: FAILED — {out[-200:]}"]
    return [l for l in out.splitlines() if l.strip()]


# ── unit (D3) ────────────────────────────────────────────────────────────────


def overriding_flags(exec_start: str) -> list:
    return [f"{f} {v}" for f in OVERRIDING for v in re.findall(rf"{f}[ =](\S+)", exec_start)]


def install_unit(name: str, tree: Path, home: Path, env: dict, dry_run: bool) -> list:
    unit_dir = home / ".config" / "systemd" / "user"
    unit_name = f"{name}-auto-clear.service"
    existing = ac.watcher_units(str(home), str(tree)) + ac.package_units(str(home), str(tree))
    if (unit_dir / unit_name).is_file() and not any(u == unit_name for u, _ in existing):
        existing.append((unit_name, ""))
    if existing:
        lines = []
        for unit, cmd in existing:
            flags = overriding_flags(cmd)
            if flags:
                lines.append(f"  auto-clear unit: {unit} exists, left as is; it pins {', '.join(flags)} — "
                             f"remove them from {unit_dir / unit} and restart it to get the package defaults")
            else:
                lines.append(f"  auto-clear unit: {unit} exists, left as is")
        return lines
    reload_wired, _, _ = ac.hooks_wired(str(tree))
    if not reload_wired and not dry_run:
        return ["  auto-clear unit: not created — no reload hook is wired, so a cleared session would reload nothing"]
    rc, _ = _run(["systemctl", "--user", "show-environment"], env=env, timeout=10)
    if rc != 0:
        return ["  auto-clear unit: skipped — systemctl --user is not available here"]
    if dry_run:
        return [f"  auto-clear unit: would create {unit_dir / unit_name} and start it"]
    node = shutil.which("node", path=env.get("PATH"))
    text = (UNIT_TEMPLATE.read_text()
            .replace("@TREE@", str(tree)).replace("@NAME@", name)
            .replace("@NODE_DIR@", os.path.dirname(node) if node else "/usr/bin"))
    unit_dir.mkdir(parents=True, exist_ok=True)
    (unit_dir / unit_name).write_text(text)
    logger.info("auto-clear unit written: %s", unit_dir / unit_name)
    _run(["systemctl", "--user", "daemon-reload"], env=env, timeout=30)
    rc, out = _run(["systemctl", "--user", "enable", "--now", unit_name], env=env, timeout=30)
    if rc != 0:
        return [f"  auto-clear unit: created {unit_name}, but it did not start: {out[-200:]}"]
    return [f"  ✔ auto-clear unit: created and started {unit_name}"]


# ── the step ─────────────────────────────────────────────────────────────────


def deploy(name: str, tree: Path, registry: dict, home: Path, env: dict, dry_run: bool) -> list:
    entry = registry.get(name) or {}
    why = skip_reason(entry)
    if why:
        return [f"  auto-clear: skipped — {why}"]
    pkg = ac.package_path(registry)
    if not pkg:
        return [f"  auto-clear: skipped — the {ac.PACKAGE} checkout is not in the registry "
                f"(set-project add {ac.PACKAGE} <path>)"]
    package_route = bool(ac.package_units(str(home), str(tree)))
    lines = install_templates(Path(pkg), tree, env, dry_run, package_route)
    reload_, arm, _ = ac.hooks_wired(str(tree), str(home))
    if package_route and reload_ and arm:
        # B-253: a plugin already wires reload + arm; settings hooks would run them twice.
        lines.append("  auto-clear hooks: package route — reload and arm come from an enabled plugin, left as is")
    else:
        lines += merge_hooks(tree, dry_run)
    lines += install_unit(name, tree, home, env, dry_run)
    return lines


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="set-project init (auto-clear step)")
    p.add_argument("--project-dir", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    from set_kb.lifecycle import registry_path
    try:
        registry = json.loads(Path(registry_path()).read_text()).get("projects") or {}
    except (OSError, ValueError) as e:
        print(f"  auto-clear: skipped — the project registry is unreadable ({type(e).__name__})")
        return 0
    for line in deploy(a.name, Path(a.project_dir).resolve(), registry, Path.home(), dict(os.environ), a.dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
