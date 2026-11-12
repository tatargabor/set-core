"""Opt-in Hungarian stemming (change kb-hungarian-stemming): the suffix stemmer,
the stem-prefix match expression, the loud config switch, and the end-to-end
recall the spec's scenarios name — on a purpose-built corpus where each
section spells exactly ONE form of a word, so a hit can only come from the
widening."""

from __future__ import annotations

import json

import pytest

from set_kb.config import CONFIG_REL, ConfigError, load_config, search_options
from set_kb.indexer import AtomicIndexSource, IndexOptions, RunIndexAtomicOpts, run_index_atomic
from set_kb.lang import language_pack
from set_kb.lang_hu import MIN_STEM, hungarian_pack, prefix_stem, stems
from set_kb.search import SearchOpts, search, to_match
from set_kb.store import SqliteFtsStore

from conftest_kb import make_repo, write

NO_MACHINE = "/nonexistent/kb-machine.json"


# ── the stemmer ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "word, stem",
    [
        ("vonalkódot", "vonalkod"),  # accusative
        ("vonalkódok", "vonalkod"),  # plural
        ("vonalkódokat", "vonalkod"),  # plural + accusative, two steps
        ("vonalkód", "vonalkod"),  # accented base form: widened by its letters
        ("vonalkóddal", "vonalkod"),  # assimilated instrumental (-val after d)
        ("kulccsal", "kulcs"),  # assimilated instrumental on a digraph (cs → ccs)
        ("rendszerrel", "rendszer"),
        ("számlákat", "szaml"),
        ("szamlakat", "szaml"),  # accents dropped by the user: same stem
        ("keretszerződésben", "keretszerzodes"),
        # the base `kod` is under the floor, so the accented word is widened
        # only as itself, folded — never down to a 3-letter prefix
        ("kódot", "kodot"),
    ],
)
def test_prefix_stem_reaches_the_base(word, stem):
    assert prefix_stem(word) == stem


@pytest.mark.parametrize("word", ["árak", "kód", "admin", "webp", "post"])
def test_short_or_unchanged_ascii_words_are_not_widened(word):
    """Below MIN_STEM a prefix matches far too much; an unchanged plain-ASCII
    word is left alone because a bilingual corpus is full of English words."""
    assert prefix_stem(word) is None


def test_no_form_is_shorter_than_the_floor():
    for w in ("termékek", "domainek", "content", "digit"):
        assert all(len(f) >= MIN_STEM for f in stems(w)[1:]), w


def test_the_hungarian_pack_carries_the_stemmer():
    assert hungarian_pack.stem is prefix_stem
    assert language_pack("en").stem is None, "English has none — stemming:true with en is a config error"


# ── the match expression ─────────────────────────────────────────────────────


def test_off_by_default_the_expression_is_unchanged():
    hu = language_pack("hu")
    assert to_match("vonalkódot", hu) == '"vonalkódot"'
    assert to_match("vonalkódot", hu, stemming=False) == '"vonalkódot"'


def test_stemming_replaces_the_term_with_its_stem_prefix():
    hu = language_pack("hu")
    assert to_match("vonalkódot", hu, stemming=True) == '"vonalkod"*'
    # a term the stemmer leaves alone is matched as written
    assert to_match("árak admin", hu, stemming=True) == '"árak" OR "admin"'
    # two forms of one word collapse into one prefix term, not two
    assert to_match("vonalkódot vonalkódok", hu, stemming=True) == '"vonalkod"*'


def test_stemming_without_a_stemmer_changes_nothing():
    assert to_match("vonalkódot", language_pack("en"), stemming=True) == '"vonalkódot"'


# ── the config switch ────────────────────────────────────────────────────────


def cfg_of(tmp_path, config: dict, name="repo"):
    root = make_repo(tmp_path, name)
    write(root / CONFIG_REL, json.dumps(config, ensure_ascii=False))
    return load_config(root, machine_path=NO_MACHINE)


def test_stemming_defaults_off_and_reaches_the_search_options(tmp_path):
    off = cfg_of(tmp_path, {"language": "hu"}, name="a")
    assert off.stemming is False and search_options(off).stemming is False
    on = cfg_of(tmp_path, {"language": "hu", "stemming": True}, name="b")
    assert on.stemming is True and search_options(on).stemming is True


def test_stemming_with_a_language_without_a_stemmer_is_loud(tmp_path):
    with pytest.raises(ConfigError, match=r"config\.stemming.*'en'.*packs with one: hu"):
        cfg_of(tmp_path, {"language": "en", "stemming": True})


def test_stemming_must_be_a_boolean(tmp_path):
    with pytest.raises(ConfigError, match=r"config\.stemming: expected a boolean"):
        cfg_of(tmp_path, {"language": "hu", "stemming": "yes"})


def test_stemming_does_not_force_a_reindex(tmp_path):
    from set_kb.config import corpus_config_hash

    a = cfg_of(tmp_path, {"language": "hu"}, name="h1")
    b = cfg_of(tmp_path, {"language": "hu", "stemming": True}, name="h2")
    assert corpus_config_hash(a) == corpus_config_hash(b), "query-side only: rows never change"


# ── end to end: each section spells ONE form ─────────────────────────────────


@pytest.fixture(scope="module")
def forms(tmp_path_factory):
    root = tmp_path_factory.mktemp("kb-forms")
    (root / "docs").mkdir()
    pad = " ".join(f"filler{i}" for i in range(40))  # keep sections above the merge threshold
    pages = {
        "base.md": ("Identification keys", "Every item carries a vonalkód on the label."),
        "plural-acc.md": ("Label printing", "The printer handles vonalkódokat in batches."),
        "invoice.md": ("Reporting", "Each számla is reported in real time."),
        "unrelated.md": ("Something else", "Nothing here mentions the identification code."),
    }
    for name, (heading, line) in pages.items():
        (root / "docs" / name).write_text(f"# {heading}\n\n{line}\n\n{pad} {name}\n", encoding="utf-8")
    db = root / "idx.db"
    run_index_atomic(RunIndexAtomicOpts(db_path=str(db), sources=[AtomicIndexSource(id="docs", dir=str(root / "docs"))], index_opts=IndexOptions()))
    store = SqliteFtsStore(str(db))
    store.init()
    yield store
    store.close()


def paths(store, q, stemming):
    opts = SearchOpts(language=language_pack("hu"), stemming=stemming, limit=10)
    return {h.path for h in search(store, q, opts)}


def test_an_inflected_query_finds_the_base_form(forms):
    assert "base.md" in paths(forms, "vonalkódot", True)
    assert "base.md" not in paths(forms, "vonalkódot", False), "off: the old miss is still there"


def test_a_base_form_query_finds_an_inflected_form(forms):
    assert "plural-acc.md" in paths(forms, "vonalkód", True)
    assert "plural-acc.md" not in paths(forms, "vonalkód", False)


def test_accents_dropped_by_the_user(forms):
    assert "invoice.md" in paths(forms, "szamlakat", True)
    assert "invoice.md" not in paths(forms, "szamlakat", False)


def test_the_assimilated_instrumental(forms):
    assert "base.md" in paths(forms, "vonalkóddal", True)


def test_the_widening_does_not_pull_in_unrelated_sections(forms):
    assert "unrelated.md" not in paths(forms, "vonalkódot", True)
