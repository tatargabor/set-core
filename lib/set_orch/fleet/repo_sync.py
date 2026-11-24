"""The fleet's repository-sync view: is every recently active project committed and pushed?

Openspec change `fleet-repo-sync`. One request answers, for every registered project active
within a window (a commit by anybody on any branch), its branch, uncommitted entries, ahead/behind against its upstream, local
branches with commits on no remote, stashes, worktrees, the age of the last fetch, and a
three-valued hint on whether a push to the current branch may start a deployment.

Three properties are the point of the module, and each is a rule rather than an accident:

- **Computed on request only.** Nothing here runs on a timer, and nothing is cached: the owner
  asked for a view that costs nothing until it is opened, and a cache file would persist data
  derived from consumer trees.
- **A gap is not a zero.** A git call that fails or times out yields `None` plus a reason, and
  the row counts as a problem. A clean row is one that was measured clean.
- **Nothing read from a tree is persisted or logged.** Logs carry counts and the registered
  project names only — never a branch name, an in-tree path, a commit message or a URL. The
  answer itself carries the remote's HOST, never its URL.

The deploy hint reads the tree's own CI and hosting files. It is deliberately three-valued and
leans to `unknown`: a misread must make the reader ask, never make a deploying push look safe.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CONFIG_KEY = "fleet_repo_sync_days"
#: Registered project names the owner hid from this table (machine-local, a JSON list).
HIDDEN_KEY = "fleet_repo_sync_hidden"
DEFAULT_DAYS = 30.0
MIN_DAYS = 1.0
MAX_DAYS = 365.0

GIT_TIMEOUT_S = 10.0
SCAN_WORKERS = 8
FETCH_TIMEOUT_S = 30.0
FETCH_WORKERS = 4
#: A repository with more local branches than this is reported with the rest unmeasured.
MAX_BRANCHES = 60

YES, NO, UNKNOWN = "yes", "no", "unknown"

#: Files whose presence means a hosting provider is linked to the tree. The production branch
#: of such a link lives in the provider's settings, so the tree alone cannot say "no".
HOSTING_LINK_FILES = (
    ".vercel", "vercel.json", "netlify.toml", "wrangler.toml", "wrangler.json", "wrangler.jsonc",
    "fly.toml", "railway.json", "railway.toml", "render.yaml",
)

_GITLAB_RESERVED = {
    "stages", "variables", "default", "include", "workflow", "image", "services",
    "before_script", "after_script", "cache", "pages:deploy",
}


# --------------------------------------------------------------------------- #
# git plumbing
# --------------------------------------------------------------------------- #

def _git_env() -> Dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # A scan must never take the index lock another agent's commit is waiting for.
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    return env


def _git(root: Path, *args: str, timeout: float = GIT_TIMEOUT_S) -> Tuple[bool, str, str]:
    """Run one git command in `root`. Answers (ok, stdout, reason-if-not-ok)."""
    try:
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           timeout=timeout, env=_git_env())
    except subprocess.TimeoutExpired:
        return False, "", f"timed out after {timeout:g}s"
    except OSError as exc:
        return False, "", f"git not runnable ({type(exc).__name__})"
    if p.returncode != 0:
        first = (p.stderr or "").strip().splitlines()[:1]
        return False, p.stdout, (first[0][:160] if first else f"exit {p.returncode}")
    return True, p.stdout, ""


def _lines(out: str) -> List[str]:
    return [ln for ln in out.splitlines() if ln.strip()]


# --------------------------------------------------------------------------- #
# the activity window
# --------------------------------------------------------------------------- #

def window_days(requested: Optional[float] = None) -> float:
    """`requested`, else machine-local `fleet_repo_sync_days`, else 30 — clamped to 1..365."""
    value: Any = requested
    if value is None:
        try:
            from .. import local_config
            value = local_config.get(CONFIG_KEY)
        except Exception as exc:  # config unreadable: say so, fall back to the default
            logger.warning("repo-sync: %s unreadable (%s), using %gd", CONFIG_KEY,
                           type(exc).__name__, DEFAULT_DAYS)
            value = None
    try:
        days = float(value) if value is not None else DEFAULT_DAYS
    except (TypeError, ValueError):
        logger.warning("repo-sync: %s=%r is not a number, using %gd", CONFIG_KEY, value, DEFAULT_DAYS)
        days = DEFAULT_DAYS
    return max(MIN_DAYS, min(MAX_DAYS, days))


def newest_commit(root: Path) -> Optional[float]:
    """The newest committer date on any local OR remote-tracking branch — anybody's commit."""
    ok, out, _ = _git(root, "for-each-ref", "--sort=-committerdate", "--count=1",
                      "--format=%(committerdate:unix)", "refs/heads", "refs/remotes")
    if not ok:
        return None
    try:
        return float(out.strip()) if out.strip() else None
    except ValueError:
        return None


