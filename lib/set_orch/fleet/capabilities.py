"""What a project has WIRED IN, and the three answers that are not two — task 2.6.

A capability is connected, not connected, or **unknown**, and the third is not a
polite version of the second. *Not connected* invites wiring it in; *unknown*
says the question could not be answered, and a screen that renders the two alike
invites someone to install something they may already have.

## What is NOT a signal, measured before anything was built

`.claude/` exists in **12 of 12** projects that had a live agent, because every
project somebody opens an agent in has one. Counting it would have reported the
framework installed everywhere — a false value of exactly the kind this screen
exists against, and the first thing measured here. The `opsx` command count is no
better: it spread 5 → 13 across those twelve *including set-core's own 12*,
because the OpenSpec CLI generates those files in each project rather than the
framework deploying them.

So a capability report names **what the framework actually installs**, and it
takes that from the framework's own deploy sources rather than from a list
somebody maintains by hand. A hand-kept list is a second copy of the manifest,
and it drifts at the moment it is written.

## `inferred` is the NORMAL case here, not a footnote

Task 2.9's wording assumes the install ledger answers and that inference is the
fallback. Measured across those same twelve projects: a ledger exists for **1 of
12**, and inside that one it covers **4 of its 16 rule files**. So the fallback
is the answer for eleven projects out of twelve and for three quarters of the
files in the twelfth — and the surface has to make *inferred* legible rather than
exceptional.

**Un-ledgered is not a synonym for stale.** For a file the ledger does not cover,
the framework cannot separate *the project edited it* from *our own template
moved on*, and `cannot tell` is the honest report. Rendering it as stale would
accuse a project of drift the framework has no evidence for.

## Confidentiality

Paths inside a consumer's tree are read and counted here. Counts and capability
names may be shown; nothing derived from the project is written down, and the
diagnostics name the capability and the count, never a path.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "CONNECTED", "NOT_CONNECTED", "UNKNOWN",
    "Capability", "CapabilityReport",
    "framework_capabilities", "report_for_project",
]

#: The framework installs these files and the project has them.
CONNECTED = "connected"
#: The framework installs these files and the project has none of them.
NOT_CONNECTED = "not-connected"
#: The question could not be answered. NOT a synonym for the one above.
UNKNOWN = "unknown"
#: Some of the capability's files are there and some are not. A FOURTH value,
#: because the requirement says a capability is connected when *the files* that
#: constitute it are present — plural — and one shared file out of four is not
#: that. Measured the moment this ran on real projects: two module capabilities
#: reported connected on a single file they share with a third, which is a false
#: value in the reassuring direction, and it says "already wired in" about a
#: project that is not.
PARTIAL = "partial"


@dataclass(frozen=True)
class Capability:
    """One named group of files the framework deploys, with its target paths.

    `targets` are project-relative and produced by the DEPLOY ENGINE's own
    mapping function rather than by a second copy of it here — `rules/x.md`
    becomes `.claude/rules/x.md` and `framework-rules/x.md` becomes
    `.claude/rules/set-x.md`, and a capability report that re-derived those rules
    would start reporting a project as missing files it has the day the mapping
    changes.
    """

    name: str
    targets: tuple = ()
    #: Where the declaration came from, so a reader can go and look.
    source: str = ""


@dataclass
class CapabilityState:
    """One capability, as this project has it."""

    name: str
    state: str = UNKNOWN
    present: int = 0
    total: int = 0
    #: Files present and covered by the install ledger — provenance is known.
    ledgered: int = 0
    #: Present, not in the ledger. **Not stale**: the framework cannot tell a
    #: project's own edit from its own drift for these, and saying either would
    #: be a claim it cannot support.
    inferred: int = 0
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return {"name": self.name, "state": self.state, "present": self.present,
                "total": self.total, "ledgered": self.ledgered,
                "inferred": self.inferred, "reason": self.reason}


@dataclass
class CapabilityReport:
    """Every capability for one project, plus how the answer was reached."""

    capabilities: List[CapabilityState] = field(default_factory=list)
    #: True when a ledger was found. False is ordinary — measured 1 project in 12.
    ledger_present: bool = False
    #: Set when the project tree itself could not be read, so every capability is
    #: `unknown` for ONE reason rather than twelve.
    unreadable: Optional[str] = None
    #: True when the project DECLARED what it wants. The requirement puts the
    #: declaration ahead of file presence, and for a reason: a declaration can
    #: express a version mismatch and a file cannot — a file is either there or
    #: not, so inference is structurally blind to a half-upgraded project.
    declared: bool = False
    #: `module -> comparison`, only where a declaration exists. `unknown` is never
    #: rendered as a match: the whole reason to ask is the case where they differ.
    versions: List[Dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "capabilities": [c.as_dict() for c in self.capabilities],
            "ledger_present": self.ledger_present,
            "unreadable": self.unreadable,
            # Counted from the data, never from a declaration.
            "connected": sum(1 for c in self.capabilities if c.state == CONNECTED),
            "partial": sum(1 for c in self.capabilities if c.state == PARTIAL),
            "not_connected": sum(1 for c in self.capabilities if c.state == NOT_CONNECTED),
            "unknown": sum(1 for c in self.capabilities if c.state == UNKNOWN),
            "declared": self.declared,
        }


def _framework_root(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit)
    # …/lib/set_orch/fleet/capabilities.py → the repository root
    return Path(__file__).resolve().parents[3]


def _relative_target(template_rel: str) -> str:
    """The project-relative path a template file lands at.

    ⚠ Written as its own function because the obvious one-liner was WRONG and
    the wrongness was invisible in the code and obvious in the output:
    `.as_posix().lstrip("./")` strips *characters*, not a prefix, so
    `.claude/rules/x.md` came back as `claude/rules/x.md` — a path no project
    has, which made every capability report **not-connected** on a machine where
    they are installed. `lstrip` takes a SET of characters; the leading dot is in
    it. A test holds the shape so it cannot come back.
    """
    from ..profile_deploy import _target_path
    return _target_path(template_rel, Path(".")).relative_to(Path(".")).as_posix()


def framework_capabilities(framework_root: Optional[str] = None) -> List[Capability]:
    """What this framework installs, read from its own deploy sources.

    Data rather than a list: the core rules come from the directory that ships
    them, and each module's files come from that module's manifest. Adding a rule
    or a module changes the report without anything here being edited — which is
    the property a hand-kept list cannot have.
    """
    from ..profile_deploy import _target_path  # the engine's own mapping, not a copy

    root = _framework_root(framework_root)
    out: List[Capability] = []

    core = root / "templates" / "core" / "rules"
    if core.is_dir():
        rels = sorted(f"rules/{p.name}" for p in core.glob("*.md"))
        targets = tuple(_relative_target(rel) for rel in rels)
        if targets:
            out.append(Capability(name="core-rules", targets=targets,
                                  source=str(core.relative_to(root))))

    for manifest in sorted((root / "modules").glob("*/*/templates/*/manifest.yaml")):
        try:
            import yaml
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001 — a broken manifest is one absent capability
            logger.warning("fleet capabilities: unreadable manifest %s: %s", manifest.name, exc)
            continue
        rels = []
        for entry in data.get("core") or []:
            rel = entry.get("path") if isinstance(entry, dict) else entry
            if isinstance(rel, str):
                rels.append(rel)
        if not rels:
            continue
        targets = tuple(_relative_target(rel) for rel in sorted(rels))
        out.append(Capability(name=manifest.parent.name, targets=targets,
                              source=str(manifest.relative_to(root))))
    logger.debug("fleet capabilities: %d capabilities declared by the framework", len(out))
    return out


def _ledger_paths(project_root: Path) -> Optional[set]:
    """Paths the install ledger covers, or None when there is no ledger."""
    from ..deploy_ledger import LEDGER_REL
    path = project_root / LEDGER_REL
    if not path.is_file():
        return None
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("fleet capabilities: unreadable install ledger: %s", exc)
        return None
    files = data.get("files")
    return set(files) if isinstance(files, dict) else set()


def report_for_project(
    project_root: str, *, capabilities: Optional[List[Capability]] = None,
) -> CapabilityReport:
    """What this project has wired in. Three states, and `unknown` is one of them."""
    root = Path(project_root)
    caps = capabilities if capabilities is not None else framework_capabilities()
    if not root.is_dir():
        # ONE reason for the whole project rather than the same sentence twelve
        # times — and every capability stays `unknown` rather than falling to
        # `not-connected`, which would invite installing into a tree we cannot see.
        return CapabilityReport(
            capabilities=[CapabilityState(name=c.name, total=len(c.targets),
                                          reason="the project directory could not be read")
                          for c in caps],
            unreadable="the project directory could not be read")

    ledger = _ledger_paths(root)
    declaration, versions = _declaration_view(root)
    out: List[CapabilityState] = []
    for cap in caps:
        present = ledgered = 0
        for rel in cap.targets:
            if (root / rel).exists():
                present += 1
                if ledger is not None and rel in ledger:
                    ledgered += 1
        if not present:
            state = NOT_CONNECTED
        elif present == len(cap.targets):
            state = CONNECTED
        else:
            state = PARTIAL
        out.append(CapabilityState(
            name=cap.name, state=state, present=present, total=len(cap.targets),
            ledgered=ledgered, inferred=present - ledgered,
            # Said for the connected case, because this is where task 2.9's
            # assumption inverts: most of what is present is present without
            # provenance, and un-ledgered must not read as stale.
            reason=None if not present or ledgered == present
            else "present without an install record — the framework cannot tell "
                 "a project edit from its own drift for these",
        ))
    logger.debug("fleet capabilities: %d checked, ledger=%s, declared=%s",
                 len(out), ledger is not None, declaration)
    return CapabilityReport(capabilities=out, ledger_present=ledger is not None,
                            declared=declaration, versions=versions)


def _declaration_view(root: Path) -> tuple:
    """What the project DECLARED, and how its versions compare. `(False, [])` if none.

    The declaration is the source where it exists, ahead of file presence — an
    earlier draft of the requirement had it the other way round, which is
    sniffing for a fact the project states outright, and cannot express a version
    mismatch at all. Measured, though: a declaration exists for **1 project in
    12**, so this is the exception and inference is the rule, which is the
    inversion task 2.9 is written around.
    """
    try:
        from ..module_install import read_install_record, read_project_declaration, version_report
        decl = read_project_declaration(root)
        if not decl.present:
            return False, []
        record = read_install_record(root)
        return True, [
            {"module": c.module, "expected": c.expected, "installed": c.installed,
             "state": getattr(c, "state", None) or getattr(c, "verdict", None)}
            for c in version_report(decl, record.modules)
        ]
    except Exception as exc:  # noqa: BLE001 — a broken declaration is one missing answer
        logger.warning("fleet capabilities: the project declaration could not be read: %s", exc)
        return False, []
