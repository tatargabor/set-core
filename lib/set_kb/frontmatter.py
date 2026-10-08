# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""Zero-dependency YAML-subset frontmatter parser + structural routing.

The parser is TOTAL (never raises) and PURE (same bytes → same output). It
supports a bounded grammar: `key: scalar`, inline `[a, b]`, block `- item`
lists, bool/int/float, `YYYY-MM-DD`, `#` comments, single/double quotes.
Unsupported constructs (anchors/aliases, `|`/`>` block scalars handled
explicitly below, general nested maps, merge keys) fall back to string / skip —
never a raise. A top-level `kb:` key and its indented subtree are consumed and
discarded (owned by the semantic-annotation plane upstream).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional, Union

logger = logging.getLogger(__name__)

FmValue = Union[str, int, float, bool, list]


@dataclass
class ParsedFrontmatter:
    body: str  # markdown after the frontmatter block (CRLF-normalized)
    fm: Optional[dict]  # None when no/malformed frontmatter
    parse_failed: bool  # a frontmatter block was present but a line did not parse


def _quoted_prefix(s: str) -> str:
    """Scan to the closing quote of a quoted prefix, honoring escapes.

    The previous naive "find the quote" truncation cut an ESCAPED quote inside
    the value and dropped the tail as a pseudo-comment — titles are a default
    searchable key, so those meta records were unfindable by their full titles.
    Double quotes honor `\\"`/`\\\\`; single quotes honor YAML's `''` doubling.
    Unterminated → the whole string, unchanged.
    """
    q = s[0]
    i = 1
    while i < len(s):
        if q == '"' and s[i] == "\\":
            i += 2
            continue
        if q == "'" and s[i] == "'" and s[i + 1 : i + 2] == "'":
            i += 2
            continue
        if s[i] == q:
            return s[: i + 1]
        i += 1
    return s


def _strip_comment(s: str) -> str:
    """Strip a trailing `# comment`. For a quoted value, keep through the
    closing quote and drop any comment after it (`title: "H" # c` → `"H"`)."""
    t = s.strip()
    if t.startswith('"') or t.startswith("'"):
        return _quoted_prefix(t)
    idx = t.find(" #")
    return (t[:idx] if idx >= 0 else t).strip()


def _coerce_scalar(raw: str) -> FmValue:
    """Coerce a bare scalar token to bool/int/float/string. Quoted → string,
    with the same escapes `_quoted_prefix` honored (`\\"` → `"`, `\\\\` → `\\`,
    `''` → `'`). Other backslash sequences stay literal — bounded grammar;
    guessing at `\\n` would silently rewrite values."""
    s = raw.strip()
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return re.sub(r'\\(["\\])', r"\1", s[1:-1])
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    if s == "true":
        return True
    if s == "false":
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _parse_inline_array(s: str) -> list:
    """Parse an inline `[a, b, "c"]` array (elements trimmed/unquoted)."""
    inner = re.sub(r"^\[", "", re.sub(r"\]$", "", s))
    out = []
    for e in inner.split(","):
        t = e.strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            t = t[1:-1]
        t = t.strip()
        if t:
            out.append(t)
    return out


def _is_indented(line: str) -> bool:
    return bool(re.match(r"^\s", line))


def _is_blank(line: str) -> bool:
    return line.strip() == ""


_KEY_RE = re.compile(r"^([\w.\-/]+):(.*)$", re.UNICODE)


