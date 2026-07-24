"""Read a project's development status through a contract it publishes itself.

WHY THIS EXISTS. set-core can see how orchestration is going — changes, gates, merges —
and nothing at all about how the *project* is going: what is broken, what is about to
ship, what is running where. That information exists, but it lives in the project's own
shapes: its bug tracker, its release files, its deploy scripts. A framework that reads
those shapes directly becomes a framework that only fits one project.

So the project publishes a command, and the command speaks a versioned contract:

    <configured command> <name> [args...]   → one JSON envelope on stdout

    {"contractVersion": 1, "generatedAt": "...", "command": "releases",
     "ok": true, "data": {...}}

set-core owns the ENVELOPE and nothing inside `data`. That split is deliberate and it is
the whole abstraction: the envelope is domain-free and this module validates it; `data`
is full of the project's domain — partner names, order numbers, business rules — and
this module neither interprets nor persists it.

**Never persist what comes back.** It is read at request time, shown, and dropped. Not
into this repo, not into a cache, not into a log. The logging here follows that rule:
shape, counts, and error classes — never a value out of `data`.

**Never invent a value.** A project that cannot answer must produce a visible gap, not a
plausible number. Everything here fails to `ok=False` with a reason a person can act on;
nothing falls back to zero, to an empty list, or to "probably fine". A dashboard that
quietly shows 0 open bugs because a script crashed is worse than one showing an error,
because only one of them gets fixed.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Envelope versions this module understands. A project announcing anything else is
#: refused rather than parsed on a guess — an unknown version may have moved a field
#: this code would then read as absent.
SUPPORTED_CONTRACT_VERSIONS = frozenset({1})

#: Config key under `set/orchestration/config.yaml`.
CONFIG_KEY = "status_api"

DEFAULT_TIMEOUT_SECONDS = 30

#: Hard cap on stdout. A contract answer is a summary; anything this large means the
#: project is streaming its database at us, and reading it all would be the framework's
#: problem, not the project's.
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class StatusConfig:
    """How to invoke a project's status contract."""

    command: str
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    cwd: Optional[str] = None

    @property
    def argv_prefix(self) -> List[str]:
        return shlex.split(self.command)


@dataclass(frozen=True)
class StatusResult:
    """One answer, or one visible gap. Never a guess."""

    command: str
    ok: bool
    data: Any = None
    error: Optional[str] = None
    error_class: Optional[str] = None
    contract_version: Optional[int] = None
    generated_at: Optional[str] = None

    @classmethod
    def failure(cls, command: str, error_class: str, error: str) -> "StatusResult":
        return cls(command=command, ok=False, error=error, error_class=error_class)


def load_status_config(project_path: str | Path) -> Optional[StatusConfig]:
    """Read the `status_api` block from a project's orchestration config.

    Returns None when the project has not published a contract — which is not an error.
    Most projects have not, and the surface simply stays empty for them.
    """
    config_path = Path(project_path) / "set" / "orchestration" / "config.yaml"
    if not config_path.is_file():
        return None

    try:
        import yaml
    except ImportError:  # pragma: no cover - environment without PyYAML
        logger.warning("project_status: PyYAML missing, cannot read %s", config_path)
        return None

    try:
        with open(config_path) as fh:
            raw = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("project_status: cannot read %s (%s)", config_path, type(exc).__name__)
        return None

    if not isinstance(raw, dict):
        return None
    block = raw.get(CONFIG_KEY)
    if not isinstance(block, dict):
        return None

    command = block.get("command")
    if not isinstance(command, str) or not command.strip():
        logger.warning(
            "project_status: %s.%s present but has no usable 'command'", CONFIG_KEY, config_path
        )
        return None

    timeout = block.get("timeout", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(timeout, int) or timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SECONDS

    cwd = block.get("cwd")
    return StatusConfig(
        command=command.strip(),
        timeout=timeout,
        cwd=cwd if isinstance(cwd, str) and cwd.strip() else None,
    )


def parse_envelope(command: str, raw: str) -> StatusResult:
    """Validate the envelope and lift `data` out of it, or explain why not.

    Kept separate from the subprocess call so the contract can be checked against a
    recorded answer without running anything.
    """
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        return StatusResult.failure(
            command, "invalid-json",
            f"the command did not produce JSON ({type(exc).__name__})",
        )

    if not isinstance(payload, dict):
        return StatusResult.failure(
            command, "invalid-envelope",
            f"expected a JSON object, got {type(payload).__name__}",
        )

    version = payload.get("contractVersion")
    if version is None:
        return StatusResult.failure(
            command, "missing-version",
            "the answer carries no contractVersion — refusing to guess its shape",
        )
    if version not in SUPPORTED_CONTRACT_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_CONTRACT_VERSIONS))
        return StatusResult.failure(
            command, "unsupported-version",
            f"contractVersion {version} is not one this set-core understands "
            f"(supported: {supported}) — upgrade set-core rather than reading it blind",
        )

    if payload.get("ok") is not True:
        # The project answered honestly that it could not answer. Carry its reason
        # through instead of replacing it with one of ours.
        reported = payload.get("error") or payload.get("message")
        return StatusResult(
            command=command, ok=False,
            error=str(reported) if reported else "the project reported ok=false with no reason",
            error_class="project-reported-failure",
            contract_version=version,
            generated_at=_str_or_none(payload.get("generatedAt")),
        )

    if "data" not in payload:
        return StatusResult.failure(
            command, "missing-data",
            "the answer is ok=true but carries no 'data'",
        )

    return StatusResult(
        command=command,
        ok=True,
        data=payload["data"],
        contract_version=version,
        generated_at=_str_or_none(payload.get("generatedAt")),
    )


