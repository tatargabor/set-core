"""Project configuration for the knowledge-base engine.

One file per project, owned by the project: `set/knowledge/kb.json`.
`set/knowledge/` is project-owned and never touched by a framework deploy,
so the project's search vocabulary lives where the project can edit it.

THREE LAYERS, merged in this order:

    built-in defaults  ←  ~/.config/set-core/kb.json (machine, optional)
                       ←  <project>/set/knowledge/kb.json (project)

Nested objects merge field by field. Arrays REPLACE — with one deliberate
exception: `exclude` is ADDITIVE at every layer (design D4). One project
pattern added to `exclude` must never silently re-admit the agent-log trees
the defaults hold out; opting out of a default is always an explicit act.

THE EXPLICIT ACTS are `"excludeDefaults": false` (lifts every default) and
`"keepDefault": [<group name>]` (lifts exactly the named default groups —
the names are the keys of `DEFAULT_EXCLUSION_GROUPS`, and an unknown name is
a config error, not a silent no-op).

`_`-PREFIXED KEYS ARE DOCUMENTATION. They are dropped on load, at every
level, so a config can keep its reasoning next to its values.

VALIDATION IS LOUD. An unknown language, a channel rule without roots, a
scope pattern without `{scope}`, a non-string pattern — every one fails
loading with the offending key path (`config.channels[0].roots …`). A config
error is never a silent fallback to defaults: the wrong corpus searched
confidently is worse than no search at all.

LEGACY LOCATION. A project migrating from the originating engine still has
its config at `<project>/kb.config.json`; when the project file is absent
the loader reads the legacy file and warns once, naming the new path — the
migration is a two-step change, not a flag day.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import set_kb.lang_hu  # noqa: F401 — registers the "hu" pack, so `language: "hu"` resolves
from set_kb.channels import ChannelRule
from set_kb.indexer import IndexOptions
from set_kb.lang import language_pack, registered_languages
from set_kb.scopes import ScopeRule, check_pattern
from set_kb.search import SearchOpts

logger = logging.getLogger(__name__)

# The project-owned location, relative to the project root.
CONFIG_REL = os.path.join("set", "knowledge", "kb.json")
# The originating engine's location — read with a warning when the project
# file is absent.
LEGACY_REL = "kb.config.json"
# The machine-level layer, under the user's home.
MACHINE_REL = os.path.join(".config", "set-core", "kb.json")

# The deploy ledger (design D5): unmodified framework-deployed files are not
# project knowledge and are not indexed; a project that edited one owns it.
FRAMEWORK_LEDGER_REL = os.path.join("set", ".deploy-manifest.json")


class ConfigError(ValueError):
    """An invalid configuration. The message carries the offending key path —
    a config error is always loud, never a silent fallback."""


# ── the default corpus (design D5) ──────────────────────────────────────────
#
# With no configuration the corpus is every `.md` file under the repository
# root, minus these tree groups. Each group is NAMED so a project can lift
# exactly one on purpose (`keepDefault`) and the doctor can report the share
# a rule removes. `.git/` and `.set/` are NOT here: they are plumbing, pruned
# by the indexer permanently, and no configuration key can lift them.
DEFAULT_EXCLUSION_GROUPS: list = [
    ("dependencies", ["node_modules/"]),
    ("worktrees", ["**/worktrees/"]),
    (
        "build-output",
        ["dist/", "build/", "out/", "coverage/", ".next*/", ".nuxt/", ".turbo/", ".cache/", "test-results/", "playwright-report/"],
    ),
    ("virtualenvs-and-caches", [".venv*/", "venv/", ".pytest_cache/", ".mypy_cache/", "__pycache__/"]),
    ("vendored-trees", ["vendor/", "3rdparty/", "third_party/"]),
    ("agent-logs", ["**/claude-sessions/", "**/tool-calls/"]),
]
DEFAULT_GROUP_NAMES = [name for name, _patterns in DEFAULT_EXCLUSION_GROUPS]

DEFAULT_EXTENSIONS = [".md"]

# A readable transcript's frontmatter type wins over any folder name: the
# dump of an agent session is kept out wherever it is saved, and the readable
# transcript beside it stays in.
DEFAULT_EXCLUDE_FRONTMATTER = {"type": ["*-session-claude-code", "claude-session"]}

# Built-in defaults, in one place so the merge has an honest base.
DEFAULTS: dict = {
    "language": "en",
    "sources": [{"ref": ""}],  # the whole repository, one root
    "exclude": [],
    "excludeDefaults": True,
    "keepDefault": [],
    "extensions": list(DEFAULT_EXTENSIONS),
    "excludeFrontmatter": {k: list(v) for k, v in DEFAULT_EXCLUDE_FRONTMATTER.items()},
    "includeFrameworkFiles": False,
    "channels": [],
    "scopes": [],
    "ranking": {
        "fieldWeights": {"headingPath": 10, "heading": 3, "body": 1},
        "proximityBoost": False,
        "diversity": {"enabled": False, "lambda": 0.7},
        "sourceDedup": True,
        "laneChannels": [],
        # The lane quota is a per-project measurement (design D8), never a
        # copied default — and with no laneChannels the lane never engages.
        "laneQuota": 0.0,
        "laneLeadMargin": 0.0,
        "coverageRerank": False,
    },
    "findability": {"globs": []},
}


@dataclass
class SourceConfig:
    """One indexed root: a directory under the project root, plus the priority
    that decides the exact-content dedup winner. `about` is the project's own
    one-line description, shown by `set-kb sources` (design D3) — display-only,
    like a channel's `about`, and out of the corpus-config hash."""

    ref: str
    priority: int = 0
    about: Optional[str] = None


