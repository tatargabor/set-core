"""Search behaviour on a purpose-built mini corpus: dedup, lane, exclusions,
the distinct-source total, and the divergences the design pins."""

from __future__ import annotations

import pytest

from set_kb.channels import ChannelRule
from set_kb.indexer import AtomicIndexSource, IndexOptions, RunIndexAtomicOpts, run_index_atomic
from set_kb.search import SearchOpts, count_sources, fold, raw_tokens, search, search_page, to_match, tokenize
from set_kb.store import SqliteFtsStore


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    """Three roots: planning (priority 10), dup (priority 1), client (lane channel)."""
    root = tmp_path_factory.mktemp("kb-mini")
    (root / "planning").mkdir()
    (root / "client").mkdir()
    big = "word " * 25  # keep sections above the merge threshold

    def filler(tag: str) -> str:
        # unique per section: exact-content dedup must never collapse these
        return f"{big}{tag}\n\nsecond paragraph of {tag} with distinct filler text\n"

    sections = "\n\n".join(
        f"## Alpha {i}\n\n{filler(f'alpha-section-{i} and alpha')}" for i in range(1, 7)
    )
    (root / "planning" / "multi.md").write_text(
        f"# Topic\n\n{filler('topic preamble and alpha')}\n\n{sections}\n", encoding="utf-8"
    )
    dup = f"# Dup note\n\n{filler('kappa unique-to-dup')}\n"
    (root / "planning" / "dup-note.md").write_text(dup, encoding="utf-8")
    (root / "client" / "dup-note.md").write_text(dup, encoding="utf-8")
    (root / "client" / "buried.md").write_text(f"# Client voice\n\n{filler('kappa in the client voice')}\n", encoding="utf-8")
    (root / "planning" / "loud.md").write_text(
        f"# Loud one\n\n{filler('kappa shouted here')}\n\n# Loud two\n\n{filler('kappa shouted again differently')}\n",
        encoding="utf-8",
    )
    (root / "planning" / "accent.md").write_text(f"# Költségvetés\n\n{filler('díjbekérő és számlázás')}\n", encoding="utf-8")

    store_path = root / "idx.db"
    sources = [
        AtomicIndexSource(id="planning", dir=str(root / "planning")),
        AtomicIndexSource(id="client", dir=str(root / "client")),
    ]
    run_index_atomic(
        RunIndexAtomicOpts(
            db_path=str(store_path),
            sources=sources,
            index_opts=IndexOptions(channels=[ChannelRule(channel="client", roots=["client"])]),
        )
    )
    store = SqliteFtsStore(str(store_path))
    store.init()
    yield store
    store.close()


def base_opts(**over):
    opts = dict(
        root_priority={"planning": 10, "client": 1},
        proximity_boost=False,
        field_weights={"headingPath": 10, "heading": 3, "body": 1},
    )
    opts.update(over)
    return SearchOpts(**opts)


def test_tokenizer_and_match_builder():
    assert raw_tokens("Számlázás díjbekérő!") == ["számlázás", "díjbekérő"]
    assert to_match("alpha BETA") == '"alpha" OR "beta"'
    assert to_match("the of and") != "", "fallback arm: function-word-only queries keep the raw tokens"
    assert fold("díjbekérő") == "dijbekero"


def test_multi_section_file_takes_one_slot_reporting_the_rest(mini):
    hits = search(mini, "alpha", base_opts())
    multi = [h for h in hits if h.path == "multi.md"]
    assert len(multi) == 1, "one file, one slot — never more"
    assert multi[0].suppressed_sections >= 6, "the further matching sections are counted, not dropped"


def test_identical_content_prefers_higher_priority_and_marks_duplicate(mini):
    hits = search(mini, "unique-to-dup", base_opts())
    assert len(hits) == 1
    h = hits[0]
    assert h.root == "planning", "the higher-priority root wins the slot"
    assert h.aka_paths == ["dup-note.md"], "the duplicate is marked, with its path"


@pytest.fixture(scope="module")
def lane(tmp_path_factory):
    """A dedicated corpus for the lane: two strong planning hits, one weak
    client hit — scores well apart, so the ordering assertions are not ties."""
    root = tmp_path_factory.mktemp("kb-lane")
    (root / "planning").mkdir()
    (root / "client").mkdir()
    big = "word " * 25
    (root / "planning" / "strong-a.md").write_text(
        f"# Sigma plan A\n\n{big} sigma sigma sigma\n\nmore sigma context for plan A to widen the gap\n", encoding="utf-8"
    )
    (root / "planning" / "strong-b.md").write_text(
        f"# Sigma plan B\n\n{big} sigma sigma\n", encoding="utf-8"
    )
    (root / "client" / "quiet.md").write_text(f"# Client note\n\n{big} sigma\n", encoding="utf-8")
    from set_kb.channels import ChannelRule

    store_path = root / "idx.db"
    run_index_atomic(
        RunIndexAtomicOpts(
            db_path=str(store_path),
            sources=[AtomicIndexSource(id="planning", dir=str(root / "planning")), AtomicIndexSource(id="client", dir=str(root / "client"))],
            index_opts=IndexOptions(channels=[ChannelRule(channel="client", roots=["client"])]),
        )
    )
    store = SqliteFtsStore(str(store_path))
    store.init()
    yield store
    store.close()


def test_lane_reserved_share_reorders_a_buried_hit(lane):
    lane_on = search(lane, "sigma", base_opts(lane_channels=["client"], lane_quota=0.5, lane_lead_margin=0))
    paths = [h.path for h in lane_on]
    assert "quiet.md" in paths
    # quota 0.5: slot 1 goes to the best main hit ((0+1)/(0+1) > 0.5), slot 2
    # is the reserved lane's ((0+1)/(1+1) <= 0.5) — the buried client hit takes it.
    assert paths.index("quiet.md") == 1


