"""The living record must name every envelope field the reader actually consumes.

WHY A GATE AND NOT CARE. `CLAUDE.md` tells every session that this document outranks its
own recollection — "when your recollection and the living record disagree, the record
wins". That is a strong authority claim, and it is made to readers who cannot check it
cheaply: an agent resuming after a compact has nothing else. So a field the code reads and
the record never mentions is not a documentation gap. It is the record lending its
authority to an answer it does not contain, which is the same shape as a manifest pointing
at a stale specification.

The obligation runs in one direction on purpose: **the live code is the source, the
document is the obliged party.** The expected set is derived from the parser's own AST, so
adding a field to the envelope reader without saying what it means fails here. A
hard-coded list of field names would be the very thing this replaces — a second place to
forget.

**Its weakness, stated rather than discovered later:** this checks that a field is
MENTIONED, not that it is described correctly. It cannot stop the record from explaining a
field badly; it can only stop the record from being silent about one. The fail direction is
the safe one — a missing field fails loudly, and nothing passes quietly.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
READER = REPO / "lib" / "set_orch" / "project_status.py"
RECORD = REPO / "docs" / "integration" / "consumer-integration.md"


def envelope_keys_read_by_the_parser() -> set[str]:
    """Every literal key `parse_envelope` pulls out of the project's answer.

    Read from the syntax tree rather than by importing and calling, because the point is
    to catch a key the moment it is written — including one on a branch no live project
    currently exercises. A test that only sees keys a real answer happens to carry would
    pass through an empty cycle for exactly the fields most likely to be undocumented.
    """
    fn = next(
        n for n in ast.walk(ast.parse(READER.read_text()))
        if isinstance(n, ast.FunctionDef) and n.name == "parse_envelope"
    )
    keys: set[str] = set()
    for node in ast.walk(fn):
        # payload.get("x")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "payload"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)
        # "x" in payload / "x" not in payload
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], (ast.In, ast.NotIn))
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
            and isinstance(node.comparators[0], ast.Name)
            and node.comparators[0].id == "payload"
        ):
            keys.add(node.left.value)
        # payload["x"]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "payload"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)
    return keys


def named_as_a_field(key: str, document: str) -> bool:
    """Whether the document names this key AS A FIELD — inside code formatting.

    The looser test, a bare substring search, was measured and is worthless here: it
    reported every envelope field as documented while two were not mentioned at all. This
    record is English prose, and `error`, `message` and `data` are ordinary English words,
    so a bare-word gate passes on any sufficiently wordy page. A gate that cannot fail is
    indistinguishable from no gate, and worse, because it reports calm it never verified.
    """
    return re.search(rf"`[^`\n]*\b{re.escape(key)}\b[^`\n]*`", document) is not None


def test_every_envelope_field_the_reader_consumes_is_named_in_the_living_record():
    keys = envelope_keys_read_by_the_parser()
    assert keys, "the AST walk found nothing — the parser was refactored, fix this first"

    record = RECORD.read_text()
    missing = sorted(k for k in keys if not named_as_a_field(k, record))

    assert not missing, (
        f"{RECORD.relative_to(REPO)} never names {missing} as fields, but "
        "parse_envelope reads them. A reader is told this record outranks their own "
        "recollection, so silence here reads as 'no such field'."
    )


def test_a_bare_substring_check_would_not_have_caught_it():
    """The gate's own strictness is the load-bearing part, so it is held by a test.

    Without this, a later 'simplification' to `key in record` would look identical, pass,
    and quietly stop checking anything — the failure mode being defended against, arriving
    through the defence itself.
    """
    record = RECORD.read_text()

    for common_english_word in ("error", "message", "data"):
        assert common_english_word in record, "premise of this test"

    # …yet each is a real envelope field whose presence as PROSE proves nothing.
    assert {"error", "message", "data"} <= envelope_keys_read_by_the_parser()


def test_the_document_the_gate_reads_is_the_one_that_is_pointed_at():
    """A gate that checks a different file than the reader is sent to proves nothing.

    Borrowed from the consumer's version of this gate, which verifies its own pointer for
    the same reason: the check and the claim have to be about the same object.
    """
    claim = (REPO / "CLAUDE.md").read_text()

    assert str(RECORD.relative_to(REPO)) in claim, (
        "CLAUDE.md no longer points at the document this gate obliges — one of the two "
        "moved, and the gate is now guarding a file nobody is sent to."
    )
