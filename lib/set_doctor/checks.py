"""The checks. Each returns Check records; none of them writes anything except
the MCP probe's throwaway repository and a `git fetch` of remote-tracking refs.

Status vocabulary (design D4): ok, warn, fail, skip. A skip is never a pass.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

STATUSES = ("ok", "warn", "fail", "skip")
RANK = {"ok": 0, "skip": 1, "warn": 2, "fail": 3}


@dataclass
class Check:
    section: str
    name: str
    status: str
    detail: str
    fix: Optional[str] = None
    project: Optional[str] = None
    module: Optional[str] = None  # the module doctor that produced it (doctor-module-contract)
    path: Optional[str] = None  # join key from a doctor/1 record; not part of set-doctor/1 output

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None and k != "path"}


@dataclass
class Context:
    root: str  # this set-core checkout
    home: str
    offline: bool = False
    deep: bool = False
    live: bool = False
    project_glob: Optional[str] = None
    env: dict = field(default_factory=lambda: dict(os.environ))

    @property
    def link_dir(self) -> str:
        return os.path.join(self.home, ".local", "bin")  # install.sh: INSTALL_DIR

    @property
    def mcp_dir(self) -> str:
        return os.path.join(self.root, "mcp-server")

    def which(self, name: str) -> Optional[str]:
        return shutil.which(name, path=self.env.get("PATH", ""))

    @property
    def child(self) -> bool:
        """Run by a module doctor that set-doctor started: run no module doctors (no recursion)."""
        from set_doctor.modules import CHILD_ENV

        return self.env.get(CHILD_ENV, "") == "1"


def run(cmd, cwd=None, timeout=60, env=None) -> tuple:
    """(rc, stdout, stderr); rc is None when the command could not run or timed out."""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        logger.warning("timed out after %ss: %s", timeout, cmd[:3])
        return None, "", f"timed out after {timeout} s"
    except OSError as e:
        logger.warning("could not run %s: %s", cmd[:1], e)
        return None, "", str(e)


def sh(cmd: str) -> str:
    """A fix command as one copyable line."""
    return cmd


# ── install ──────────────────────────────────────────────────────────────────


def installer_commands(root: str) -> list:
    """The command list install.sh links, read from install.sh itself (design D1)."""
    text = open(os.path.join(root, "install.sh"), encoding="utf-8").read()
    m = re.search(r"local scripts=\(([^)]*)\)", text)
    if not m:
        raise ValueError("install.sh: the `local scripts=(...)` list was not found")
    return m.group(1).split()


def check_install(ctx: Context) -> list:
    out = []
    fix_install = sh(f"cd {ctx.root} && ./install.sh")
    try:
        names = installer_commands(ctx.root)
    except (OSError, ValueError) as e:
        return [Check("install", "commands", "fail", str(e), fix_install)]
    bin_dir = os.path.realpath(os.path.join(ctx.root, "bin"))
    missing, elsewhere = [], []
    for name in names:
        p = os.path.join(ctx.link_dir, name)
        if not os.path.exists(p):  # a dangling link counts as missing
            missing.append(name)
        elif os.path.dirname(os.path.realpath(p)) != bin_dir:
            elsewhere.append(f"{name} → {os.path.realpath(p)}")
    if missing:
        out.append(Check("install", "commands", "fail",
                         f"{len(missing)} of {len(names)} installer command(s) missing from {ctx.link_dir}: "
                         + ", ".join(missing), fix_install))
    elif elsewhere:
        out.append(Check("install", "commands", "warn",
                         f"{len(elsewhere)} command(s) run another checkout's code: " + "; ".join(elsewhere),
                         fix_install))
    else:
        out.append(Check("install", "commands", "ok",
                         f"{len(names)}/{len(names)} installer commands link into {bin_dir}"))

    path_dirs = [os.path.realpath(d) for d in ctx.env.get("PATH", "").split(os.pathsep) if d]
    if os.path.realpath(ctx.link_dir) in path_dirs:
        out.append(Check("install", "PATH", "ok", f"{ctx.link_dir} is on PATH"))
    else:
        out.append(Check("install", "PATH", "fail", f"{ctx.link_dir} is not on PATH",
                         sh(f"echo 'export PATH=\"{ctx.link_dir}:$PATH\"' >> ~/.bashrc && . ~/.bashrc")))

    venv = os.path.join(ctx.mcp_dir, ".venv")
    if os.path.isdir(venv):
        out.append(Check("install", "mcp deps", "ok", f"{venv} exists"))
    else:
        out.append(Check("install", "mcp deps", "fail", f"the MCP server's environment is missing: {venv}",
                         sh(f"cd {ctx.mcp_dir} && uv sync")))
    return out


# ── checkout ─────────────────────────────────────────────────────────────────


def git(ctx_root: str, *args, timeout=30) -> tuple:
    return run(["git", "-C", ctx_root, *args], timeout=timeout)


def head_label(root: str) -> str:
    rc, out, _ = git(root, "rev-parse", "--short", "HEAD")
    return out.strip() if rc == 0 else "?"


def check_checkout(ctx: Context) -> list:
    out = []
    rc, status, err = git(ctx.root, "status", "--porcelain")
    if rc != 0:
        return [Check("checkout", "git", "fail", f"{ctx.root} is not a readable git checkout: {err.strip()}",
                      sh(f"git clone <set-core url> {ctx.root}"))]
    dirty = [ln for ln in status.splitlines() if ln.strip()]
    if dirty:
        out.append(Check("checkout", "clean", "warn", f"{len(dirty)} uncommitted file(s) in {ctx.root}",
                         sh(f"git -C {ctx.root} status   # commit or stash them before pulling")))
    else:
        out.append(Check("checkout", "clean", "ok", "no uncommitted files"))

    rc, up, _ = git(ctx.root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if rc != 0:
        rc_b, branch, _ = git(ctx.root, "rev-parse", "--abbrev-ref", "HEAD")
        out.append(Check("checkout", "upstream", "warn", f"branch {branch.strip() or '?'} has no upstream",
                         sh(f"git -C {ctx.root} branch --set-upstream-to origin/main")))
        return out
    up = up.strip()
    fetched_note = ""
    if ctx.offline:
        fetched_note = " (not fetched: --offline)"
    else:
        remote = up.split("/", 1)[0]
        rc_f, _, err_f = git(ctx.root, "fetch", "--quiet", remote, timeout=20)
        if rc_f != 0:
            fetched_note = f" (fetch failed: {err_f.strip()[:120] or 'timeout'} — compared with the refs on disk)"
    rc, counts, _ = git(ctx.root, "rev-list", "--left-right", "--count", f"HEAD...{up}")
    if rc != 0:
        out.append(Check("checkout", "upstream", "warn", f"could not compare with {up}{fetched_note}",
                         sh(f"git -C {ctx.root} fetch")))
        return out
    ahead, behind = (int(x) for x in counts.split())
    if behind and ahead:
        out.append(Check("checkout", "upstream", "warn",
                         f"diverged from {up}: {ahead} ahead, {behind} behind{fetched_note}",
                         sh(f"git -C {ctx.root} pull --no-rebase")))
    elif behind:
        out.append(Check("checkout", "upstream", "warn", f"{behind} commit(s) behind {up}{fetched_note}",
                         sh(f"git -C {ctx.root} pull")))
    elif ahead:
        out.append(Check("checkout", "upstream", "warn", f"{ahead} local commit(s) not on {up}{fetched_note}",
                         sh(f"git -C {ctx.root} push")))
    else:
        out.append(Check("checkout", "upstream", "ok", f"even with {up}{fetched_note}"))
    return out


# ── tools ────────────────────────────────────────────────────────────────────

TOOL_HINTS = {
    "python3": "sudo apt install python3   # 3.10 or newer",
    "uv": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    "node": "install Node.js 20+ (nvm install 22, or the distribution's package)",
    "jq": "sudo apt install jq",
    "git": "sudo apt install git",
    "claude": "npm install -g @anthropic-ai/claude-code",
    "openspec": "npm install -g @fission-ai/openspec@latest",
}


# Floors with the reason, so a failing line says who needs the newer version.
MIN_VERSION = {"python3": (3, 10), "node": (18,)}
MIN_WHY = {"python3": "set-core", "node": "Claude Code"}


def version_tuple(text: str) -> tuple:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else ()


def openspec_floor(root: str) -> tuple:
    """The newest `generatedBy` among the checkout's generated OpenSpec skills."""
    floor: tuple = ()
    sdir = os.path.join(root, ".claude", "skills")
    for d in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []:
        if not d.startswith("openspec-"):
            continue
        try:
            text = open(os.path.join(sdir, d, "SKILL.md"), encoding="utf-8").read()
        except OSError:
            continue
        m = re.search(r'generatedBy:\s*"?([\d.]+)', text)
        if m:
            floor = max(floor, version_tuple(m.group(1)))
    return floor


