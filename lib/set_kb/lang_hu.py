"""Hungarian language pack.

Written new for the fork this engine descends from (the upstream stopword set
is English only; over a Hungarian corpus every `hogy`, `nem`, `van`, `ami` in a
question is carried into the FTS5 MATCH and into the ranking as if it were a
content word).

THE STEMMER, and why it is opt-in. A suffix stripper, used ONLY on the query
side and only when the project config sets `stemming: true`: each query term
is matched as an FTS5 prefix of its shortest stem (see `prefix_stem`). Measured
2026-11-12 on a Hungarian business corpus whose pages are English with the
Hungarian domain word beside them: 16 Hungarian queries (inflected,
accent-dropped, whole questions) found their target in the top 10 4 times
without it and 16 times with it, and 9 English queries kept identical ranks.
An earlier measurement on a different corpus found base, prefix matching and a
light suffix stripper "within noise" — which is why it is a switch and not a
default: each corpus measures its own (`set-kb eval`).

The suffix list and the breadth-first stripping are adopted from the Hungarian
module of a sibling search plugin built on the same upstream engine, where they
are measured on an office archive. Added here: the assimilated instrumental
(`kóddal` → `kód`, `kulccsal` → `kulcs`), the one miss that list had on the
measured set.

SCOPE OF THE LIST: function words only — articles, conjunctions, pronouns,
postpositions, auxiliary/light verbs, quantifiers, discourse particles. A
DOMAIN word never belongs here: those are exactly the tokens the corpus is
searched by. Single characters are not listed — the tokenizer's `{2,}` lower
bound already drops them.
"""

from __future__ import annotations

import unicodedata
from typing import Optional

from set_kb.lang import ENGLISH_STOPWORDS, LanguagePack, register_language_pack

# Hungarian function words, alphabetical, one flat list so an addition is a
# one-line diff and a duplicate is visible on sight.
HUNGARIAN_STOPWORDS = frozenset(
    [
        "ahhoz", "ahogy", "ahol", "aki", "akik", "akkor", "alatt", "amely", "amelyek", "amelyik", "ami",
        "amiben", "amikor", "amit", "annak", "arra", "arról", "az", "azok", "azon", "azonban", "azt",
        "aztán", "azért", "be", "bele", "belül", "benne", "bár", "bárki", "csak", "csupán", "de", "ebben",
        "ebből", "eddig", "egy", "egyes", "egyik", "egyre", "egyéb", "ehhez", "ekkor", "el", "ellen",
        "elé", "előtt", "először", "első", "emiatt", "engem", "ennek", "ennyi", "ennél", "erre", "erről",
        "esetben", "ez", "ezek", "ezekre", "ezen", "ezt", "ezután", "ezért", "fel", "felé", "fog",
        "fogja", "ha", "hanem", "hiszen", "hogy", "hogyan", "hozzá", "hát", "ide", "igen", "illetve",
        "inkább", "is", "ismét", "itt", "jobban", "jól", "kell", "kellene", "kellett", "keresztül", "ki",
        "kicsit", "kívül", "közben", "között", "közül", "le", "legyen", "lehet", "lehetett", "lenne",
        "lenni", "lesz", "lett", "maga", "magát", "majd", "meg", "mellett", "mely", "melyek", "mert",
        "mi", "miatt", "mikor", "milyen", "mind", "minden", "mindig", "mindkét", "minket", "mit", "mivel",
        "miért", "mostmár", "már", "más", "másik", "még", "mögött", "nagyon", "neked", "neki", "nekem",
        "nekik", "nekünk", "nem", "nincs", "oda", "olyan", "onnan", "ott", "pedig", "persze", "például",
        "rá", "rájuk", "saját", "sem", "semmi", "senki", "sok", "sokkal", "során", "stb", "szemben",
        "szerint", "szinte", "számára", "talán", "tehát", "tovább", "további", "több", "túl", "ugyanaz",
        "ugyanis", "ugye", "után", "utána", "utolsó", "vagy", "vagyis", "vagyok", "van", "vannak", "vele",
        "velük", "vissza", "viszont", "volna", "volt", "voltak", "végül", "új", "úgy", "újra", "ön",
        "önök", "össze",
    ]
)

