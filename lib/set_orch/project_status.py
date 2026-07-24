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

**A field's name is not a promise about what it counts.** Whatever renders this data
should prefer counts and lists over free-text summaries, and should not promote a field
to a headline just because it reads like one. Two failure modes have been measured on a
real contract: a description written when a release was opened, still displayed after a
dozen changes landed under it; and a count whose name said one thing while it counted
another. Both render as confident, specific, wrong. When a contract offers both a
summary and a count of the thing summarised, show the count too — it is the one that
cannot go stale without the underlying list changing.
"""

from __future__ import annotations

import json
import logging
import os
import re
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

#: Config key under `set/orchestration/config.yaml`. An operator override.
CONFIG_KEY = "status_api"

#: Repo-root manifest a project drops to announce its own entry point, so the contract
#: is DISCOVERABLE rather than hand-configured once per project:
#:
#:     {"contractVersion": 1, "command": ["node", "scripts/set-api.mjs"], "cwd": "."}
#:
#: `command` is a LIST on purpose. A string would have to be split, and splitting is
#: where a path with a space silently becomes two arguments. Nothing here assumes an
#: interpreter: the next project to publish a contract may be Python, Go, or a binary.
MANIFEST_FILENAME = ".set-endpoint.json"

DEFAULT_TIMEOUT_SECONDS = 30

#: Hard cap on stdout. A contract answer is a summary; anything this large means the
#: project is streaming its database at us, and reading it all would be the framework's
#: problem, not the project's.
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


#: A contract command name, as it may be appended to the argv. Constrained because the
#: name arrives from an HTTP query string on the way to `subprocess.run`: no leading dash
#: (so it can never be read as a flag), no separators, no spaces. The allowlist below is
#: the real guard; this is what holds when a project declares nothing.
_COMMAND_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


def is_valid_command_name(name: str) -> bool:
    """Whether a string is shaped like a contract command."""
    return bool(_COMMAND_NAME.match(name or ""))


@dataclass(frozen=True)
class StatusConfig:
    """How to invoke a project's status contract.

    `command` accepts a list (from the manifest — unambiguous) or a string (from the
    operator config — convenient). `source` records which one won, because "why is it
    calling THAT" is the first question anyone asks when a status panel misbehaves.

    `commands` is what the project says it ANSWERS. set-core does not keep a built-in
    list of contract commands: the framework would then be guessing on the project's
    behalf, and a project that grows a sixth question would need a set-core release to be
    seen. Empty means undeclared, which is not the same as none — it means ask by name.
    """

    command: str | List[str]
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    cwd: Optional[str] = None
    source: str = "config"
    commands: tuple = ()
    #: Commands that CHANGE something on the project's side. Kept in a list of their
    #: own, never merged with `commands`, because the separation is the safety property:
    #: a renderer walking the read list can then never call a write by accident, and a
    #: caller asking to write can never reach a command the project did not mark as one.
    #: A name in both lists is refused outright — see `_declared_commands`.
    write_commands: tuple = ()
    #: Which answer a reader should be shown FIRST. Without it the surface opens whatever
    #: the project happened to declare first, which is an ordering decision nobody made.
    #: The project knows which of its answers is "where do we stand"; set-core cannot,
    #: and must not guess it from a name. None means no preference — see `_primary`.
    primary: Optional[str] = None
    #: Declared read commands that must NOT run on a page load. Still reads, still
    #: harmless to call — but expensive enough that asking automatically would either
    #: make the page unusable or, worse, get the whole surface quietly abandoned. A
    #: measured example: probing whether a deployed environment answers took minutes.
    #: The alternative to this flag is the project dropping the command from its declared
    #: list, which trades a slow answer for NO answer — the wrong direction, since "is
    #: the live system up" is exactly the kind of thing a status screen exists for.
    on_demand: tuple = ()

    @property
    def argv_prefix(self) -> List[str]:
        if isinstance(self.command, (list, tuple)):
            return [str(part) for part in self.command]
        return shlex.split(self.command)


def _declared_commands(raw: Any) -> tuple:
    """Read a declared command list, dropping anything not shaped like a command name."""
    if not isinstance(raw, (list, tuple)):
        return ()
    out = []
    for item in raw:
        name = str(item).strip()
        if is_valid_command_name(name):
            out.append(name)
        elif name:
            logger.warning(
                "project_status: ignoring declared command %r — not a command name", name
            )
    return tuple(dict.fromkeys(out))


def _split_command_lists(read_raw: Any, write_raw: Any) -> tuple:
    """Read the two declared lists, refusing any name that appears in both.

    An overlap is not a conflict to resolve by precedence — it means the project has
    told us a command both is and is not safe to call on a page load. There is no
    reading of that which is safe, so the name is dropped from both lists and has to be
    asked for by neither.
    """
    read = _declared_commands(read_raw)
    write = _declared_commands(write_raw)
    both = set(read) & set(write)
    if both:
        logger.warning(
            "project_status: %s declared in BOTH commands and writeCommands — dropping "
            "from both; a command cannot be safe to call on a page load and also change "
            "something", ", ".join(sorted(both)),
        )
        read = tuple(n for n in read if n not in both)
        write = tuple(n for n in write if n not in both)
    return read, write


def _primary(raw: Any, read_cmds: tuple, write_cmds: tuple) -> Optional[str]:
    """Read the project's preferred opening answer, or None if it named nothing usable.

    Three ways this can be wrong, and all three resolve to None rather than to an error,
    because the cost of ignoring a preference is one extra click and the cost of honouring
    a bad one is a surface that opens on something that cannot be shown:

    - a name that is not declared as a read command — including a stale one left behind
      after the command was renamed;
    - a WRITE command, which would mean opening the page performs the write's tab and
      invites a click on a mutation nobody asked for;
    - anything not shaped like a command name at all.

    Each is logged, because a preference silently not taking effect is exactly the kind of
    thing that gets re-declared three times before anyone looks.
    """
    if raw is None:
        return None
    name = str(raw).strip()
    if not name:
        return None
    if not is_valid_command_name(name):
        logger.warning("project_status: ignoring primary %r — not a command name", name)
        return None
    if name in write_cmds:
        logger.warning(
            "project_status: ignoring primary %r — it is a WRITE command; a surface must "
            "not open on something that changes state", name,
        )
        return None
    if name not in read_cmds:
        logger.warning(
            "project_status: ignoring primary %r — not among the declared commands (%s)",
            name, ", ".join(read_cmds) or "none",
        )
        return None
    return name


def _on_demand(raw: Any, read_cmds: tuple) -> tuple:
    """Read the declared do-not-auto-run list, keeping only real read commands.

    A name that is not a declared read command is dropped: it can only be a typo, a
    rename left behind, or a write command — and a write command in here would be
    meaningless, since writes never run on a page load anyway.

    The fail direction is the point. Ignoring a valid entry costs a slow page load, which
    is visible and annoying. Honouring an invalid one would silently stop asking a
    question the project believes it publishes — a gap that looks exactly like a project
    with nothing to say.
    """
    if not isinstance(raw, (list, tuple)):
        return ()
    out = []
    for item in raw:
        name = str(item).strip()
        if not is_valid_command_name(name):
            if name:
                logger.warning(
                    "project_status: ignoring onDemand %r — not a command name", name
                )
            continue
        if name not in read_cmds:
            logger.warning(
                "project_status: ignoring onDemand %r — not among the declared commands",
                name,
            )
            continue
        out.append(name)
    return tuple(dict.fromkeys(out))


def load_manifest(project_path: str | Path) -> Optional[StatusConfig]:
    """Read the repo-root endpoint manifest, or None when there is none.

    A manifest announcing a contract version this set-core does not understand is
    refused HERE, before anything is run — the alternative is spawning a process whose
    answer we would then have to reject anyway.
    """
    path = Path(project_path) / MANIFEST_FILENAME
    if not path.is_file():
        return None

    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning(
            "project_status: unreadable %s (%s) — ignoring it",
            MANIFEST_FILENAME, type(exc).__name__,
        )
        return None

    if not isinstance(raw, dict):
        return None

    version = raw.get("contractVersion")
    if version is not None and version not in SUPPORTED_CONTRACT_VERSIONS:
        logger.warning(
            "project_status: %s announces contractVersion %s, which this set-core does "
            "not support — not calling it", MANIFEST_FILENAME, version,
        )
        return None

    command = raw.get("command")
    if isinstance(command, (list, tuple)):
        parts = [str(p) for p in command if str(p).strip()]
        if not parts:
            return None
        command = parts
    elif isinstance(command, str) and command.strip():
        command = command.strip()
    else:
        logger.warning("project_status: %s has no usable 'command'", MANIFEST_FILENAME)
        return None

    timeout = raw.get("timeout", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(timeout, int) or timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SECONDS

    cwd = raw.get("cwd")
    resolved_cwd: Optional[str] = None
    if isinstance(cwd, str) and cwd.strip() and cwd.strip() != ".":
        resolved_cwd = str((Path(project_path) / cwd.strip()).resolve())

    read_cmds, write_cmds = _split_command_lists(
        raw.get("commands"), raw.get("writeCommands"),
    )
    return StatusConfig(
        command=command, timeout=timeout, cwd=resolved_cwd, source="manifest",
        commands=read_cmds, write_commands=write_cmds,
        primary=_primary(raw.get("primary"), read_cmds, write_cmds),
        on_demand=_on_demand(raw.get("onDemand"), read_cmds),
    )


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
    #: Field names the project still emits but no longer stands behind. See
    #: `_deprecated_fields` for why this is the project's call and not the framework's.
    deprecated: tuple = ()

    @classmethod
    def failure(cls, command: str, error_class: str, error: str) -> "StatusResult":
        return cls(command=command, ok=False, error=error, error_class=error_class)


def resolve_status_config(project_path: str | Path) -> Optional[StatusConfig]:
    """Find how to call this project, preferring an operator's explicit override.

    Order: `status_api` in the orchestration config, then the repo-root manifest. The
    override wins because a manifest is committed by the project and an override is
    chosen by whoever is running set-core right now — the person present when something
    is wrong must be able to redirect it without editing someone else's repository.

    None means the project publishes no contract. That is not an error; most projects
    do not, and their status surface simply stays empty.
    """
    return load_status_config(project_path) or load_manifest(project_path)


def load_status_config(project_path: str | Path) -> Optional[StatusConfig]:
    """Read the `status_api` block from a project's orchestration config."""
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
    read_cmds, write_cmds = _split_command_lists(
        block.get("commands"), block.get("write_commands"),
    )
    return StatusConfig(
        command=command.strip(),
        timeout=timeout,
        cwd=cwd if isinstance(cwd, str) and cwd.strip() else None,
        commands=read_cmds, write_commands=write_cmds,
        primary=_primary(block.get("primary"), read_cmds, write_cmds),
        on_demand=_on_demand(block.get("on_demand"), read_cmds),
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
        deprecated=_deprecated_fields(payload.get("deprecated")),
    )