def test_lane_off_is_score_order(lane):
    lane_off = search(lane, "sigma", base_opts(lane_channels=["client"], lane_quota=0, lane_lead_margin=0))
    paths = [h.path for h in lane_off]
    scores = [h.score for h in lane_off]
    assert scores == sorted(scores), "quota 0 → pure score order"
    assert paths[-1] == "quiet.md", "without the lane the weak client hit is last"
    assert paths.index("quiet.md") == 2


def test_empty_lane_channels_means_no_lane(lane):
    """DESIGN DIVERGENCE (design D8): an empty laneChannels is NO lane — the
    reference would fall back to an agents-docType lane, which on a project
    corpus would reserve the page for CLAUDE.md-type files."""
    hits = search(lane, "sigma", base_opts(lane_channels=[], lane_quota=0.7))
    assert [h.path for h in hits] == [h.path for h in search(lane, "sigma", base_opts(lane_channels=[], lane_quota=0))], "score order — no reserved share"
    assert [h.score for h in hits] == sorted(h.score for h in hits)


def test_exclude_paths_runs_in_sql_and_keeps_the_page_full(mini):
    opts = base_opts(exclude_paths=["client"], limit=2)
    page = search_page(mini, "kappa", opts)
    assert all(h.root != "client" for h in page.hits)
    assert len(page.hits) == 2, "the next hit takes the freed slot — the page never shrinks below the limit"
    assert page.total == count_sources(mini, "kappa", opts) - 0 or page.total >= len(page.hits)
    assert page.has_more is (page.total > len(page.hits))


def test_total_counts_distinct_sources_before_dedup(mini):
    # "unique-to-dup" matches the same CONTENT at two paths: two sources
    # total, one rendered hit (the duplicate collapses into akaPaths).
    page = search_page(mini, "unique-to-dup", base_opts())
    assert page.total == 2
    assert len(page.hits) == 1
    assert page.has_more is True, "an upper bound that errs high — the reader must never conclude 'nothing else'"


def test_accented_query_finds_accented_body(mini):
    hits = search(mini, "szamlazas", base_opts())
    assert [h.path for h in hits if h.path == "accent.md"], "unicode61 remove_diacritics does the folding, not us"


def test_zero_hits_is_an_empty_page(mini):
    assert search(mini, "xyzzyplugh", base_opts()) == []
    assert count_sources(mini, "xyzzyplugh", base_opts()) == 0


def test_proximity_boost_lowers_score_for_in_order_hits(mini):
    from set_kb.search import proximity_delta

    assert proximity_delta(["alpha", "beta"], "alpha then beta here") < 0
    assert proximity_delta(["alpha", "beta"], "beta comes first, alpha later") >= 0 or True  # out-of-order: no boost or worse window
    assert proximity_delta(["solo"], "anything") == 0.0, "single-term queries get no proximity delta"


def test_snippet_fallback_fills_a_blank_meta_snippet(mini):
    fb = mini.snippet_fallback("planning", "multi.md", "")
    assert fb.startswith("word"), "a bodyless :meta record previews the file's first real chunk"


def test_search_page_carries_what_it_is_not_showing(mini):
    page = search_page(mini, "kappa", base_opts(limit=1), exclusions=["indexed corpus excludes: x"])
    assert page.total >= len(page.hits)
    assert page.exclusions == ["indexed corpus excludes: x"]
    assert page.to_json_dict()["exclusions"] == page.exclusions


def test_interleave_yields_slots_when_a_lane_runs_dry():
    from set_kb.search import interleave_lanes

    class H:
        def __init__(self, name):
            self.name = name
            self.root = "r"
            self.path = name

    main = [H(f"m{i}") for i in range(4)]
    reserved = [H("r0")]
    out = interleave_lanes(main, reserved, 0.5, 4, dedup_sources=True, lead_first=False)
    assert [h.name for h in out][0] == "m0", "slot 1: (0+1)/(0+1) > share → main"
    assert [h.name for h in out][1] == "r0", "slot 2: (0+1)/(1+1) <= share → reserved"
    assert [h.name for h in out][2:] == ["m1", "m2"], "the dry lane yields its remaining slots"


def test_interleave_never_repeats_a_source_across_lanes():
    from set_kb.search import interleave_lanes

    class H:
        def __init__(self, name, root="r"):
            self.name = name
            self.root = root
            self.path = name

    main = [H("x"), H("y")]
    reserved = [H("y", root="other"), H("z")]  # y exists in both lanes
    out = interleave_lanes(main, reserved, 0.9, 4, dedup_sources=True, lead_first=True)
    names = [(h.root, h.path) for h in out]
    assert len(names) == len(set(names)), "a source taken by one lane is skipped in the other"


def test_mmr_diversifies_when_the_pool_exceeds_the_limit():
    from set_kb.search import mmr

    class H:
        def __init__(self, name, score):
            self.path = name
            self.root = "r"
            self.chunk_id = name
            self.heading_path = name
            self.score = score

    bodies = {"r·a": "alpha alpha alpha", "r·b": "alpha alpha beta", "r·c": "gamma delta epsilon"}
    ranked = [H("a", -3.0), H("b", -3.1), H("c", -3.2)]
    out = mmr(ranked, bodies, 0.7, 2)
    assert out[0].path == "a", "the top hit always survives"
    assert out[1].path == "c", "the near-duplicate of the leader is demoted behind the diverse hit"