def fold(s: str) -> str:
    """Accent fold + lower case — the same normalisation FTS5 `unicode61`
    applies, so the suffix rules work on what the index holds."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(ch))


# Folded suffixes: case endings, plural, accusative, a few possessives. Short on
# purpose — a stripped stage only widens the prefix, it never removes a match.
HUNGARIAN_SUFFIXES = tuple(
    dict.fromkeys(
        fold(x)
        for x in (
            "jaitól", "eitől", "aitól",
            "ból", "ből", "ról", "ről", "tól", "től", "nak", "nek", "val", "vel", "ban", "ben", "hoz", "hez",
            "nál", "nél", "ként", "ért", "kor",
            "juk", "jük", "uk", "ük", "unk", "ünk", "ink", "ját", "jét", "aik", "eik",
            "ja", "je", "ba", "be", "ra", "re", "ig", "ul",
            "at", "et", "ot", "ak", "ek", "ok", "on", "en",
            "t", "k", "a", "e", "i",
        )
    )
)

# A stem shorter than this is never widened. Measured: at 4, English words
# lost too much (`content` → `cont`*, `digit` → `digi`*, `termékek` → `term`*
# reaching `terminal`); 5 kept every Hungarian hit on the measured set.
MIN_STEM = 5

_VOWELS = set("aeiou")
# The long-consonant digraphs whose doubling writes only the first letter twice.
_DIGRAPH_TAILS = ("cs", "sz", "gy", "ly", "ny", "ty", "zs")


def _undo_instrumental(w: str) -> Optional[str]:
    """`-val/-vel` after a consonant assimilates: the consonant doubles and the
    suffix becomes `-al/-el` (`kód+val` → `kóddal`, `kulcs+val` → `kulccsal`).
    Returns the base, or None when the word does not have that shape."""
    if len(w) < 5 or w[-2:] not in ("al", "el"):
        return None
    head = w[:-2]
    for dg in _DIGRAPH_TAILS:  # kulccs → kulcs
        if head.endswith(dg[0] + dg) and len(head) >= 3:
            return head[: -len(dg) - 1] + dg
    if len(head) >= 2 and head[-1] == head[-2] and head[-1] not in _VOWELS:
        return head[:-1]
    return None


def stems(word: str) -> list:
    """The folded word and its suffix-stripped forms (breadth first, three steps,
    every matching suffix at each step — Hungarian suffixes overlap:
    `szamlakat` → `szamlak` → `szamla` as well as `szaml`). No form shorter than
    MIN_STEM is produced."""
    w = fold(word)
    out = [w]
    frontier = [w]
    for _ in range(3):
        nxt: list = []
        for cur in frontier:
            cands = [cur[: -len(suf)] for suf in HUNGARIAN_SUFFIXES if cur.endswith(suf) and len(cur) - len(suf) >= MIN_STEM]
            base = _undo_instrumental(cur)
            if base is not None and len(base) >= MIN_STEM:
                cands.append(base)
            for c in cands:
                if c not in out:
                    out.append(c)
                    nxt.append(c)
        frontier = nxt
    return out


def prefix_stem(token: str) -> Optional[str]:
    """The pack's `stem`: the shortest form from `stems` that is at least
    MIN_STEM letters, to be matched as an FTS5 prefix term — or None, and the
    token is matched only as written.

    None also when nothing was stripped from a plain-ASCII token: a bilingual
    corpus is full of English words, and widening an unchanged `admin` to
    `admin`* reached `administrator` and moved English rankings for no Hungarian
    gain. An accented token is Hungarian by its letters, so its folded form is
    widened even unchanged (`vonalkód` → `vonalkod`* reaches `vonalkódot`)."""
    w = fold(token)
    forms = [f for f in stems(token) if len(f) >= MIN_STEM]
    if not forms:
        return None
    best = min(forms, key=len)
    if best == w and w == token.lower():
        return None
    return best


# Hungarian pack = the Hungarian function words ON TOP OF the English ones.
# A corpus is bilingual in practice (English framework rules beside Hungarian
# knowledge pages), so the list is beside the English one, not instead of it.
hungarian_pack = LanguagePack(
    id="hu",
    stopwords=frozenset(ENGLISH_STOPWORDS | HUNGARIAN_STOPWORDS),
    stem=prefix_stem,
)

# Imported by `config` for the side effect, so a `language: "hu"` config
# resolves without every call site knowing which packs exist.
register_language_pack(hungarian_pack)