def _deprecated_fields(raw: Any) -> tuple:
    """Field names the project keeps emitting but no longer stands behind.

    Read from the envelope, never decided here. A deprecated field usually exists
    because removing it would break someone, so it goes on being sent — and a renderer
    that shows every field it receives will then put the stale value NEXT TO the correct
    one, contradicting it. Measured on a live screen: an old count read `1` beside its
    replacement's `2`, which is precisely the ambiguity the replacement was introduced
    to end.

    The alternative was to name the field in set-core and hide it. That is one line and
    it is the wrong line: the framework would then hold a list of one project's field
    names, and the next project's stale field would contradict its replacement until
    someone shipped a set-core release. The project knows which of its fields it no
    longer stands behind; it is the only side that can know.
    """
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(
        str(item).strip() for item in raw if str(item).strip()
    ))


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
    cfg = config or resolve_status_config(project_path)
    if cfg is None:
        return StatusResult.failure(
            command, "not-configured",
            f"this project publishes no status contract — no '{CONFIG_KEY}.command' in "
            f"set/orchestration/config.yaml and no {MANIFEST_FILENAME} at its root",
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


#: A flag name a caller may send with a write. Same shape as a command name, for the
#: same reason: it becomes an argv entry.
def is_valid_flag_name(name: str) -> bool:
    return bool(_COMMAND_NAME.match(name or ""))


def write(
    project_path: str | Path,
    command: str,
    args: Optional[Dict[str, Any]] = None,
    config: Optional[StatusConfig] = None,
) -> StatusResult:
    """Ask the project to RECORD something. set-core never writes; it asks.

    That distinction is the design, not a turn of phrase. The value lives on the
    project's side, in a store the project chose, written by the project's own command.
    set-core holds no copy and no memory of having asked — which is only safe because
    the write is idempotent: sending the same acknowledgement twice is a successful
    no-op, so the surface never has to remember what it already sent.

    The command must appear in the project's `writeCommands`. Not in `commands`, and
    not merely be well-shaped — a project that never declared a write has none, and no
    argument from this side changes that.

    Arguments arrive as `{flag: value}` and become `--flag value` argv entries. There is
    no shell, so nothing is interpolated; the one remaining hazard is a VALUE that looks
    like a flag, which is refused rather than escaped.

    **What may be declared a write command at all — the standard, arrived at with the
    first project to publish one and adopted as the general rule.** The first write was
    acceptable because it appends to a file in the project's own repository, and is
    therefore *structurally* incapable of reaching a live system: no network, no database,
    no deployment. That is the bar. A write that reaches anything else — a database, an
    HTTP endpoint, another service's API — is not covered by this design and must not be
    declared here without the operator deciding so explicitly, however harmless it looks
    from the command's name.

    The reason to write the bar down rather than trust it: this function cannot check it.
    set-core spawns a command it was told to spawn and cannot know what the command does.
    So the guarantee is not enforced here — it is a property of *which commands a project
    declares*, and it survives only as long as someone restates it at the moment a second
    kind of write is proposed.
    """
    project_path = Path(project_path)
    cfg = config or resolve_status_config(project_path)
    if cfg is None:
        return StatusResult.failure(
            command, "not-configured", "this project publishes no status contract",
        )

    if command not in cfg.write_commands:
        declared = ", ".join(cfg.write_commands) or "none"
        return StatusResult.failure(
            command, "not-a-write-command",
            f"the project does not publish {command!r} as a write command "
            f"(it declares: {declared})",
        )

    argv = cfg.argv_prefix + [command]
    for flag, value in (args or {}).items():
        if not is_valid_flag_name(flag):
            return StatusResult.failure(
                command, "invalid-argument", f"not an argument name: {flag!r}",
            )
        text = str(value)
        if text.startswith("-"):
            # With no shell there is no injection, but argv is positional: a value
            # beginning with a dash is read by the project's own parser as the next
            # flag, silently shifting everything after it.
            return StatusResult.failure(
                command, "invalid-argument",
                f"the value for --{flag} starts with '-', which the project would read "
                f"as another flag",
            )
        argv += [f"--{flag}", text]

    env = dict(os.environ)
    env["CI"] = "1"
    env["NO_COLOR"] = "1"

    logger.info("project_status: WRITE '%s' with %d argument(s)", command, len(args or {}))
    try:
        proc = subprocess.run(
            argv, cwd=cfg.cwd or str(project_path), env=env,
            capture_output=True, timeout=cfg.timeout,
        )
    except FileNotFoundError:
        return StatusResult.failure(
            command, "command-not-found", f"cannot run the write command ({argv[0]!r} not found)",
        )
    except subprocess.TimeoutExpired:
        # A timed-out write is the one case where "did it happen?" has no answer here.
        # Saying so is the only honest report; the project's own record is the truth,
        # and re-asking is safe because the write is idempotent.
        return StatusResult.failure(
            command, "timeout",
            f"the project did not answer within {cfg.timeout}s — whether it recorded the "
            f"change is unknown from here; re-reading the project is the only way to tell",
        )
    except OSError as exc:
        return StatusResult.failure(
            command, "spawn-failed", f"could not start the write command ({type(exc).__name__})",
        )

    if proc.returncode != 0:
        logger.warning(
            "project_status: WRITE '%s' exited %d (%d bytes on stderr)",
            command, proc.returncode, len(proc.stderr),
        )
        return StatusResult.failure(
            command, "nonzero-exit", f"the write command exited {proc.returncode}",
        )

    return parse_envelope(command, proc.stdout.decode("utf-8", errors="replace"))


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
                    "deprecated": list(r.deprecated),
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
    cfg = config or resolve_status_config(project_path)
    snapshot = StatusSnapshot()
    for name in commands:
        snapshot.results[name] = query(project_path, name, config=cfg)
    return snapshot
