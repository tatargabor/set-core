"""Hungarian language pack.

Written new for the fork this engine descends from (the upstream stopword set
is English only; over a Hungarian corpus every `hogy`, `nem`, `van`, `ami` in a
question is carried into the FTS5 MATCH and into the ranking as if it were a
content word).

WHAT IS DELIBERATELY ABSENT: a stemmer. Measured over a mined question set:
base, prefix matching and a light Hungarian suffix stripper land within noise
of each other. The honest statement is "no measured benefit", NOT "it hurts".
The `stem` seam stays optional; this pack simply does not fill it.

SCOPE OF THE LIST: function words only — articles, conjunctions, pronouns,
postpositions, auxiliary/light verbs, quantifiers, discourse particles. A
DOMAIN word never belongs here: those are exactly the tokens the corpus is
searched by. Single characters are not listed — the tokenizer's `{2,}` lower
bound already drops them.
"""

from __future__ import annotations

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

# Hungarian pack = the Hungarian function words ON TOP OF the English ones.
# A corpus is bilingual in practice (English framework rules beside Hungarian
# knowledge pages), so the list is beside the English one, not instead of it.
hungarian_pack = LanguagePack(
    id="hu",
    stopwords=frozenset(ENGLISH_STOPWORDS | HUNGARIAN_STOPWORDS),
)

# Imported by `config` for the side effect, so a `language: "hu"` config
# resolves without every call site knowing which packs exist.
register_language_pack(hungarian_pack)