def _is_git_tree(root: Path) -> bool:
    return (root / ".git").exists()


def hidden_projects() -> List[str]:
    """The owner's hidden list. An unreadable value is an empty list, said in the log."""
    try:
        from .. import local_config
        raw = local_config.get(HIDDEN_KEY)
    except Exception as exc:
        logger.warning("repo-sync: %s unreadable (%s)", HIDDEN_KEY, type(exc).__name__)
        return []
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            import json
            raw = json.loads(raw)
        except ValueError:
            raw = [raw]
    if not isinstance(raw, list):
        logger.warning("repo-sync: %s is not a list, ignored", HIDDEN_KEY)
        return []
    return sorted({str(x) for x in raw if str(x).strip()})


def set_hidden(name: str, hidden: bool) -> List[str]:
    """Add or remove one name. Changes only the machine-local list, never a repository."""
    names = set(hidden_projects())
    before = name in names
    (names.add if hidden else names.discard)(name)
    from .. import local_config
    local_config.set_value(HIDDEN_KEY, sorted(names))
    logger.info("repo-sync: %s hidden %s -> %s (%d hidden)", name, before, hidden, len(names))
    return sorted(names)


def select_projects(projects: List[Dict[str, Any]], *, days: float, now: float, home: Path,
                    e2e_root: Optional[Path], hidden: Optional[List[str]] = None
                    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Split the registry into the listed projects and the counted exclusions.

    Activity is a commit by anybody on any local or remote-tracking branch within the window
    (owner, 2026-11-24: "commit decides"); sessions and fetches are not activity.
    """
    cutoff = now - days * 86400
    hidden_set = set(hidden or [])
    excluded: Dict[str, Any] = {"archived": 0, "hidden": 0, "e2e_run": 0, "inactive": 0,
                                "missing": [], "not_git": []}
    selected: List[Dict[str, Any]] = []
    e2e_prefix = str(e2e_root.resolve()) + os.sep if e2e_root else None
    for p in projects:
        name, path = p.get("name") or "", p.get("path") or ""
        if p.get("archived"):
            excluded["archived"] += 1
            continue
        if name in hidden_set:
            excluded["hidden"] += 1
            continue
        if e2e_prefix and path and (str(Path(path).resolve()) + os.sep).startswith(e2e_prefix):
            excluded["e2e_run"] += 1
            continue
        root = Path(path)
        if not path or not root.is_dir():
            excluded["missing"].append(name)
            continue
        if not _is_git_tree(root):
            excluded["not_git"].append(name)
            continue
        commit_t = newest_commit(root)
        if commit_t is None or commit_t < cutoff:
            excluded["inactive"] += 1
            continue
        selected.append({"name": name, "path": path, "active_by": ["commit"],
                         "last_commit_at": commit_t, "last_session_at": None})
    return selected, excluded


# --------------------------------------------------------------------------- #
# one repository's state
# --------------------------------------------------------------------------- #

def remote_host(url: str) -> Optional[str]:
    """The host of a remote URL — never the URL itself, never a credential."""
    u = (url or "").strip()
    if not u:
        return None
    m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^@/]*@)?([^/:]+)", u, re.I)
    if m:
        return m.group(1).lower()
    m = re.match(r"^(?:[^@/]+@)?([^/:]+):", u)  # scp-like: git@host:owner/repo
    if m:
        return m.group(1).lower()
    return "local"


def _age(ts: Optional[float], now: float) -> Optional[float]:
    return None if ts is None else max(0.0, now - ts)


def _branch(root: Path) -> Tuple[Optional[str], bool, Optional[str]]:
    """(branch, detached, error)."""
    ok, out, _ = _git(root, "symbolic-ref", "--short", "-q", "HEAD")
    if ok and out.strip():
        return out.strip(), False, None
    ok2, _, reason = _git(root, "rev-parse", "--verify", "-q", "HEAD")
    if ok2:
        return None, True, None
    return None, False, reason or "no HEAD"


def _upstream(root: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """(upstream, no_upstream_marker, error)."""
    ok, out, reason = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if ok and out.strip():
        return out.strip(), None, None
    low = reason.lower()
    if "no upstream" in low or "does not point to a branch" in low or "no such branch" in low:
        return None, "no-upstream", None
    return None, None, reason


def _unpushed_branches(root: Path, current: Optional[str], now: float,
                       errors: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    ok, out, reason = _git(root, "for-each-ref", "--format=%(refname:short)%09%(committerdate:unix)",
                           "refs/heads")
    if not ok:
        errors["unpushed_branches"] = reason
        return None
    refs = []
    for ln in _lines(out):
        b, _, t = ln.partition("\t")
        refs.append((b, float(t) if t.strip().isdigit() else None))
    found: List[Dict[str, Any]] = []
    if len(refs) > MAX_BRANCHES:
        errors["unpushed_branches"] = f"{len(refs)} branches, measured the newest {MAX_BRANCHES}"
        refs.sort(key=lambda r: r[1] or 0, reverse=True)
        refs = refs[:MAX_BRANCHES]
    for b, t in refs:
        ok, cnt, reason = _git(root, "rev-list", "--count", f"refs/heads/{b}", "--not", "--remotes")
        if not ok:
            errors.setdefault("unpushed_branches", reason)
            continue
        n = int(cnt.strip() or 0)
        if n > 0:
            found.append({"branch": b, "commits": n, "last_commit_age_s": _age(t, now),
                          "current": b == current})
    found.sort(key=lambda r: (not r["current"], -(r["commits"])))
    return found


def _fetch_age(root: Path, now: float) -> Optional[float]:
    ok, out, _ = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not ok or not out.strip():
        return None
    try:
        return _age((Path(out.strip()) / "FETCH_HEAD").stat().st_mtime, now)
    except OSError:
        return None  # never fetched: an absent age, not a zero


def _worktrees(root: Path, main_branch: Optional[str], now: float,
               errors: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    ok, out, reason = _git(root, "worktree", "list", "--porcelain")
    if not ok:
        errors["worktrees"] = reason
        return None
    blocks, cur = [], {}
    for ln in out.splitlines():
        if not ln.strip():
            if cur:
                blocks.append(cur)
            cur = {}
            continue
        k, _, v = ln.partition(" ")
        cur[k] = v if v else True
    if cur:
        blocks.append(cur)
    result = []
    main_path = str(root.resolve())
    for b in blocks:
        path = b.get("worktree")
        if not path or str(Path(path).resolve()) == main_path:
            continue
        branch = b.get("branch")
        branch = branch[len("refs/heads/"):] if isinstance(branch, str) and branch.startswith("refs/heads/") else None
        wt = Path(path)
        missing = not wt.exists() or "prunable" in b
        entry: Dict[str, Any] = {"path": path, "branch": branch, "detached": bool(b.get("detached")),
                                 "missing": missing, "uncommitted": None, "last_commit_age_s": None,
                                 "merged": None}
        if not missing:
            ok, st, _ = _git(wt, "status", "--porcelain")
            entry["uncommitted"] = len(_lines(st)) if ok else None
            ok, ct, _ = _git(wt, "log", "-1", "--format=%ct")
            if ok and ct.strip().isdigit():
                entry["last_commit_age_s"] = _age(float(ct.strip()), now)
        head = b.get("HEAD")
        if isinstance(head, str) and main_branch:
            ok, _, _ = _git(root, "merge-base", "--is-ancestor", head, f"refs/heads/{main_branch}")
            entry["merged"] = ok
        result.append(entry)
    return result


def _default_branch(root: Path) -> Optional[str]:
    ok, out, _ = _git(root, "symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD")
    if ok and "/" in out.strip():
        return out.strip().split("/", 1)[1]
    return None


def repo_state(root: Path, now: float) -> Dict[str, Any]:
    """Everything one row carries, except the project's name and activity."""
    errors: Dict[str, str] = {}
    branch, detached, err = _branch(root)
    if err:
        errors["branch"] = err

    ok, out, reason = _git(root, "status", "--porcelain")
    uncommitted = untracked = None
    if ok:
        lines = _lines(out)
        untracked = sum(1 for ln in lines if ln.startswith("??"))
        uncommitted = len(lines)
    else:
        errors["uncommitted"] = reason

    upstream, no_upstream, err = (None, None, None)
    ahead = behind = None
    if branch:
        upstream, no_upstream, err = _upstream(root)
        if err:
            errors["upstream"] = err
        if upstream:
            ok, out, reason = _git(root, "rev-list", "--left-right", "--count", "@{u}...HEAD")
            parts = out.split() if ok else []
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
            else:
                errors["ahead_behind"] = reason or "unreadable"

    ok, out, reason = _git(root, "stash", "list", "--format=%gd")
    stash = len(_lines(out)) if ok else None
    if not ok:
        errors["stash"] = reason

    remote_name = upstream.split("/", 1)[0] if upstream and "/" in upstream else None
    ok, rout, _ = _git(root, "remote")
    remotes = _lines(rout) if ok else []
    if remote_name not in remotes:
        remote_name = "origin" if "origin" in remotes else (remotes[0] if remotes else None)
    host = None
    if remote_name:
        ok, url, _ = _git(root, "remote", "get-url", remote_name)
        host = remote_host(url) if ok else None

    unpushed = _unpushed_branches(root, branch, now, errors)
    worktrees = _worktrees(root, branch, now, errors)
    default_branch = _default_branch(root)

    return {
        "branch": branch, "detached": detached,
        "uncommitted": uncommitted, "untracked": untracked,
        "upstream": upstream, "no_upstream": no_upstream == "no-upstream",
        "ahead": ahead, "behind": behind,
        "diverged": bool(ahead and behind),
        "unpushed_branches": unpushed,
        "stash": stash,
        "remote": remote_name, "remote_host": host, "remotes": len(remotes),
        "fetch_age_s": _fetch_age(root, now),
        "worktrees": worktrees,
        "default_branch": default_branch,
        "push_may_deploy": deploy_hint(root, branch, default_branch),
        "errors": errors,
    }


# --------------------------------------------------------------------------- #
# the deploy hint
# --------------------------------------------------------------------------- #

def _hint(value: str, source: Optional[str], reason: str, **extra: Any) -> Dict[str, Any]:
    return {"value": value, "source": source, "reason": reason, **extra}


_BRANCH_CMP = re.compile(
    r"\$CI_COMMIT_(?:BRANCH|REF_NAME)\s*(==|!=)\s*(?:[\"']([^\"']+)[\"']|(\$CI_DEFAULT_BRANCH))")
_BRANCH_RX = re.compile(r"\$CI_COMMIT_(?:BRANCH|REF_NAME)\s*(=~|!~)\s*/(.+?)/")
_MR_ONLY = re.compile(r"\$CI_PIPELINE_SOURCE\s*==\s*[\"']merge_request_event[\"']")


def _gitlab_if_matches(cond: str, branch: str, default_branch: Optional[str]) -> Optional[bool]:
    """Does a `rules: - if:` match a PUSH to `branch`? True / False / None (cannot tell)."""
    cmps = _BRANCH_CMP.findall(cond)
    rxs = _BRANCH_RX.findall(cond)
    if not cmps and not rxs:
        if _MR_ONLY.search(cond) and "||" not in cond:
            return False  # merge-request pipelines only: a push does not start them
        return None
    verdicts = []
    for op, lit, default in cmps:
        target = default_branch if default else lit
        if target is None:
            verdicts.append(None)
            continue
        eq = branch == target
        verdicts.append(eq if op == "==" else not eq)
    for op, rx in rxs:
        try:
            hit = re.search(rx, branch) is not None
        except re.error:
            verdicts.append(None)
            continue
        verdicts.append(hit if op == "=~" else not hit)
    if "||" in cond:
        if any(v is True for v in verdicts):
            return True
        # Another `||` term may be an unread variable: only a branch term that is true decides.
        return None
    # `&&` (or a single term): any branch term false decides; the other terms (a token
    # variable, a commit-message filter) are treated as possibly true — the deploying side.
    if any(v is False for v in verdicts):
        return False
    return None if any(v is None for v in verdicts) else True


def _gitlab_job_mode(job: Dict[str, Any], branch: str, default_branch: Optional[str]) -> str:
    """'auto' | 'manual' | 'never' | 'unknown' for a push to `branch`."""
    job_when = job.get("when")
    rules = job.get("rules")
    if isinstance(rules, list):
        for r in rules:
            if not isinstance(r, dict):
                return "unknown"
            cond = r.get("if")
            match = True if cond is None else _gitlab_if_matches(str(cond), branch, default_branch)
            if match is False:
                continue
            w = r.get("when")
            if w is None and job_when is not None:
                # A job-level `when` beside `rules`: how GitLab combines them is not settled by
                # the file, and reading it as "manual" would be the deploying misread.
                return "unknown"
            w = w or "on_success"
            if w == "never":
                return "never" if match else "unknown"
            if w == "manual":
                return "manual"
            return "auto" if match else "unknown"
        return "never"
    if rules is not None:
        return "unknown"
    only = job.get("only")
    if only is not None:
        refs = only.get("refs") if isinstance(only, dict) else only
        if isinstance(refs, str):
            refs = [refs]
        if not isinstance(refs, list):
            return "unknown"
        hit = False
        for ref in refs:
            ref = str(ref)
            if ref in (branch, "branches", "pushes"):
                hit = True
            elif ref.startswith("/") and ref.endswith("/") and len(ref) > 2:
                try:
                    hit = hit or re.search(ref[1:-1], branch) is not None
                except re.error:
                    return "unknown"
        if not hit:
            return "never"
    if job_when == "never":
        return "never"
    if job_when == "manual":
        return "manual"
    return "auto"


def _env_name(job: Dict[str, Any]) -> Optional[str]:
    env = job.get("environment")
    if isinstance(env, dict):
        env = env.get("name")
    return str(env) if env is not None else None


def _gitlab_hint(root: Path, branch: str, default_branch: Optional[str]) -> Optional[Dict[str, Any]]:
    f = root / ".gitlab-ci.yml"
    if not f.is_file():
        return None
    import yaml
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _hint(UNKNOWN, ".gitlab-ci.yml", "the CI file does not parse")
    if not isinstance(data, dict):
        return _hint(UNKNOWN, ".gitlab-ci.yml", "the CI file is not a mapping")
    unknown = None
    for name, job in data.items():
        if not isinstance(job, dict) or str(name).startswith(".") or name in _GITLAB_RESERVED:
            continue
        env = _env_name(job)
        is_deploy = job.get("stage") == "deploy" or (env is not None and "prod" in env.lower())
        if not is_deploy:
            continue
        mode = _gitlab_job_mode(job, branch, default_branch)
        if mode == "auto":
            return _hint(YES, ".gitlab-ci.yml", "a deploy job runs on a push to this branch",
                         job=str(name), environment=env)
        if mode == "unknown" and unknown is None:
            unknown = _hint(UNKNOWN, ".gitlab-ci.yml", "a deploy job's rules cannot be read for this branch",
                            job=str(name), environment=env)
    if unknown:
        return unknown
    if data.get("include"):
        return _hint(UNKNOWN, ".gitlab-ci.yml", "the CI file includes others that are not read")
    return _hint(NO, ".gitlab-ci.yml", "no deploy job runs on a push to this branch without a manual step")


def _gh_push_matches(on: Any, branch: str) -> Optional[bool]:
    if isinstance(on, str):
        return on == "push"
    if isinstance(on, list):
        return "push" in on
    if not isinstance(on, dict) or "push" not in on:
        return False
    push = on.get("push")
    if not isinstance(push, dict):
        return True
    if "branches" in push:
        pats = push.get("branches") or []
        return any(fnmatch.fnmatchcase(branch, str(p)) for p in pats)
    if "branches-ignore" in push:
        pats = push.get("branches-ignore") or []
        return not any(fnmatch.fnmatchcase(branch, str(p)) for p in pats)
    if "tags" in push and "branches" not in push:
        return False  # a tags-only push trigger
    return True


def _github_hint(root: Path, branch: str) -> Optional[Dict[str, Any]]:
    d = root / ".github" / "workflows"
    if not d.is_dir():
        return None
    files = sorted([*d.glob("*.yml"), *d.glob("*.yaml")])
    if not files:
        return None
    import yaml
    unknown = None
    for f in files:
        rel = f".github/workflows/{f.name}"
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            unknown = unknown or _hint(UNKNOWN, rel, "the workflow does not parse")
            continue
        if not isinstance(data, dict):
            continue
        on = data.get("on", data.get(True))  # YAML 1.1 reads a bare `on:` key as True
        if not _gh_push_matches(on, branch):
            continue
        wf_deploy = "deploy" in str(data.get("name", "")).lower()
        for job_id, job in (data.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            env = _env_name(job)
            label = f"{job_id} {job.get('name', '')}".lower()
            if not (wf_deploy or "deploy" in label or (env and "prod" in env.lower())):
                continue
            cond = str(job.get("if", ""))
            heads = re.findall(r"refs/heads/([A-Za-z0-9._/-]+)", cond)
            if heads and branch not in heads:
                continue
            return _hint(YES, rel, "a workflow deploys on a push to this branch", job=str(job_id),
                         environment=env)
    return unknown or _hint(NO, ".github/workflows", "no workflow deploys on a push to this branch")


def deploy_hint(root: Path, branch: Optional[str], default_branch: Optional[str] = None) -> Dict[str, Any]:
    """Whether a push to `branch` may start a deployment: yes / no / unknown, naming the file."""
    if not branch:
        return _hint(UNKNOWN, None, "no current branch")
    hints = [h for h in (_gitlab_hint(root, branch, default_branch), _github_hint(root, branch)) if h]
    for h in hints:
        if h["value"] == YES:
            return h
    links = [n for n in HOSTING_LINK_FILES if (root / n).exists()]
    if links:
        return _hint(UNKNOWN, links[0], "a hosting provider is linked; its production branch is set there")
    for h in hints:
        if h["value"] == UNKNOWN:
            return h
    if hints:
        return hints[0]
    return _hint(NO, None, "no CI or hosting file in the tree")


# --------------------------------------------------------------------------- #
# problems, the whole answer, the fetch
# --------------------------------------------------------------------------- #

def problems(row: Dict[str, Any]) -> List[str]:
    out = []
    if row.get("errors"):
        out.append("unreadable")
    if row.get("uncommitted"):
        out.append("uncommitted")
    if row.get("diverged"):
        out.append("diverged")
    elif row.get("ahead"):
        out.append("ahead")
    elif row.get("behind"):
        out.append("behind")
    if row.get("no_upstream"):
        out.append("no-upstream")
    if any(not b.get("current") or row.get("no_upstream") for b in (row.get("unpushed_branches") or [])):
        out.append("unpushed-branch")
    if (row.get("push_may_deploy") or {}).get("value") == YES:
        out.append("push-may-deploy")
    return out


def _e2e_root() -> Optional[Path]:
    try:
        from ..registry_prune import e2e_runs_root  # type: ignore[attr-defined]
        return Path(e2e_runs_root())
    except Exception:
        return Path.home() / ".local" / "share" / "set-core" / "e2e-runs"


def collect(days: Optional[float] = None, *, projects: Optional[List[Dict[str, Any]]] = None,
            home: Optional[Path] = None, now: Optional[float] = None,
            e2e_root: Optional[Path] = None, hidden: Optional[List[str]] = None) -> Dict[str, Any]:
    """The whole answer for `GET /api/fleet/repo-sync`."""
    t0 = time.monotonic()
    now = time.time() if now is None else now
    home = Path.home() if home is None else home
    d = window_days(days)
    if projects is None:
        from ..project_registry import load_projects
        projects = load_projects()
    hidden = hidden_projects() if hidden is None else hidden
    listed, excluded = select_projects(projects, days=d, now=now, home=home,
                                       e2e_root=_e2e_root() if e2e_root is None else e2e_root,
                                       hidden=hidden)

    def one(p: Dict[str, Any]) -> Dict[str, Any]:
        t = time.monotonic()
        try:
            row = {**p, **repo_state(Path(p["path"]), now)}
        except Exception as exc:  # one broken tree must not take the table down
            logger.warning("repo-sync: %s unreadable (%s)", p["name"], type(exc).__name__)
            row = {**p, "errors": {"repository": type(exc).__name__}}
        row["last_commit_age_s"] = _age(p.get("last_commit_at"), now)
        row["last_session_age_s"] = _age(p.get("last_session_at"), now)
        row["problems"] = problems(row)
        logger.debug("repo-sync: %s measured in %.0f ms", p["name"], (time.monotonic() - t) * 1000)
        return row

    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        rows = list(pool.map(one, listed))
    rows.sort(key=lambda r: (not r["problems"], r["name"]))
    problem_count = sum(1 for r in rows if r["problems"])
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info("repo-sync: %d project(s), %d with problems, excluded archived=%d hidden=%d e2e=%d "
                "inactive=%d missing=%d not-git=%d, %d ms", len(rows), problem_count, excluded["archived"],
                excluded["hidden"],
                excluded["e2e_run"], excluded["inactive"], len(excluded["missing"]),
                len(excluded["not_git"]), duration_ms)
    return {"generated_at": now, "days": d, "duration_ms": duration_ms, "projects": rows,
            "problem_count": problem_count, "excluded": excluded,
            "hidden": sorted(n for n in hidden if n in {p.get("name") for p in projects})}


def _fetch_one(name: str, path: str, timeout: float) -> Dict[str, Any]:
    env = _git_env()
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=10")
    try:
        p = subprocess.run(["git", "-C", path, "fetch", "--all", "--prune", "--quiet"],
                           capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"name": name, "result": "timeout", "reason": f"no answer within {timeout:g}s"}
    except OSError as exc:
        return {"name": name, "result": "failed", "reason": type(exc).__name__}
    if p.returncode != 0:
        first = (p.stderr or "").strip().splitlines()[:1]
        return {"name": name, "result": "failed", "reason": first[0][:160] if first else f"exit {p.returncode}"}
    return {"name": name, "result": "ok", "reason": None}


def fetch(names: Optional[List[str]] = None, days: Optional[float] = None, *,
          projects: Optional[List[Dict[str, Any]]] = None, home: Optional[Path] = None,
          timeout: float = FETCH_TIMEOUT_S) -> Dict[str, Any]:
    """`git fetch --all --prune` across the listed projects, or the named ones."""
    t0 = time.monotonic()
    if projects is None:
        from ..project_registry import load_projects
        projects = load_projects()
    if names:
        wanted = set(names)
        targets = [(p["name"], p["path"]) for p in projects
                   if p.get("name") in wanted and p.get("path") and Path(p["path"]).is_dir()]
        unknown = sorted(wanted - {n for n, _ in targets})
    else:
        listed, _ = select_projects(projects, days=window_days(days), now=time.time(),
                                    home=Path.home() if home is None else home, e2e_root=_e2e_root(),
                                    hidden=hidden_projects())
        targets = [(p["name"], p["path"]) for p in listed]
        unknown = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        results = list(pool.map(lambda t: _fetch_one(t[0], t[1], timeout), targets))
    results += [{"name": n, "result": "failed", "reason": "not a registered project with a tree"} for n in unknown]
    counts = {k: sum(1 for r in results if r["result"] == k) for k in ("ok", "timeout", "failed")}
    logger.info("repo-sync fetch: %d project(s): ok=%d timeout=%d failed=%d, %d ms", len(results),
                counts["ok"], counts["timeout"], counts["failed"], int((time.monotonic() - t0) * 1000))
    return {"results": results, **counts}