def _str_or_none(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def query(
    project_path: str | Path,
    command: str,
    args: Optional[List[str]] = None,
    config: Optional[StatusConfig] = None,
) -> StatusResult:
    """Ask a project one question through its published contract.

    Every failure mode returns `ok=False` with an `error_class` — no exception escapes,
    because a status panel must render the gap rather than take the page down with it.
    """
    project_path = Path(project_path)
    cfg = config or load_status_config(project_path)
    if cfg is None:
        return StatusResult.failure(
            command, "not-configured",
            f"this project publishes no status contract (no '{CONFIG_KEY}.command' in "
            f"set/orchestration/config.yaml)",
        )

    argv = cfg.argv_prefix + [command] + list(args or [])
    cwd = cfg.cwd or str(project_path)

    # The consumer's own env, minus anything that would make its tooling interactive.
    env = dict(os.environ)
    env["CI"] = "1"
    env["NO_COLOR"] = "1"

    try:
        proc = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, timeout=cfg.timeout,
        )
    except FileNotFoundError:
        return StatusResult.failure(
            command, "command-not-found",
            f"cannot run the configured status command ({argv[0]!r} not found)",
        )
    except subprocess.TimeoutExpired:
        return StatusResult.failure(
            command, "timeout",
            f"the project did not answer within {cfg.timeout}s",
        )
    except OSError as exc:
        return StatusResult.failure(
            command, "spawn-failed",
            f"could not start the status command ({type(exc).__name__})",
        )

    if len(proc.stdout) > MAX_OUTPUT_BYTES:
        return StatusResult.failure(
            command, "response-too-large",
            f"the answer exceeded {MAX_OUTPUT_BYTES} bytes — a status contract returns a "
            f"summary, not a dump",
        )

    if proc.returncode != 0:
        # stderr is the project's, and may quote its own domain. Report that it failed
        # and how, never what it said.
        logger.warning(
            "project_status: '%s' exited %d (%d bytes on stderr)",
            command, proc.returncode, len(proc.stderr),
        )
        return StatusResult.failure(
            command, "nonzero-exit",
            f"the status command exited {proc.returncode}",
        )

    result = parse_envelope(command, proc.stdout.decode("utf-8", errors="replace"))
    logger.info(
        "project_status: '%s' → ok=%s class=%s version=%s",
        command, result.ok, result.error_class, result.contract_version,
    )
    return result


@dataclass
class StatusSnapshot:
    """Several answers gathered for one view. Held in memory, never written down."""

    results: Dict[str, StatusResult] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.results) and all(r.ok for r in self.results.values())

    @property
    def gaps(self) -> Dict[str, str]:
        """command → why it is missing. What the surface must show instead of a number."""
        return {
            name: (r.error or "unknown")
            for name, r in self.results.items() if not r.ok
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for an API response — a transport shape, not a stored one."""
        return {
            "ok": self.ok,
            "commands": {
                name: {
                    "ok": r.ok,
                    "data": r.data if r.ok else None,
                    "error": r.error,
                    "errorClass": r.error_class,
                    "generatedAt": r.generated_at,
                    "contractVersion": r.contract_version,
                }
                for name, r in self.results.items()
            },
            "gaps": self.gaps,
        }


def gather(
    project_path: str | Path,
    commands: List[str],
    config: Optional[StatusConfig] = None,
) -> StatusSnapshot:
    """Run several contract commands, keeping each one's failure separate.

    One command failing must not blank the others: a project with a broken release
    script still has bugs worth showing.
    """
    cfg = config or load_status_config(project_path)
    snapshot = StatusSnapshot()
    for name in commands:
        snapshot.results[name] = query(project_path, name, config=cfg)
    return snapshot
