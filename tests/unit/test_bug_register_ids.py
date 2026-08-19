"""The bug register's identifiers must be unique, and a rule alone does not do it.

Written after the rule failed twice in one day, the second time within an hour of
being written down — and by the session that wrote it.

**First failure, 2026-08-19:** one session issued `B-9` and `B-10` twice, four
commits apart, colliding with itself. **Second, the same day:** a session
measured the register at 16 entries, wrote `B-17` and `B-18` from that number,
and by then a PARALLEL session had already taken both. That is the shape that
makes this a test rather than a paragraph: the register is a file two sessions
write, so the largest number is not something anybody can carry in their head —
it changes while you are typing.

What a collision costs is not tidiness. *"B-9 is closed"* stops being an
answerable sentence when two different defects answer to it, and every commit
message, task and channel entry that cites the id inherits the ambiguity.

⚠ A COMMENT ASKS TO BE BELIEVED; A TEST REFUSES TO BE REVERTED. The register's
own format section states the allocation rule in prose. Prose is exactly what
was in place for both failures.
"""
import re
from collections import Counter
from pathlib import Path

REGISTER = Path(__file__).resolve().parents[2] / "openspec" / "bugs" / "README.md"


def _entries():
    """Every entry heading, with the fenced format EXAMPLE excluded.

    The example is `### B-<n> — <one line…>` inside a code fence, and a bare
    line-scan counts it — the measurement sitting inside the corpus it measures.
    """
    text = re.sub(r"```.*?```", "", REGISTER.read_text(encoding="utf-8"), flags=re.S)
    return re.findall(r"^### (B-\d+) — (.+)$", text, flags=re.M)


def test_no_identifier_names_two_defects():
    seen = Counter(ident for ident, _ in _entries())
    clashes = {k: v for k, v in seen.items() if v > 1}
    assert not clashes, (
        "these identifiers name more than one defect: "
        + ", ".join(f"{k} ×{v}" for k, v in sorted(clashes.items()))
        + " — allocate by MEASURING the file, never from memory; two sessions "
          "write this register and the largest number changes while you type"
    )


def test_the_register_has_entries_at_all():
    """A regex that silently matches nothing would make the test above pass
    for ever. Every count is worth this much: a zero with an empty breakdown is
    a shape error until proven otherwise.
    """
    entries = _entries()
    assert len(entries) >= 10, f"only {len(entries)} entries parsed — the heading shape changed?"


def test_a_bare_line_scan_would_have_counted_the_format_example():
    """Holds the WRONG pattern, so a later simplification back to it fails
    instead of looking identical and quietly counting one entry too many.
    """
    raw = REGISTER.read_text(encoding="utf-8")
    naive = re.findall(r"^### (B-\d+) — ", raw, flags=re.M)
    fenced = re.findall(r"^### (B-<n>) — ", raw, flags=re.M)
    assert fenced, "the format example no longer looks like an entry — re-check this guard"
    assert len(naive) == len(_entries()), (
        "the fence-stripping and the naive scan disagree about the entry count"
    )


def test_every_entry_declares_a_state():
    """An entry with no state is one nobody can act on, which is the same as not
    having written it. The register's own two conditions say so.
    """
    text = re.sub(r"```.*?```", "", REGISTER.read_text(encoding="utf-8"), flags=re.S)
    blocks = re.split(r"^### B-\d+ — .+$", text, flags=re.M)[1:]
    stateless = [
        ident for (ident, _), block in zip(_entries(), blocks)
        if not re.search(r"^- \*\*state:\*\*", block, flags=re.M)
    ]
    assert not stateless, f"entries with no state: {', '.join(stateless)}"