def check_tools(ctx: Context) -> list:
    out = []
    for name in ("python3", "uv", "node", "jq", "git", "claude", "openspec"):
        path = ctx.which(name)
        if not path:
            out.append(Check("tools", name, "fail", f"{name} is not on PATH", TOOL_HINTS[name]))
            continue
        rc, so, se = run([path, "--version"], timeout=20)
        first = ((so or se).strip().splitlines() or ["?"])[0]
        v = version_tuple(first)
        floor = MIN_VERSION.get(name)
        if floor and v and v < floor:
            want = ".".join(map(str, floor))
            out.append(Check("tools", name, "fail", f"{first} — {MIN_WHY[name]} needs {want} or newer",
                             TOOL_HINTS[name]))
            continue
        if name == "openspec":
            floor = openspec_floor(ctx.root)
            if floor and v and v < floor:
                want = ".".join(map(str, floor))
                out.append(Check("tools", name, "warn",
                                 f"{first} is older than {want}, which the checkout's OpenSpec skills were generated with",
                                 TOOL_HINTS[name]))
                continue
        out.append(Check("tools", name, "ok" if rc == 0 else "warn", f"{first} ({path})",
                         None if rc == 0 else f"{path} --version"))
    return out


# ── MCP ──────────────────────────────────────────────────────────────────────


