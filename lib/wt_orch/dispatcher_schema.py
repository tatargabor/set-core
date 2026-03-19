"""Schema digest generation for dispatch context.

Parses ORM schema files (Prisma, etc.) at dispatch time and generates
a concise markdown digest for injection into worktree CLAUDE.md.
Replaces the stale LLM-generated data-definitions.md.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ─── Data Structures ────────────────────────────────────────────────


@dataclass
class SchemaField:
    name: str
    type: str
    is_optional: bool = False
    is_list: bool = False
    is_id: bool = False
    is_unique: bool = False
    default: str | None = None
    relation_to: str | None = None


@dataclass
class SchemaModel:
    name: str
    fields: list[SchemaField] = field(default_factory=list)


@dataclass
class SchemaEnum:
    name: str
    values: list[str] = field(default_factory=list)


@dataclass
class ParsedSchema:
    models: list[SchemaModel] = field(default_factory=list)
    enums: list[SchemaEnum] = field(default_factory=list)


# ─── Prisma Parser ──────────────────────────────────────────────────

# Regex patterns for Prisma schema parsing
_MODEL_BLOCK_RE = re.compile(r"^model\s+(\w+)\s*\{", re.MULTILINE)
_ENUM_BLOCK_RE = re.compile(r"^enum\s+(\w+)\s*\{", re.MULTILINE)
_FIELD_RE = re.compile(
    r"^\s+(\w+)\s+"           # field name
    r"(\w+)(\[\])?"           # type + optional array
    r"(\?)?"                  # optional marker
    r"(.*?)$",                # rest of line (attributes)
    re.MULTILINE,
)


def _extract_block(text: str, start_pos: int) -> str:
    """Extract content between { } starting from a match position."""
    brace_start = text.index("{", start_pos)
    depth = 1
    i = brace_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[brace_start + 1 : i - 1]


def _parse_field_attributes(attr_str: str) -> dict:
    """Parse Prisma field attributes like @id, @default(...), @relation(...)."""
    result: dict = {}
    if "@id" in attr_str:
        result["is_id"] = True
    if "@unique" in attr_str:
        result["is_unique"] = True

    default_m = re.search(r"@default\(", attr_str)
    if default_m:
        # Balance parentheses to handle nested calls like cuid(), now(), uuid()
        start = default_m.end()
        depth = 1
        i = start
        while i < len(attr_str) and depth > 0:
            if attr_str[i] == "(":
                depth += 1
            elif attr_str[i] == ")":
                depth -= 1
            i += 1
        result["default"] = attr_str[start:i - 1]

    relation_m = re.search(r"@relation\(", attr_str)
    if relation_m:
        # Extract fields reference if present
        fields_m = re.search(r'fields:\s*\[([^\]]+)\]', attr_str)
        refs_m = re.search(r'references:\s*\[([^\]]+)\]', attr_str)
        if fields_m:
            result["relation_fields"] = fields_m.group(1).strip()
        if refs_m:
            result["relation_refs"] = refs_m.group(1).strip()

    return result


def parse_prisma_schema(schema_path: str) -> ParsedSchema:
    """Parse a Prisma schema file into structured data.

    Uses regex parsing — no Prisma CLI dependency required.
    """
    try:
        text = Path(schema_path).read_text(encoding="utf-8")
    except OSError:
        logger.warning("Cannot read Prisma schema: %s", schema_path)
        return ParsedSchema()

    schema = ParsedSchema()

    # Parse models
    for m in _MODEL_BLOCK_RE.finditer(text):
        model_name = m.group(1)
        block = _extract_block(text, m.start())
        model = SchemaModel(name=model_name)

        for fm in _FIELD_RE.finditer(block):
            fname = fm.group(1)
            ftype = fm.group(2)
            is_list = fm.group(3) is not None
            is_optional = fm.group(4) is not None
            attrs_str = fm.group(5) or ""

            # Skip @@-level attributes (they start with @@)
            if fname.startswith("@@"):
                continue

            attrs = _parse_field_attributes(attrs_str)

            # Detect relation: field type matches a model name or has @relation
            relation_to = None
            if "relation_fields" in attrs or "@relation" in attrs_str:
                relation_to = ftype
            elif ftype[0].isupper() and ftype not in (
                "String", "Int", "Float", "Boolean", "DateTime",
                "Json", "Bytes", "Decimal", "BigInt",
            ):
                relation_to = ftype

            model.fields.append(SchemaField(
                name=fname,
                type=ftype,
                is_optional=is_optional,
                is_list=is_list,
                is_id=attrs.get("is_id", False),
                is_unique=attrs.get("is_unique", False),
                default=attrs.get("default"),
                relation_to=relation_to,
            ))

        schema.models.append(model)

    # Parse enums
    for m in _ENUM_BLOCK_RE.finditer(text):
        enum_name = m.group(1)
        block = _extract_block(text, m.start())
        values = [
            line.strip()
            for line in block.splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        schema.enums.append(SchemaEnum(name=enum_name, values=values))

    logger.info(
        "Parsed Prisma schema: %d models, %d enums",
        len(schema.models), len(schema.enums),
    )
    return schema


# ─── Markdown Formatter ─────────────────────────────────────────────


def format_schema_digest(schema: ParsedSchema) -> str:
    """Convert parsed schema into concise markdown for CLAUDE.md injection."""
    if not schema.models and not schema.enums:
        return ""

    lines: list[str] = []

    for model in schema.models:
        lines.append(f"### {model.name}")
        lines.append("| Field | Type | Notes |")
        lines.append("|-------|------|-------|")

        for f in model.fields:
            type_str = f.type
            if f.is_list:
                type_str += "[]"
            if f.is_optional:
                type_str += "?"

            notes: list[str] = []
            if f.is_id:
                notes.append("@id")
            if f.is_unique:
                notes.append("@unique")
            if f.default is not None:
                notes.append(f"default({f.default})")
            if f.relation_to:
                notes.append(f"→ {f.relation_to}")

            lines.append(f"| {f.name} | {type_str} | {', '.join(notes)} |")

        lines.append("")

    if schema.enums:
        lines.append("### Enums")
        for enum in schema.enums:
            lines.append(f"- **{enum.name}**: {', '.join(enum.values)}")
        lines.append("")

    return "\n".join(lines)


# ─── CLAUDE.md Integration ──────────────────────────────────────────

_SECTION_HEADER = "## Project Schema (auto-generated, readonly)"
_SECTION_END_RE = re.compile(r"^## ", re.MULTILINE)


def append_schema_digest_to_claudemd(wt_path: str) -> bool:
    """Append or replace ``## Project Schema`` section in worktree CLAUDE.md.

    Idempotent: replaces existing section if present, appends if not.
    Creates CLAUDE.md if missing.

    Returns True if section was written, False if skipped (no schema found).
    """
    # Detect ORM schema
    schema_path = os.path.join(wt_path, "prisma", "schema.prisma")
    if not os.path.isfile(schema_path):
        return False

    parsed = parse_prisma_schema(schema_path)
    digest = format_schema_digest(parsed)
    if not digest:
        return False

    section = f"\n\n{_SECTION_HEADER}\n\n{digest}"

    claude_md = os.path.join(wt_path, "CLAUDE.md")
    existing = ""
    if os.path.isfile(claude_md):
        try:
            existing = Path(claude_md).read_text(encoding="utf-8")
        except OSError:
            pass

    if _SECTION_HEADER in existing:
        # Replace existing section
        header_pos = existing.index(_SECTION_HEADER)
        # Find next ## header after our section
        rest = existing[header_pos + len(_SECTION_HEADER):]
        next_header = _SECTION_END_RE.search(rest)
        if next_header:
            end_pos = header_pos + len(_SECTION_HEADER) + next_header.start()
            new_content = existing[:header_pos] + _SECTION_HEADER + "\n\n" + digest + "\n" + existing[end_pos:]
        else:
            new_content = existing[:header_pos] + _SECTION_HEADER + "\n\n" + digest
        try:
            with open(claude_md, "w") as f:
                f.write(new_content)
            logger.info("Replaced Project Schema section in %s", claude_md)
            return True
        except OSError:
            logger.warning("Failed to update schema in %s", claude_md)
            return False
    else:
        # Append new section
        try:
            with open(claude_md, "a") as f:
                f.write(section)
            logger.info("Appended Project Schema digest to %s", claude_md)
            return True
        except OSError:
            logger.warning("Failed to write schema digest to %s", claude_md)
            return False
