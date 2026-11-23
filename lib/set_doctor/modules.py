"""Module doctors (change doctor-module-contract): discovered from declarations, run once,
their records merged into set-doctor's report and attributed to a module and a project.

A declaration is `<set-core config dir>/doctors.d/<module>.json`:

    {"module": "example", "command": ["example", "doctor", "--json"],
     "contract": "doctor/1", "install": "<one line that installs it>", "timeout_s": 120}

`doctor/1` is set-doctor/1's record shape plus `path`:

    {"schema": "doctor/1", "module": "example",
     "checks": [{"section", "name", "status", "detail", "fix"?, "path"?}]}

Three contracts that predate `doctor/1` are read through adapters: `sac.doctor/1` and
`set-kb.doctor/1` (built in, run even with no declaration) and `aiplus-doctor/1` (only when
declared). A declaration for `sac` or `set-kb` takes over that module's invocation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

CONTRACT = "doctor/1"
CHILD_ENV = "SET_DOCTOR_CHILD"
SAC_CONTRACT = "sac.doctor/1"
KB_CONTRACT = "set-kb.doctor/1"
AIPLUS_CONTRACT = "aiplus-doctor/1"
KNOWN_CONTRACTS = (CONTRACT, SAC_CONTRACT, KB_CONTRACT, AIPLUS_CONTRACT)
STATUSES = ("ok", "warn", "fail", "skip")
DEFAULT_TIMEOUT_S = 120
REQUIRED = ("module", "command", "contract", "install")


@dataclass
class Declaration:
    module: str
    command: list
    contract: str
    install: str
    file: str
    timeout_s: int = DEFAULT_TIMEOUT_S


def doctors_dir(env: dict) -> str:
    from set_kb.lifecycle import config_dir

    return os.path.join(config_dir(env), "doctors.d")


def load_declarations(env: dict) -> tuple:
    """(valid declarations by module, problem Checks). A broken or duplicate declaration is a
    `fail` naming its file(s), and is not used — the built-in adapter, if any, stays in charge."""
    from set_doctor.checks import Check

    d = doctors_dir(env)
    problems: list = []
    found: dict = {}
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
    except FileNotFoundError:
        logger.debug("no doctors.d at %s", d)
        return {}, []
    except OSError as e:
        return {}, [Check("modules", "doctors.d", "fail", f"{d} is unreadable: {e}", f"ls -l {d}")]
    for n in names:
        path = os.path.join(d, n)
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            missing = [k for k in REQUIRED if not raw.get(k)]
            if missing:
                raise ValueError(f"missing {', '.join(missing)}")
            if not isinstance(raw["command"], list) or not all(isinstance(a, str) for a in raw["command"]):
                raise ValueError("`command` must be a list of strings")
            decl = Declaration(module=str(raw["module"]), command=list(raw["command"]),
                               contract=str(raw["contract"]), install=str(raw["install"]), file=path,
                               timeout_s=int(raw.get("timeout_s") or DEFAULT_TIMEOUT_S))
        except (OSError, ValueError, TypeError) as e:
            logger.warning("declaration rejected: %s: %s", path, e)
            problems.append(Check("modules", n, "fail", f"declaration {path} is unusable: {e}",
                                  f"fix or delete {path}"))
            continue
        found.setdefault(decl.module, []).append(decl)
    out = {}
    for module, decls in found.items():
        if len(decls) > 1:
            files = ", ".join(x.file for x in decls)
            logger.warning("module %s declared %d times: %s", module, len(decls), files)
            problems.append(Check("modules", module, "fail", f"declared more than once: {files}",
                                  "keep one declaration per module", module=module))
            continue
        out[module] = decls[0]
    return out, problems


def child_env(env: dict) -> dict:
    return {**env, CHILD_ENV: "1"}


def installed(decl: Declaration, env: dict) -> Optional[str]:
    cmd = decl.command[0]
    if os.path.isabs(cmd):
        return cmd if os.access(cmd, os.X_OK) else None
    return shutil.which(cmd, path=env.get("PATH", ""))


def not_installed(decl: Declaration):
    from set_doctor.checks import Check

    return Check("modules", decl.module, "warn",
                 f"declared ({decl.file}) but `{decl.command[0]}` is not installed on this machine",
                 decl.install, module=decl.module)


def run_json(decl: Declaration, env: dict, cwd: Optional[str] = None) -> tuple:
    """(parsed JSON | None, problem Check | None). Never raises."""
    from set_doctor.checks import Check, run

    t0 = time.monotonic()
    rc, so, se = run(decl.command, cwd=cwd, timeout=decl.timeout_s, env=child_env(env))
    took = time.monotonic() - t0
    if rc is None and "timed out" in (se or ""):
        logger.warning("module %s timed out after %ss", decl.module, decl.timeout_s)
        return None, Check("modules", decl.module, "fail", f"timed out after {decl.timeout_s} s",
                           " ".join(decl.command), module=decl.module)
    try:
        data = json.loads(so)
    except ValueError:
        tail = (se or so or "").strip()[-300:]
        logger.warning("module %s gave no report (exit %s)", decl.module, rc)
        return None, Check("modules", decl.module, "fail", f"gave no parseable report (exit {rc}): {tail}",
                           " ".join(decl.command), module=decl.module)
    logger.info("module %s: exit %s in %.1fs", decl.module, rc, took)
    return data, None


def parse_doctor1(decl: Declaration, data) -> tuple:
    """(records, problem Check | None). An unknown schema or status is a failure of the module,
    never a silent drop (spec: an unknown contract is a failure, not an absence)."""
    from set_doctor.checks import Check

    bad = lambda why: ([], Check("modules", decl.module, "fail", why, " ".join(decl.command),  # noqa: E731
                                 module=decl.module))
    if not isinstance(data, dict):
        return bad("report is not a JSON object")
    if data.get("schema") != CONTRACT:
        return bad(f"report schema {data.get('schema')!r}, expected {CONTRACT!r}")
    checks = data.get("checks")
    if not isinstance(checks, list):
        return bad("report has no `checks` list")
    out = []
    for i, r in enumerate(checks):
        if not isinstance(r, dict) or r.get("status") not in STATUSES or not r.get("name"):
            return bad(f"record {i} has no name or a status outside {', '.join(STATUSES)}: {str(r)[:120]}")
        status = r["status"]
        fix = r.get("fix") or None
        if status in ("warn", "fail") and not fix:
            fix = f"{' '.join(decl.command)}   # the module gave no fix"
        out.append(Check(str(r.get("section") or decl.module), str(r["name"]), status, str(r.get("detail") or ""),
                         fix if status in ("warn", "fail") else None, module=decl.module,
                         path=r.get("path") or None))
    logger.info("module %s: %d record(s)", decl.module, len(out))
    return out, None


def parse_aiplus(decl: Declaration, data, registry_names: set) -> tuple:
    """`aiplus-doctor/1`: {"schema", "machine": [...], "repos": {name: [...]}}, records
    {check, status, detail, fix}. Repos join registered projects by name."""
    from set_doctor.checks import Check

    if not isinstance(data, dict) or data.get("schema") != AIPLUS_CONTRACT:
        return [], Check("modules", decl.module, "fail",
                         f"report schema {data.get('schema') if isinstance(data, dict) else None!r}, "
                         f"expected {AIPLUS_CONTRACT!r}", " ".join(decl.command), module=decl.module)

    def rec(r, section, project=None):
        status = r.get("status") if r.get("status") in STATUSES else "warn"
        fix = (r.get("fix") or None) if status in ("warn", "fail") else None
        if status in ("warn", "fail") and not fix:
            fix = f"{' '.join(decl.command)}   # the module gave no fix"
        return Check(section, str(r.get("check") or "?"), status, str(r.get("detail") or ""), fix,
                     project=project, module=decl.module)

    out = []
    for r in data.get("machine") or []:
        if str(r.get("check")) == "set-doctor":
            continue  # its verdict on the run that is reading it — self-referential (spec)
        out.append(rec(r, "modules"))
    for name, rs in (data.get("repos") or {}).items():
        known = name in registry_names
        for r in rs or []:
            c = rec(r, "project" if known else "modules", project=name if known else None)
            if not known:
                c.detail = f"{name}: {c.detail}" if c.detail else name
            out.append(c)
    logger.info("module %s: %d record(s), %d repo(s)", decl.module, len(out), len(data.get("repos") or {}))
    return out, None


def join_by_path(records: list, path_to_name: dict) -> list:
    """Attach a record carrying `path` to the registered project at the same real path; leave
    the rest under the module's own section."""
    for c in records:
        if not c.path:
            c.section = "modules"  # a machine-level record of the module; its own section name is
            continue               # not one set-doctor renders, so it would vanish from the text
        name = path_to_name.get(os.path.realpath(os.path.expanduser(c.path)))
        if name:
            c.project = name
            c.section = "project"
        else:
            c.section = "modules"
            c.detail = f"{c.path}: {c.detail}" if c.detail else c.path
    return records