def check_mcp_probe(ctx: Context) -> list:
    from set_doctor.mcp_probe import probe

    if not ctx.which("uv"):
        return [Check("mcp", "server", "skip", "uv is not on PATH, so the server cannot start")]
    if not os.path.isfile(os.path.join(ctx.mcp_dir, "set_mcp_server.py")):
        return [Check("mcp", "server", "fail", f"no set_mcp_server.py in {ctx.mcp_dir}", None)]
    ok, detail = probe(ctx.mcp_dir)
    return [Check("mcp", "server", "ok" if ok else "fail", detail,
                  None if ok else sh(f"cd {ctx.mcp_dir} && uv sync && uv run python set_mcp_server.py"))]


def claude_config_path(ctx: Context) -> str:
    d = ctx.env.get("CLAUDE_CONFIG_DIR", "").strip()
    return os.path.join(os.path.expanduser(d), ".claude.json") if d else os.path.join(ctx.home, ".claude.json")


def load_claude_projects(ctx: Context) -> Optional[dict]:
    try:
        with open(claude_config_path(ctx), encoding="utf-8") as f:
            return json.load(f).get("projects") or {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning("Claude config unreadable: %s", e)
        return None


def mcp_registration(ctx: Context, claude_projects: Optional[dict], path: str) -> Check:
    if claude_projects is None:
        return Check("project", "mcp", "skip", f"the Claude config is unreadable: {claude_config_path(ctx)}")
    entry = None
    for key in (path, os.path.realpath(path)):
        entry = ((claude_projects.get(key) or {}).get("mcpServers") or {}).get("set-core")
        if entry:
            break
    fix = sh(f"cd {path} && claude mcp remove set-core; set-project init")
    if not entry:
        return Check("project", "mcp", "warn", "the set-core MCP server is not registered (no kb_search for agents)",
                     sh(f"cd {path} && set-project init"))
    args = list(entry.get("args") or [])
    server_dir = args[args.index("--directory") + 1] if "--directory" in args[:-1] else None
    proj_dir = next((a.split("=", 1)[1] for a in args if a.startswith("CLAUDE_PROJECT_DIR=")), None)
    proj_dir = proj_dir or (entry.get("env") or {}).get("CLAUDE_PROJECT_DIR")
    problems = []
    if not server_dir or os.path.realpath(server_dir) != os.path.realpath(ctx.mcp_dir):
        problems.append(f"server in {server_dir or '?'}, not this checkout's {ctx.mcp_dir}")
    if not proj_dir or os.path.realpath(proj_dir) != os.path.realpath(path):
        problems.append(f"CLAUDE_PROJECT_DIR={proj_dir or '(unset)'}, not {path}")
    if problems:
        return Check("project", "mcp", "warn", "registered, but " + "; ".join(problems), fix)
    return Check("project", "mcp", "ok", "registered for this project, this checkout's server")


# ── projects ─────────────────────────────────────────────────────────────────


def load_registry(ctx: Context) -> tuple:
    """(path, {name: entry}) or (path, None) when unreadable."""
    from set_kb.lifecycle import registry_path

    p = registry_path(ctx.env)
    try:
        with open(p, encoding="utf-8") as f:
            return p, (json.load(f).get("projects") or {})
    except FileNotFoundError:
        return p, {}
    except (OSError, ValueError) as e:
        logger.warning("registry unreadable: %s: %s", p, e)
        return p, None


def deployed_version(ctx: Context, path: str) -> Check:
    vfile = os.path.join(path, ".claude", ".set-version")
    fix = sh(f"cd {path} && set-project init")
    try:
        v = open(vfile, encoding="utf-8").read().strip()
    except OSError:
        return Check("project", "deploy", "warn", "set-core was never deployed here (no .claude/.set-version)", fix)
    rc, sha, _ = git(ctx.root, "rev-parse", "--verify", "-q", f"{v}^{{commit}}")
    if rc != 0:
        return Check("project", "deploy", "warn", f"deployed version {v} is unknown to this checkout", fix)
    rc, n, _ = git(ctx.root, "rev-list", "--count", f"{sha.strip()}..HEAD")
    behind = int(n.strip()) if rc == 0 and n.strip().isdigit() else None
    if behind == 0:
        return Check("project", "deploy", "ok", f"current ({v})")
    if behind is None:
        return Check("project", "deploy", "warn", f"could not count commits since {v}", fix)
    return Check("project", "deploy", "warn", f"{behind} commit(s) behind this checkout (deployed {v})", fix)


def deep_dry_run(ctx: Context, path: str) -> Check:
    env = {**ctx.env, "SET_MANAGER_URL": "http://127.0.0.1:9"}  # a dry run sends nothing, belt and braces
    rc, so, se = run([os.path.join(ctx.root, "bin", "set-project"), "init", "--dry-run"], cwd=path,
                     timeout=180, env=env)
    if rc != 0:
        return Check("project", "dry-run", "fail", f"set-project init --dry-run failed: {(se or so).strip()[-300:]}",
                     sh(f"cd {path} && set-project init --dry-run"))
    plan = [ln.strip() for ln in so.splitlines()
            if re.match(r"\s*Would (update|deploy [1-9]|scaffold)", ln)]
    if plan:
        return Check("project", "dry-run", "warn", "; ".join(plan), sh(f"cd {path} && set-project init"))
    return Check("project", "dry-run", "ok", "init would change nothing")


def kb_doctor(ctx: Context, path: str, command: Optional[list] = None) -> Check:
    """The `set-kb.doctor/1` adapter: one project's `set-kb doctor --json`, folded into one record.
    A `set-kb` declaration's command replaces the built-in one (one run, never two)."""
    cmd = command or [os.path.join(ctx.root, "bin", "set-kb"), "doctor", "--json"]
    from set_doctor.modules import child_env

    rc, so, se = run(cmd, cwd=path, timeout=120, env=child_env(ctx.env))
    fix = sh(f"cd {path} && set-kb doctor")
    mk = lambda st, d, f=None: Check("project", "kb", st, d, f, module="set-kb")  # noqa: E731
    try:
        d = json.loads(so)
    except ValueError:
        return mk("fail", f"set-kb doctor gave no report: {(se or so).strip()[-300:]}", fix)
    bad = [c for c in d.get("checks", []) if c.get("status") == "blocked"]
    warn = [c for c in d.get("checks", []) if c.get("status") == "warn"]
    if bad:
        return mk("fail", "; ".join(f"{c['name']}: {c['detail']}" for c in bad), fix)
    if warn:
        # "not built yet" is the zero-config default, not a defect: the first search builds it.
        real = [c for c in warn if not (c["name"] == "index" and "not built yet" in c["detail"])]
        if real:
            return mk("warn", "; ".join(f"{c['name']}: {c['detail']}" for c in real), fix)
    idx = next((c["detail"] for c in d.get("checks", []) if c.get("name") == "index"), "")
    return mk("ok", f"search works — index {idx}" if idx else "search works")


GUARD_HOOKS = ("session-start", "watch-guard")


def bus_status(sac_by_path: Optional[dict], path: str, skip_reason: Optional[str] = None) -> list:
    """The `sac.doctor/1` adapter for one project (design D4).

    A LIVE seat without `session-start` or `watch-guard` is a fail: without the first the session
    never gets the background inbox-watch instruction, without the second nothing declines a
    Monitor watch, and each Monitor expiry re-reads the whole context (B-193)."""
    mk = lambda st, d, f=None, n="bus": Check("project", n, st, d, f, module="sac")  # noqa: E731
    if sac_by_path is None:
        return [mk("skip", skip_reason or "sac doctor did not run (see the bus section)")]
    p = sac_by_path.get(os.path.realpath(path))
    fix = sh(f"cd {path} && sac install")
    if not p:
        return [mk("warn", "not on the agent bus (no sac hooks)", fix)]
    hooks = p.get("hooks") or {}
    live = [str(x) for x in (p.get("live") or [])]
    out = []
    missing = [k for k in GUARD_HOOKS if not hooks.get(k)]
    if live and missing:
        logger.warning("live seat(s) %s in %s without hook(s) %s", live, path, missing)
        why = {"session-start": "it never gets the background inbox-watch instruction",
               "watch-guard": "nothing declines a Monitor watch, which re-reads the whole context on every expiry"}
        out.append(mk("fail", f"live session {', '.join(live)} runs without the {' and '.join(missing)} hook"
                              f"{'s' if len(missing) > 1 else ''}: " + "; ".join(why[k] for k in missing), fix))
    elif p.get("verdict") == "off":
        out.append(mk("warn", "not on the agent bus (no sac hooks)", fix))
    elif p.get("verdict") == "ok":
        out.append(mk("ok", "hooks wired" + (f", rooms: {', '.join(p.get('rooms') or [])}" if p.get("rooms") else "")))
    else:
        out.append(mk("warn", "; ".join(p.get("problems") or ["sac doctor: warn"]),
                      sh(f"sac doctor --project {os.path.basename(path)}")))
    dup = {k: v for k, v in hooks.items() if isinstance(v, list) and len(v) > 1}
    if dup:
        out.append(mk("warn", "; ".join(f"{k} runs from {len(v)} carriers ({', '.join(map(str, v))})"
                                       for k, v in sorted(dup.items())) + " — each carrier runs the hook",
                      sh(f"cd {path} && sac uninstall --dry-run   # if the plugin ships the hooks"), n="bus wiring"))
    return out


def check_project(ctx: Context, name: str, entry: dict, claude_projects, sac_by_path,
                  kb_command: Optional[list] = None, module_skip: Optional[str] = None,
                  registry: Optional[dict] = None) -> list:
    path = os.path.expanduser(str(entry.get("path") or ""))
    tag = lambda cs: [setattr(c, "project", name) or c for c in cs]  # noqa: E731
    if not path or not os.path.isdir(path):
        # run_all folds these into one `stale` record before it gets here; a direct caller
        # still gets a record, never silence.
        return tag([Check("project", "path", "warn", f"registered path does not exist: {path or '(none)'}",
                          sh("set-project prune --dry-run"))])
    rc, top, _ = git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        return tag([Check("project", "path", "fail", f"{path} is not a git repository",
                          sh(f"set-project remove {name}"))])
    out = [Check("project", "path", "ok", path)]
    if entry.get("deploy") is False:
        reason = "data repository (deploy: false)"
        out += [Check("project", n, "skip", reason) for n in ("deploy", "mcp", "bus", "auto-clear")]
    else:
        out.append(deployed_version(ctx, path))
        if ctx.deep:
            out.append(deep_dry_run(ctx, path))
        out.append(mcp_registration(ctx, claude_projects, path))
        out += bus_status(sac_by_path, path, module_skip)
        out.append(role_rule(ctx, name, path))
        from set_doctor import auto_clear
        out.append(auto_clear.check(name, entry, path, registry, ctx.home, ctx.env))
    if module_skip:
        out.append(Check("project", "kb", "skip", module_skip, module="set-kb"))
    else:
        out.append(kb_doctor(ctx, path, kb_command))
    return tag(out)


def role_rule(ctx: Context, name: str, path: str) -> Check:
    """The machine-local project role rule (fleet-era-consolidation, `project-role-rule`):
    missing or older than the operator's role file is a warn; no role file is a skip — the
    rule is opt-in through that file."""
    from set_orch.project_roles import rule_state

    status, detail = rule_state(path, ctx.env)
    return Check("project", "role", status, detail,
                 sh(f"set-project roles {name}") if status == "warn" else None)


def stale_entries(registry: dict, names: list) -> tuple:
    """(alive names, {gone name: reason}). Stale = the registered path is gone, or the directory
    is there but is not a git repository (a run directory stripped to its `.set` folder)."""
    stale = {}
    for n in names:
        path = os.path.expanduser(str(registry[n].get("path") or ""))
        if not path or not os.path.isdir(path):
            stale[n] = "gone"
        elif git(path, "rev-parse", "--show-toplevel")[0] != 0:
            stale[n] = "not a git repository"
    return [n for n in names if n not in stale], stale


def archived_entries(registry: dict, names: list, project_glob: Optional[str]) -> tuple:
    """(names to check, archived names left out). An archived entry means "do not develop"
    (fleet-era-consolidation): the full run leaves it out, but asking for it by name with
    `--project` checks it like any other."""
    if project_glob:
        return names, []
    archived = [n for n in names if registry[n].get("archived") is True]
    return [n for n in names if n not in archived], archived


def archived_check(archived: list) -> Check:
    """One summary line for the archived entries the run left out."""
    logger.debug("archived registry entries skipped: %s", archived)
    n = len(archived)
    return Check("project", "archived", "skip",
                 f"{n} archived project{'' if n == 1 else 's'} skipped — "
                 "`set-doctor --project <name>` checks one")


def stale_check(stale: dict) -> Check:
    """One record for every stale registry entry (design D5): bookkeeping, not a broken system,
    so it does not set the exit code — but each name and its reason stay visible."""
    logger.info("stale registry entries: %d", len(stale))
    by_reason: dict = {}
    for n, why in sorted(stale.items()):
        by_reason.setdefault(why, []).append(n)
    detail = f"{len(stale)} registry entr{'y' if len(stale) == 1 else 'ies'} with nothing to check — " + \
        "; ".join(f"{why}: {', '.join(ns)}" for why, ns in sorted(by_reason.items()))
    fix = sh("for p in " + " ".join(sorted(stale)) + "; do set-project remove \"$p\"; done")
    return Check("project", "stale", "warn", detail, fix)


def sac_doctor(ctx: Context, decl=None) -> tuple:
    """(by_realpath | None, Check). The `sac.doctor/1` adapter; a `sac` declaration's command
    replaces the built-in `sac doctor --json` (one run, never two)."""
    from set_doctor.modules import child_env, installed, not_installed

    if decl is not None:
        if not installed(decl, ctx.env):
            return None, not_installed(decl)
        cmd = decl.command
    else:
        sac = ctx.which("sac")
        if not sac:
            return None, Check("bus", "sac", "fail", "the `sac` launcher is not on PATH",
                               sh("node <set-agent-comm checkout>/bin/sac.mjs setup"), module="sac")
        cmd = [sac, "doctor", "--json"]
    rc, so, se = run(cmd, timeout=90, env=child_env(ctx.env))
    try:
        d = json.loads(so)
    except ValueError:
        return None, Check("bus", "sac", "fail", f"sac doctor gave no report: {(se or so).strip()[-300:]}",
                           sh("sac doctor"), module="sac")
    by_path = {os.path.realpath(p["path"]): p for p in d.get("projects", []) if p.get("path")}
    return by_path, Check("bus", "sac", "ok", f"{cmd[0]} — {len(by_path)} project(s) known to the bus", module="sac")


def check_relay(ctx: Context) -> Check:
    if ctx.offline:
        return Check("bus", "relay", "skip", "not checked (--offline)")
    sac = ctx.which("sac")
    if not sac:
        return Check("bus", "relay", "skip", "no sac launcher")
    rc, so, se = run([sac, "relay", "status"], timeout=30, env=ctx.env)
    text = so or ""
    if "CONFIG UNREADABLE" in text:
        return Check("bus", "relay", "fail", "the relay configuration is unreadable", sh("sac relay status"))
    if "(none configured)" in text:
        return Check("bus", "relay", "skip", "no relay configured — the bus reaches this machine only")
    m = re.search(r"^relay:\s+(\S+)", text, re.M)
    url = m.group(1) if m else "?"
    if re.search(r"^reachable", text, re.M):
        return Check("bus", "relay", "ok", f"{url} reachable")
    why = re.search(r"unreachable: (.*)", text)
    return Check("bus", "relay", "fail", f"{url} unreachable: {why.group(1) if why else (se or '?').strip()[:200]}",
                 sh("sac relay status"))


# ── providers, GitHub ────────────────────────────────────────────────────────


def check_provider(ctx: Context) -> list:
    """GLM resolves with a credential (design D6: the value is never printed)."""
    try:
        from set_orch.providers import is_secret_env_key, resolve
        from set_orch.providers.config import load_or_legacy
        from set_orch.providers.errors import ProviderError
    except ImportError as e:
        return [Check("providers", "glm", "skip", f"provider resolver not importable: {e}")]
    try:
        cfg, _notice = load_or_legacy()
        plan = resolve(provider="glm", model=None, config=cfg)
    except ProviderError as e:
        msg = str(e).splitlines()[0][:400]
        try:
            from set_orch.providers.config import config_path
            present = config_path().exists()
        except Exception:  # noqa: BLE001 — only decides the wording below
            present = False
        if present:
            # A file that is there but refused is NOT "not configured": that wording would
            # send the reader to create a config they already have (a false absence).
            return [Check("providers", "glm", "fail", f"the provider configuration is refused: {msg}",
                          sh("set-providers show"))]
        return [Check("providers", "glm", "warn", f"GLM is not configured: {msg}", sh("set-providers path"))]
    except Exception as e:  # noqa: BLE001 — a broken provider file is a finding, not a crash
        return [Check("providers", "glm", "fail", f"provider configuration error: {type(e).__name__}",
                      sh("set-providers show"))]
    has_secret = any(is_secret_env_key(k) and v for k, v in plan.env.items())
    out = []
    if not has_secret:
        out.append(Check("providers", "glm", "warn", "GLM resolves but carries no credential", sh("set-providers path")))
    else:
        out.append(Check("providers", "glm", "ok", f"credential present — {plan.describe()}"))
    if ctx.live and has_secret:
        rc, so, se = run([os.path.join(ctx.root, "bin", "set-glm"), "--check"], timeout=180, env=ctx.env)
        out.append(Check("providers", "glm live", "ok" if rc == 0 else "fail",
                         "a live call answered" if rc == 0 else "the live probe failed (run it to see the CLI's answer)",
                         None if rc == 0 else sh("set-glm --check")))
    return out


def check_github(ctx: Context) -> list:
    gh = ctx.which("gh")
    if not gh:
        return [Check("github", "gh", "fail", "the GitHub CLI is not on PATH", "sudo apt install gh")]
    rc, so, se = run([gh, "auth", "status"], timeout=30, env=ctx.env)
    text = (so or "") + (se or "")
    accounts = re.findall(r"Logged in to (\S+) account (\S+)", text)
    if rc == 0:
        who = ", ".join(f"{a} on {h}" for h, a in accounts) or "logged in"
        return [Check("github", "gh", "ok", who)]
    return [Check("github", "gh", "fail", "gh is not logged in (or a token is invalid)", sh("gh auth login"))]


# ── all of it ────────────────────────────────────────────────────────────────


def run_modules(ctx: Context, decls: dict, registry: dict, workers: int = 8) -> list:
    """Every declared module doctor except the built-in adapters' (sac, set-kb), each run once."""
    from set_doctor import modules as m

    jobs = [d for name, d in sorted(decls.items()) if not (name in ("sac", "set-kb") and d.contract != m.CONTRACT)]
    path_to_name = {os.path.realpath(os.path.expanduser(str(e.get("path") or ""))): n for n, e in registry.items()}

    def one(decl) -> list:
        if decl.contract not in m.KNOWN_CONTRACTS:
            return [Check("modules", decl.module, "fail", f"declares unknown contract {decl.contract!r} ({decl.file})",
                          f"fix {decl.file}", module=decl.module)]
        if not m.installed(decl, ctx.env):
            return [m.not_installed(decl)]
        data, problem = m.run_json(decl, ctx.env)
        if problem:
            return [problem]
        if decl.contract == m.AIPLUS_CONTRACT:
            recs, problem = m.parse_aiplus(decl, data, set(registry))
        elif decl.contract == m.CONTRACT:
            recs, problem = m.parse_doctor1(decl, data)
            recs = m.join_by_path(recs, path_to_name)
        else:
            return [Check("modules", decl.module, "fail",
                          f"contract {decl.contract!r} is a built-in adapter's, not this module's ({decl.file})",
                          f"fix {decl.file}", module=decl.module)]
        if problem:
            return [problem]
        if not recs:
            return [Check("modules", decl.module, "ok", "reported no checks", module=decl.module)]
        return recs

    out: list = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for recs in pool.map(one, jobs):
            out += recs
    return out


def run_all(ctx: Context, workers: int = 8) -> list:
    from set_doctor import modules as m

    checks: list = []
    checks += check_install(ctx)
    checks += check_checkout(ctx)
    checks += check_tools(ctx)
    checks += check_mcp_probe(ctx)
    decls: dict = {}
    module_skip = None
    if ctx.child:
        module_skip = "module doctors are run by the parent set-doctor"
        checks.append(Check("modules", "modules", "skip", f"{m.CHILD_ENV}=1 — {module_skip}"))
        sac_by_path = None
    else:
        decls, problems = m.load_declarations(ctx.env)
        checks += problems
        sac_decl = decls.get("sac") if decls.get("sac") and decls["sac"].contract != m.CONTRACT else None
        sac_by_path, sac_check = sac_doctor(ctx, sac_decl)
        checks.append(sac_check)
    checks.append(check_relay(ctx))
    claude_projects = load_claude_projects(ctx)
    reg_path, registry = load_registry(ctx)
    if registry is None:
        checks.append(Check("project", "registry", "fail", f"the project registry is unreadable: {reg_path}",
                            sh(f"python3 -m json.tool {reg_path}")))
        registry = {}
    elif not registry:
        checks.append(Check("project", "registry", "warn", f"no project registered ({reg_path})",
                            sh("cd <project> && set-project init")))
    else:
        checks.append(Check("project", "registry", "ok", f"{len(registry)} project(s) in {reg_path}"))
    names = [n for n in sorted(registry) if not ctx.project_glob or fnmatch.fnmatch(n, ctx.project_glob)]
    names, archived = archived_entries(registry, names, ctx.project_glob)
    if archived:
        checks.append(archived_check(archived))
    names, gone = stale_entries(registry, names)
    if gone:
        checks.append(stale_check(gone))
    kb_decl = decls.get("set-kb")
    kb_command = None
    if kb_decl is not None and kb_decl.contract != m.CONTRACT:
        if m.installed(kb_decl, ctx.env):
            kb_command = kb_decl.command
        else:
            checks.append(m.not_installed(kb_decl))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        alive = {n: e for n, e in registry.items() if n not in gone and n not in archived}
        mod_future = pool.submit(run_modules, ctx, decls, alive, workers) if decls and not ctx.child else None
        for cs in pool.map(lambda n: check_project(ctx, n, registry[n], claude_projects, sac_by_path,
                                                   kb_command, module_skip, registry), names):
            checks += cs
        if mod_future is not None:
            wanted = set(names)
            # --project narrows the report, not the module's run: a record about a project the
            # glob excludes is left out, the same as that project's own checks.
            checks += [c for c in mod_future.result() if not c.project or c.project in wanted]
    checks += check_provider(ctx)
    checks += check_github(ctx)
    for c in checks:
        assert c.status in STATUSES, c
        if c.status in ("warn", "fail"):
            logger.info("%s/%s%s: %s — %s", c.section, c.project + "/" if c.project else "", c.name, c.status, c.detail)
    return checks