@dataclass
class KbConfig:
    """A loaded, validated configuration — what the engine actually acts on."""

    sources: list
    channels: list
    scopes: list
    exclude: list  # the project's OWN additive patterns
    exclude_defaults: bool = True
    keep_default: list = field(default_factory=list)  # default groups LIFTED on purpose
    extensions: list = field(default_factory=lambda: list(DEFAULT_EXTENSIONS))
    exclude_frontmatter: dict = field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_EXCLUDE_FRONTMATTER.items()})
    include_framework_files: bool = False
    language: str = "en"
    ranking: dict = field(default_factory=dict)
    findability_globs: list = field(default_factory=list)
    legacy: bool = False  # loaded from the legacy location

    def effective_exclude(self) -> list:
        """Every exclusion pattern in force, in order: the default groups
        (minus those lifted) plus the project's own patterns."""
        pats: list = []
        if self.exclude_defaults:
            lifted = set(self.keep_default)
            for name, patterns in DEFAULT_EXCLUSION_GROUPS:
                if name not in lifted:
                    pats.extend(patterns)
        for p in self.exclude:
            if p not in pats:
                pats.append(p)
        return pats


# ── loading ──────────────────────────────────────────────────────────────────


def _read_json(path: Path, layer: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as e:
        raise ConfigError(f"kb config ({layer}, {path}): not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"kb config ({layer}, {path}): the top level must be a JSON object")
    return data


def _strip_docs(obj, path: str = "config"):
    """Drop every `_`-prefixed key, recursively — they are documentation
    (AC: a config with `_why` next to `exclude` applies the exclusions and
    `_why` has no effect)."""
    if isinstance(obj, dict):
        return {k: _strip_docs(v, f"{path}.{k}") for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    return obj


def _merge(base: dict, over: dict) -> dict:
    """Layer merge: nested objects merge field by field, arrays replace —
    except `exclude`, which is ADDITIVE (design D4)."""
    out = dict(base)
    for k, v in over.items():
        if k == "exclude" and isinstance(v, list) and isinstance(out.get(k), list):
            merged = list(out[k])
            merged.extend(p for p in v if p not in merged)
            out[k] = merged
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(project_root, machine_path=None) -> KbConfig:
    """Load and validate the configuration for one project.

    `machine_path` overrides the machine layer's location (tests use this;
    the default is `~/.config/set-core/kb.json`). Raises `ConfigError` on any
    invalid value, with the offending key path.
    """
    root = Path(project_root)
    merged = dict(DEFAULTS)

    machine = Path(machine_path) if machine_path is not None else Path.home() / MACHINE_REL
    layers = []
    if machine.is_file():
        layers.append(("machine", _read_json(machine, "machine")))
        merged = _merge(merged, _strip_docs(layers[-1][1]))

    project_file = root / CONFIG_REL
    legacy = False
    if project_file.is_file():
        layers.append(("project", _read_json(project_file, CONFIG_REL)))
    elif (root / LEGACY_REL).is_file():
        layers.append(("project", _read_json(root / LEGACY_REL, LEGACY_REL)))
        legacy = True
        # The warning IS the migration path: it names the new location, once
        # per run, so the move can happen when the project is ready.
        logger.warning("kb config: reading the legacy %s — move it to %s", LEGACY_REL, CONFIG_REL)
    if layers:
        merged = _merge(merged, _strip_docs(layers[-1][1]))

    cfg = _validate(merged)
    cfg.legacy = legacy
    return cfg


# ── validation ───────────────────────────────────────────────────────────────
#
# Every check names its key path. The point is not politeness: a config value
# that fails silently falls back to a default the project never chose, and the
# wrong corpus searched confidently is worse than no search.


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _req_list(v, path: str) -> list:
    if not isinstance(v, list):
        raise ConfigError(f"{path}: expected a list, got {type(v).__name__}")
    return v


def _req_str_list(v, path: str) -> list:
    for i, p in enumerate(_req_list(v, path)):
        if not isinstance(p, str):
            raise ConfigError(f"{path}[{i}]: expected a string pattern, got {type(p).__name__}")
    return v


def _validate(d: dict) -> KbConfig:
    for k in sorted(set(d) - set(DEFAULTS)):
        logger.warning("kb config: unknown key %s.%s ignored", "config", k)

    cfg = KbConfig(sources=[], channels=[], scopes=[], exclude=[])

    # language — an unknown pack is an error NAMING the key and the available
    # packs (AC: unknown language), because English stopwords over another
    # language's corpus silently wreck the ranking instead of erroring.
    lang = d["language"]
    if not isinstance(lang, str):
        raise ConfigError(f"config.language: expected a string, got {type(lang).__name__}")
    try:
        language_pack(lang)
    except KeyError:
        raise ConfigError(
            f"config.language: unknown language {lang!r} (available packs: {', '.join(registered_languages())})"
        ) from None
    cfg.language = lang

    # sources
    for i, s in enumerate(_req_list(d["sources"], "config.sources")):
        if not isinstance(s, dict):
            raise ConfigError(f"config.sources[{i}]: expected an object with a 'ref' key")
        ref = s.get("ref")
        if not isinstance(ref, str):
            raise ConfigError(f"config.sources[{i}].ref: expected a string path, got {type(ref).__name__}")
        prio = s.get("priority", 0)
        if not _is_num(prio):
            raise ConfigError(f"config.sources[{i}].priority: expected a number, got {type(prio).__name__}")
        about = s.get("about")
        if about is not None and not isinstance(about, str):
            raise ConfigError(f"config.sources[{i}].about: expected a string, got {type(about).__name__}")
        cfg.sources.append(SourceConfig(ref=ref, priority=int(prio), about=about))
    if not cfg.sources:
        raise ConfigError("config.sources: at least one source root is required")

    # exclude — every pattern a string (a non-string pattern is a config error
    # with the key path, design D4)
    cfg.exclude = list(_req_str_list(d["exclude"], "config.exclude"))

    # excludeDefaults / keepDefault
    if not isinstance(d["excludeDefaults"], bool):
        raise ConfigError(f"config.excludeDefaults: expected a boolean, got {type(d['excludeDefaults']).__name__}")
    cfg.exclude_defaults = d["excludeDefaults"]
    for i, name in enumerate(_req_str_list(d["keepDefault"], "config.keepDefault")):
        if name not in DEFAULT_GROUP_NAMES:
            raise ConfigError(
                f"config.keepDefault[{i}]: unknown default group {name!r} "
                f"(default groups: {', '.join(DEFAULT_GROUP_NAMES)})"
            )
    cfg.keep_default = list(d["keepDefault"])

    # extensions
    exts = _req_str_list(d["extensions"], "config.extensions")
    if not exts:
        raise ConfigError("config.extensions: at least one extension is required")
    cfg.extensions = list(exts)

    # excludeFrontmatter — {frontmatter key: [glob patterns on the value]}
    fm = d["excludeFrontmatter"]
    if not isinstance(fm, dict):
        raise ConfigError(f"config.excludeFrontmatter: expected an object, got {type(fm).__name__}")
    for k, v in fm.items():
        values = [v] if isinstance(v, str) else v
        _req_str_list(values, f"config.excludeFrontmatter.{k}")
        cfg.exclude_frontmatter[k] = list(values)

    # includeFrameworkFiles
    if not isinstance(d["includeFrameworkFiles"], bool):
        raise ConfigError(f"config.includeFrameworkFiles: expected a boolean, got {type(d['includeFrameworkFiles']).__name__}")
    cfg.include_framework_files = d["includeFrameworkFiles"]

    # channels — a rule without roots is THE measured misclassification
    # (a bare path pattern classified a ticket ABOUT a client report as the
    # client's voice), so it is rejected here, naming the rule.
    for i, r in enumerate(_req_list(d["channels"], "config.channels")):
        if not isinstance(r, dict):
            raise ConfigError(f"config.channels[{i}]: expected an object with 'channel' and 'roots'")
        name = r.get("channel")
        if not isinstance(name, str):
            raise ConfigError(f"config.channels[{i}].channel: expected a string, got {type(name).__name__}")
        roots = r.get("roots")
        if not isinstance(roots, list) or not roots or not all(isinstance(x, str) for x in roots):
            raise ConfigError(
                f"config.channels[{i}] (rule {name!r}).roots: a channel rule must name at least one root — "
                f"a path pattern alone would classify matching files under EVERY root"
            )
        for key in ("include", "exclude"):
            if r.get(key) is not None:
                _req_str_list(r[key], f"config.channels[{i}].{key}")
        about = r.get("about")
        if about is not None and not isinstance(about, str):
            raise ConfigError(f"config.channels[{i}] (rule {name!r}).about: expected a string, got {type(about).__name__}")
        cfg.channels.append(
            ChannelRule(
                channel=name,
                roots=list(roots),
                include=list(r["include"]) if r.get("include") else None,
                exclude=list(r["exclude"]) if r.get("exclude") else None,
                about=about,
            )
        )

    # scopes — a pattern without `{scope}` captures nothing, silently, so it
    # is rejected here, naming the pattern (AC: pattern without placeholder).
    for i, s in enumerate(_req_list(d["scopes"], "config.scopes")):
        if not isinstance(s, dict):
            raise ConfigError(f"config.scopes[{i}]: expected an object with 'name' and 'pattern'")
        name = s.get("name")
        if not isinstance(name, str):
            raise ConfigError(f"config.scopes[{i}].name: expected a string, got {type(name).__name__}")
        pattern = s.get("pattern")
        try:
            check_pattern(pattern)
        except ValueError as e:
            raise ConfigError(f"config.scopes[{i}] (scope {name!r}).pattern: {e}") from e
        cfg.scopes.append(ScopeRule(name=name, pattern=pattern))

    # ranking
    r = d["ranking"]
    if not isinstance(r, dict):
        raise ConfigError(f"config.ranking: expected an object, got {type(r).__name__}")
    fw = r.get("fieldWeights", {})
    if not isinstance(fw, dict):
        raise ConfigError(f"config.ranking.fieldWeights: expected an object, got {type(fw).__name__}")
    for k, v in fw.items():
        if not _is_num(v):
            raise ConfigError(f"config.ranking.fieldWeights.{k}: expected a number, got {type(v).__name__}")
    for k in ("proximityBoost", "sourceDedup", "coverageRerank"):
        if not isinstance(r.get(k, DEFAULTS["ranking"][k]), bool):
            raise ConfigError(f"config.ranking.{k}: expected a boolean")
    div = r.get("diversity", {})
    if not isinstance(div, dict):
        raise ConfigError(f"config.ranking.diversity: expected an object, got {type(div).__name__}")
    if not isinstance(div.get("enabled", False), bool):
        raise ConfigError("config.ranking.diversity.enabled: expected a boolean")
    if not _is_num(div.get("lambda", 0.7)):
        raise ConfigError("config.ranking.diversity.lambda: expected a number")
    lane = _req_str_list(r.get("laneChannels", []), "config.ranking.laneChannels")
    for k, lo, hi in (("laneQuota", 0.0, 1.0), ("laneLeadMargin", 0.0, 1.0)):
        v = r.get(k, DEFAULTS["ranking"][k])
        if not _is_num(v) or not (lo <= float(v) <= hi):
            raise ConfigError(f"config.ranking.{k}: expected a number in [{lo}, {hi}], got {v!r}")
    cfg.ranking = {
        "fieldWeights": dict(fw) or None,
        "proximityBoost": r.get("proximityBoost", False),
        "diversity": {"enabled": div.get("enabled", False), "lambda": div.get("lambda", 0.7)},
        "sourceDedup": r.get("sourceDedup", True),
        "laneChannels": list(lane),
        "laneQuota": float(r.get("laneQuota", 0.0)),
        "laneLeadMargin": float(r.get("laneLeadMargin", 0.0)),
        "coverageRerank": r.get("coverageRerank", False),
    }

    # findability (checked by `set-kb findability`, wave W3 — validated here
    # so a typo surfaces at load, not at the first check)
    f = d["findability"]
    if not isinstance(f, dict):
        raise ConfigError(f"config.findability: expected an object, got {type(f).__name__}")
    cfg.findability_globs = list(_req_str_list(f.get("globs", []), "config.findability.globs"))

    return cfg


# ── the factories the engine runs on ─────────────────────────────────────────


def read_framework_ledger(project_root) -> Optional[dict]:
    """The deploy ledger's `files` map ({project-relative path: sha256}), or
    None when there is no usable ledger. A project WITHOUT a ledger indexes
    every file like any other — the framework-noise cost is visible through
    doctor, never through a silent wrong corpus. An UNREADABLE ledger degrades
    the same way, loudly logged: a half-written ledger must not decide what is
    project knowledge."""
    path = Path(project_root) / FRAMEWORK_LEDGER_REL
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        files = data.get("files")
        if not isinstance(files, dict):
            raise ValueError("'files' is not an object")
        return {str(k): str(v) for k, v in files.items()}
    except (OSError, ValueError) as e:
        logger.warning("kb config: unreadable framework ledger at %s (%s) — indexing everything", path, e)
        return None


def index_options(cfg: KbConfig, framework_ledger: Optional[dict] = None) -> IndexOptions:
    """The IndexOptions one refresh runs with. `framework_ledger` is the
    loaded deploy ledger; `includeFrameworkFiles: true` simply passes None."""
    return IndexOptions(
        exclude=cfg.effective_exclude(),
        extensions=list(cfg.extensions),
        channels=list(cfg.channels),
        scopes=list(cfg.scopes),
        exclude_frontmatter=cfg.exclude_frontmatter or None,
        framework_ledger=None if cfg.include_framework_files else framework_ledger,
    )


def search_options(cfg: KbConfig, **overrides) -> SearchOpts:
    """The SearchOpts one search runs with — ranking comes from the config,
    per-call overrides (limit, root, scope, …) win."""
    r = cfg.ranking
    base = dict(
        field_weights=r["fieldWeights"],
        proximity_boost=r["proximityBoost"],
        diversity=r["diversity"],
        source_dedup=r["sourceDedup"],
        lane_quota=r["laneQuota"],
        lane_lead_margin=r["laneLeadMargin"],
        lane_channels=r["laneChannels"],
        coverage_rerank=r["coverageRerank"],
        language=language_pack(cfg.language),
        root_priority={s.ref: s.priority for s in cfg.sources},
        expand_parent=True,
    )
    base.update(overrides)
    return SearchOpts(**base)


def corpus_config_hash(cfg: KbConfig) -> str:
    """sha256 over everything that decides WHAT is indexed and HOW rows are
    classified. A change here forces a full re-chunk on the next refresh —
    without it, unchanged files would keep stale channel/scope labels (and
    stale exclusion decisions) forever. Language and ranking are DELIBERATELY
    out: they change how a query is ranked, never what a row says."""
    payload = {
        "sources": [s.ref for s in cfg.sources],
        "exclude": cfg.effective_exclude(),
        "extensions": list(cfg.extensions),
        "excludeFrontmatter": cfg.exclude_frontmatter,
        "includeFrameworkFiles": cfg.include_framework_files,
        "channels": [
            {"channel": c.channel, "roots": list(c.roots), "include": list(c.include) if c.include else None, "exclude": list(c.exclude) if c.exclude else None}
            for c in cfg.channels
        ],
        "scopes": [{"name": s.name, "pattern": s.pattern} for s in cfg.scopes],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def footer_exclusions(cfg: KbConfig) -> list:
    """The exclusion lines the result page footer shows — what was NOT
    searched. The active list is shown as it IS: a default lifted with
    `keepDefault` is absent from the pattern list, and the lift itself is
    stated, so the page never reads as an accident."""
    lines: list = []
    active = cfg.effective_exclude()
    if active:
        lines.append("indexed corpus excludes: " + ", ".join(active))
    if not cfg.exclude_defaults:
        lines.append("default exclusions are OFF (excludeDefaults: false)")
    if cfg.keep_default:
        lines.append("default exclusion groups lifted on purpose: " + ", ".join(cfg.keep_default))
    fm = ", ".join(f"{k} ~ [{', '.join(v)}]" for k, v in cfg.exclude_frontmatter.items())
    if fm:
        lines.append(f"agent-session dumps excluded by frontmatter: {fm}")
    if not cfg.include_framework_files:
        lines.append(f"unmodified framework-deployed files excluded (ledger: {FRAMEWORK_LEDGER_REL})")
    return lines