def parse_frontmatter(text: str) -> ParsedFrontmatter:
    """Detect + parse a leading YAML-subset frontmatter block. Total + pure."""
    norm = re.sub(r"\r\n?", "\n", text[1:] if text.startswith("\ufeff") else text)  # strip BOM; CRLF/CR → LF
    lines = norm.split("\n")
    if lines[0] != "---":
        return ParsedFrontmatter(body=norm, fm=None, parse_failed=False)
    end = -1
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end = i
            break
    if end == -1:
        return ParsedFrontmatter(body=norm, fm=None, parse_failed=False)  # no closing fence → not frontmatter

    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1 :])
    fm: dict = {}
    parse_failed = False

    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        i += 1
        if _is_blank(line) or line.strip().startswith("#"):
            continue
        if _is_indented(line):
            continue  # stray indented line without a parent key context
        m = _KEY_RE.match(line)
        if not m:
            parse_failed = True
            continue
        key = m.group(1)
        rest = _strip_comment(m.group(2))

        # Top-level `kb:` — consume + discard its entire indented subtree.
        if key == "kb":
            while i < len(fm_lines) and (_is_indented(fm_lines[i]) or _is_blank(fm_lines[i])):
                i += 1
            continue

        if rest == "":
            # block list, nested map, or empty scalar
            items = []
            while i < len(fm_lines) and re.match(r"^\s*-\s+", fm_lines[i]):
                items.append(_strip_comment(re.sub(r"^\s*-\s+", "", fm_lines[i])).strip("\"'"))
                i += 1
            if items:
                fm[key] = [e for e in items if e]
            elif i < len(fm_lines) and re.match(r"^\s+\S", fm_lines[i]):
                # nested map (unsupported) → skip its indented subtree, emit nothing
                while i < len(fm_lines) and (_is_indented(fm_lines[i]) or _is_blank(fm_lines[i])):
                    i += 1
            else:
                fm[key] = ""
            continue

        # Multiline block scalar (`key: |`, `key: >`, with an optional chomping
        # indicator `-`/`+` and an explicit indent digit). This used to SKIP the
        # block and leave parse_failed at False — a silent value loss
        # indistinguishable from "the key was not there".
        # ⚠ `_strip_comment` is deliberately NOT applied to the block body:
        # inside a block scalar a `#` is content, not a comment.
        if re.fullmatch(r"[|>][-+]?\d*", rest):
            raw = []
            while i < len(fm_lines) and (_is_indented(fm_lines[i]) or _is_blank(fm_lines[i])):
                raw.append(fm_lines[i])
                i += 1
            while raw and _is_blank(raw[-1]):
                raw.pop()
            body_lines = [l for l in raw if not _is_blank(l)]
            indent = min((len(l) - len(l.lstrip()) for l in body_lines), default=0)
            dedented = ["" if _is_blank(l) else l[indent:] for l in raw]
            # `>` folds the block to a single line, `|` keeps the line breaks.
            if rest.startswith(">"):
                fm[key] = re.sub(r"\s+", " ", " ".join(dedented)).strip()
            else:
                fm[key] = "\n".join(dedented)
            continue

        if rest.startswith("["):
            fm[key] = _parse_inline_array(rest)
            continue

        fm[key] = _coerce_scalar(rest)

    return ParsedFrontmatter(body=body, fm=fm, parse_failed=parse_failed)


# ── Structural routing: frontmatter → searchable meta + property rows ──

DEFAULT_SEARCHABLE_KEYS = ["title", "description", "aliases", "keywords"]
DEFAULT_FACET_KEYS = [
    {"key": "tags"},
    {"key": "status"},
    {"key": "author"},
    {"key": "category"},
    {"key": "date", "type": "date"},
]


def _strict_number(v) -> Optional[float]:
    """Strict full-match numeric coercion; None when not a clean, finite number
    (a very long digit string parses to inf — rejected)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip()):
        n = float(v.strip())
        return n if n == n and abs(n) != float("inf") else None
    return None


def _strict_date(v) -> Optional[str]:
    """Strict `YYYY-MM-DD` calendar date; None otherwise. Rejects impossible
    dates (e.g. `2024-02-31`). Instants deferred — bounded grammar."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(v).strip())
    if not m:
        return None
    try:
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def build_meta(fm: dict, searchable_keys: list) -> dict:
    """Build the searchable meta pieces: title (→ heading) and the rest (→
    body). `tags` is never searchable (it is a facet)."""
    title = None
    if "title" in searchable_keys and fm.get("title") is not None:
        v = fm["title"]
        title = str(" ".join(v) if isinstance(v, list) else v)
    parts = []
    for key in searchable_keys:
        if key == "title" or key == "tags":
            continue
        v = fm.get(key)
        if v is None:
            continue
        parts.append(" ".join(v) if isinstance(v, list) else str(v))
    return {"title": title, "body": " ".join(parts).strip()}


def build_properties(fm: dict, facet_keys: list) -> list:
    """Build de-duplicated property rows for the whitelisted facet keys.
    Array values → one row per distinct element; within-file duplicates
    collapse. Each entry of `facet_keys` is `{"key": str, "type"?: str}`."""
    rows = []
    for fk in facet_keys:
        key, type_ = fk["key"], fk.get("type")
        v = fm.get(key)
        if v is None:
            continue
        elems = v if isinstance(v, list) else [v]
        seen = set()
        for e in elems:
            raw = str(e)
            value = raw.lower().strip()
            if value == "" or value in seen:
                continue
            seen.add(value)
            rows.append(
                {
                    "key": key,
                    "value": value,
                    "value_num": _strict_number(e) if type_ == "number" else None,
                    "value_date": _strict_date(raw) if type_ == "date" else None,
                    "value_raw": raw,
                }
            )
    return rows
