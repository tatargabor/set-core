"""Language packs: the seam, the shipped Hungarian pack, loud unknown ids."""

from __future__ import annotations

import pytest

from set_kb.lang import ENGLISH_STOPWORDS, LanguagePack, language_pack, registered_languages, register_language_pack
from set_kb.lang_hu import HUNGARIAN_STOPWORDS, hungarian_pack  # registers "hu"
from set_kb.search import tokenize


def test_english_pack_is_upstream_verbatim():
    assert "the" in ENGLISH_STOPWORDS and "from" in ENGLISH_STOPWORDS


def test_hungarian_pack_is_registered_and_bilingual():
    assert "hu" in registered_languages()
    assert "hogy" in hungarian_pack.stopwords
    assert "the" in hungarian_pack.stopwords, "the Hungarian list sits BESIDE the English one"


def test_hungarian_pack_has_no_stemmer():
    assert hungarian_pack.stem is None, "no measured benefit — the seam stays unfilled"


def test_unknown_language_is_loud():
    with pytest.raises(KeyError) as e:
        language_pack("xx")
    assert "en" in str(e.value) and "hu" in str(e.value), "the known packs are named"


def test_tokenizer_drops_stopwords_keeps_content():
    tok = tokenize("Hogyan működik a számlázás?", hungarian_pack)
    assert "hogyan" not in [t.lower() for t in tok], "function word dropped"
    assert "működik" in tok and "számlázás" in tok, "domain words never dropped"


def test_tokenizer_accepts_every_script():
    assert tokenize("díjbekérő") == ["díjbekérő"], "an ASCII-only tokenizer would yield [] here"


def test_register_replaces_by_id():
    pack = LanguagePack(id="xx", stopwords=frozenset({"q"}))
    register_language_pack(pack)
    assert language_pack("xx") is pack
    registered = registered_languages()
    assert "xx" in registered and HUNGARIAN_STOPWORDS  # sanity: list is non-empty
