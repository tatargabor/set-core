"""Differential test against the recorded reference-engine oracle.

The kb-search oracle lives in ``tests/fixtures/kb/expected/``: result pages
recorded from the reference TypeScript engine (see that directory's README for
the pinned commit). This module runs the Python engine over a temp copy of the
committed fixture corpus with the SAME configuration and requires, for every
fixture query, the same hits in the same order — the requirement
`the-shared-engine-matches-the-reference-engine-on-a-synthetic-corpus`.

Scores are compared with a float tolerance (same SQLite, so they are expected
to be bit-identical; the tolerance keeps the test about ORDER and MEMBERSHIP,
not about float formatting). Everything else compares exactly: paths,
heading paths, chunk ids, channels, snippets, dedup counts, aka paths, parent
links, totals, exclusions.

Ranking drift (AC: WHEN an engine change alters a fixture order THEN the
differential test fails naming the query) fails with the query id in the
assertion message.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from set_kb.channels import ChannelRule
from set_kb.indexer import AtomicIndexSource, IndexOptions, RunIndexAtomicOpts, run_index_atomic
from set_kb.lang import language_pack
from set_kb.lang_hu import hungarian_pack  # noqa: F401 — registers the "hu" pack
from set_kb.search import SearchOpts, search_page
from set_kb.store import SqliteFtsStore

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "kb"

# CLI flag → SearchOpts field, for the args recorded in queries.json. A flag
# that arrives in the fixture without a mapping here is a test error, not a
# silent ignore.
LIMIT_FLAGS = {"--limit"}


def build_engine(tmp_path: Path):
    """Copy the fixture to `tmp_path`, index it once, return (store, base SearchOpts kwargs)."""
    for name in ("corpus", "kb.config.json"):
        src = FIXTURE / name
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, tmp_path / name)
    cfg = json.loads((FIXTURE / "kb.config.json").read_text(encoding="utf-8"))
    sources = [AtomicIndexSource(id=s["ref"], dir=str(tmp_path / s["ref"])) for s in cfg["sources"]]
    index_opts = IndexOptions(
        exclude=cfg["exclude"],
        extensions=cfg["extensions"],
        channels=[ChannelRule(**c) for c in cfg["channels"]],
    )
    run_index_atomic(RunIndexAtomicOpts(db_path=str(tmp_path / cfg["dbPath"]), sources=sources, index_opts=index_opts))
    store = SqliteFtsStore(str(tmp_path / cfg["dbPath"]))
    store.init()
    ranking = cfg["ranking"]
    base = dict(
        field_weights=ranking["fieldWeights"],
        proximity_boost=ranking["proximityBoost"],
        diversity=ranking["diversity"],
        source_dedup=ranking["sourceDedup"],
        lane_quota=ranking["laneQuota"],
        lane_lead_margin=ranking["laneLeadMargin"],
        lane_channels=ranking["laneChannels"],
        language=language_pack(cfg["language"]),
        root_priority={s["ref"]: s["priority"] for s in cfg["sources"]},
        expand_parent=True,
    )
    exclusions = [f"indexed corpus excludes: {', '.join(cfg['exclude'])}"]
    return store, base, exclusions


def apply_args(kwargs: dict, args: list) -> None:
    """Map one fixture query's recorded CLI args onto SearchOpts kwargs."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--no-lane-quota":
            kwargs["lane_quota"] = 0
        elif a == "--limit":
            kwargs["limit"] = int(args[i + 1])
            i += 1
        elif a == "--root":
            kwargs["root"] = args[i + 1]
            i += 1
        elif a == "--exclude-path":
            kwargs.setdefault("exclude_paths", []).append(args[i + 1])
            i += 1
        else:
            raise AssertionError(f"fixture arg {a!r} has no SearchOpts mapping — extend apply_args")
        i += 1


def exclusions_with(base: list, args: list) -> list:
    out = list(base)
    i = 0
    while i < len(args):
        if args[i] == "--exclude-path":
            out.append(f"working directory excluded from this search: {args[i + 1]}")
            i += 1
        else:
            i += 1
    return out


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kb-oracle")
    store, base, exclusions = build_engine(tmp)
    yield store, base, exclusions
    store.close()


QUERIES = json.loads((FIXTURE / "queries.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("spec", QUERIES, ids=lambda s: s["id"])
def test_page_matches_recorded_oracle(engine, spec):
    store, base, exclusions = engine
    kwargs = dict(base)
    apply_args(kwargs, spec["args"])
    page = search_page(store, spec["q"], SearchOpts(**kwargs), exclusions_with(exclusions, spec["args"]))
    actual = page.to_json_dict()
    actual["query"] = spec["q"]
    actual["limit"] = kwargs.get("limit", 10)

    expected = json.loads((FIXTURE / "expected" / f"{spec['id']}.json").read_text(encoding="utf-8"))
    assert actual["query"] == expected["query"]
    assert actual["limit"] == expected["limit"]
    assert actual["total"] == expected["total"], spec["id"]
    assert actual["hasMore"] == expected["hasMore"], spec["id"]
    assert actual["exclusions"] == exclusions_with(exclusions, spec["args"]), spec["id"]

    hits, wanted = actual["hits"], expected["hits"]
    assert len(hits) == len(wanted), f"{spec['id']}: hit count differs"
    for i, (a, e) in enumerate(zip(hits, wanted)):
        ctx = f"{spec['id']} hit[{i}]"
        for key in ("root", "path", "headingPath", "chunkId", "docType", "channel", "snippet"):
            assert a[key] == e[key], f"{ctx}: {key} differs — page order or content drifted"
        assert a["score"] == pytest.approx(e["score"], abs=1e-9), f"{ctx}: score differs"
        assert a["suppressedSections"] == e["suppressedSections"], ctx
        assert a.get("akaPaths") == e.get("akaPaths"), ctx
        assert a.get("parent") == e.get("parent"), ctx


def test_oracle_covers_every_recorded_page(engine):
    """The committed pages and the query list cannot drift apart silently."""
    recorded = {p.stem for p in (FIXTURE / "expected").glob("*.json")}
    assert recorded == {s["id"] for s in QUERIES}
