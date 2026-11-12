"""Load and validate a project's `.set/feed-watch.yaml`.

Every key that carries domain comes from here. Defaults are English and neutral; a project
whose files use other words maps them, which is how an existing layout keeps working
without a rewrite.
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DECLARATION = Path(".set") / "feed-watch.yaml"
SUPPORTED_VERSIONS = {1}


class DeclarationError(Exception):
    """The declaration is missing or invalid. The message names the file or key."""


@dataclass
class Source:
    id: str
    kind: str
    url: str
    item_filter: str = ""
    max_items_per_run: int = 30
    max_age_days: int = 2


@dataclass
class Dimension:
    key: str
    label: str
    max: int


@dataclass
class Rubric:
    marker: str
    guidance: str
    dimensions: List[Dimension]
    total_min: int
    dimension_min: Dict[str, int]

    @property
    def total_max(self) -> int:
        return sum(d.max for d in self.dimensions)


@dataclass
class Labels:
    """Header labels and section names as they appear in the project's item files."""
    link: str = "Link"
    collected: str = "Collected"
    reason: str = "Why"
    score_heading: str = "## Score"
    subject: str = "Subject"


@dataclass
class Drafts:
    template: str = ""
    suffix: str = "-reply"
    blocks: List[str] = field(default_factory=list)
    gate: str = ""


@dataclass
class Declaration:
    root: Path
    dir: Path
    sources: List[Source]
    rubric: Optional[Rubric]
    labels: Labels
    drafts: Drafts
    digest_filename: str
    item_template: str = ""

    def require_rubric(self) -> Rubric:
        if self.rubric is None:
            raise DeclarationError(f"{self.root / DECLARATION}: missing key 'rubric'")
        return self.rubric

    def digest_path(self, date: str) -> Path:
        return self.dir / self.digest_filename.replace("{date}", date)


def project_root(start: Optional[Path] = None) -> Path:
    """The git top-level of `start` (default: cwd), or `start` itself outside git."""
    start = Path(start or Path.cwd())
    try:
        out = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("git rev-parse failed in %s: %s", start, e)
    return start


def _req(d: dict, key: str, where: str):
    if key not in d or d[key] in (None, ""):
        raise DeclarationError(f"{where}: missing key '{key}'")
    return d[key]


def _int(v, where: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise DeclarationError(f"{where}: must be a non-negative integer, got {v!r}")
    return v


def load(root: Optional[Path] = None) -> Declaration:
    """Read and validate the declaration. Raises DeclarationError naming what is wrong."""
    from . import adapters  # local import: adapters do not need the declaration

    root = project_root(root)
    path = root / DECLARATION
    if not path.is_file():
        raise DeclarationError(f"{path}: not found — this project has not opted in to feed-watch")
    try:
        import yaml
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:  # yaml error or unreadable
        raise DeclarationError(f"{path}: cannot be parsed: {e}") from e
    if not isinstance(raw, dict):
        raise DeclarationError(f"{path}: top level must be a mapping")
    where = str(path)

    version = _req(raw, "version", where)
    if version not in SUPPORTED_VERSIONS:
        raise DeclarationError(f"{where}: unsupported version {version!r}")

    items_dir = root / str(_req(raw, "dir", where))

    sources = []
    for i, s in enumerate(_req(raw, "sources", where)):
        w = f"{where}: sources[{i}]"
        if not isinstance(s, dict):
            raise DeclarationError(f"{w}: must be a mapping")
        kind = str(_req(s, "kind", w))
        if kind not in adapters.ADAPTERS:
            raise DeclarationError(f"{w}: unknown source kind '{kind}' (known: {', '.join(sorted(adapters.ADAPTERS))})")
        sources.append(Source(
            id=str(_req(s, "id", w)), kind=kind, url=str(_req(s, "url", w)),
            item_filter=str(s.get("item_filter") or ""),
            max_items_per_run=_int(s.get("max_items_per_run", 30), f"{w}.max_items_per_run"),
            max_age_days=_int(s.get("max_age_days", 2), f"{w}.max_age_days"),
        ))
    if not sources:
        raise DeclarationError(f"{where}: missing key 'sources'")

    rubric = None
    if raw.get("rubric") is not None:
        r = raw["rubric"]
        w = f"{where}: rubric"
        dims = []
        for j, d in enumerate(_req(r, "dimensions", w)):
            wd = f"{w}.dimensions[{j}]"
            key = str(_req(d, "key", wd))
            if not re.fullmatch(r"\w+", key):
                raise DeclarationError(f"{wd}: key must be a word, got {key!r}")
            dims.append(Dimension(key=key, label=str(d.get("label") or key), max=_int(_req(d, "max", wd), f"{wd}.max")))
        keys = {d.key for d in dims}
        th = _req(r, "threshold", w)
        dmin = {str(k): _int(v, f"{w}.threshold.dimension_min.{k}") for k, v in (th.get("dimension_min") or {}).items()}
        unknown = set(dmin) - keys
        if unknown:
            raise DeclarationError(f"{w}.threshold.dimension_min: unknown dimension(s) {sorted(unknown)}")
        marker = str(r.get("marker") or "feed-watch")
        if not re.fullmatch(r"[\w-]+", marker):
            raise DeclarationError(f"{w}.marker: must be letters, digits, '-' or '_', got {marker!r}")
        rubric = Rubric(marker=marker, guidance=str(_req(r, "guidance", w)), dimensions=dims,
                        total_min=_int(_req(th, "total_min", f"{w}.threshold"), f"{w}.threshold.total_min"),
                        dimension_min=dmin)

    lab = raw.get("labels") or {}
    labels = Labels(**{k: str(v) for k, v in lab.items() if k in Labels.__dataclass_fields__})
    unknown_labels = set(lab) - set(Labels.__dataclass_fields__)
    if unknown_labels:
        raise DeclarationError(f"{where}: labels: unknown key(s) {sorted(unknown_labels)}")

    dr = raw.get("drafts") or {}
    drafts = Drafts(template=str(dr.get("template") or ""), suffix=str(dr.get("suffix") or "-reply"),
                    blocks=[str(b) for b in (dr.get("blocks") or [])], gate=str(dr.get("gate") or ""))

    dg = raw.get("digest") or {}
    digest_filename = str(dg.get("filename") or "{date}-digest.md")
    if "{date}" not in digest_filename:
        raise DeclarationError(f"{where}: digest.filename must contain '{{date}}'")

    decl = Declaration(root=root, dir=items_dir, sources=sources, rubric=rubric, labels=labels,
                       drafts=drafts, digest_filename=digest_filename,
                       item_template=str(raw.get("item_template") or ""))
    logger.debug("feed-watch declaration loaded: %d source(s), rubric=%s", len(sources), rubric is not None)
    return decl
