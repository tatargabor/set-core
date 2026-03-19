"""Tests for set_orch.dispatcher_schema — Prisma schema parsing and digest generation."""

import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.dispatcher_schema import (
    ParsedSchema,
    SchemaEnum,
    SchemaField,
    SchemaModel,
    append_schema_digest_to_claudemd,
    format_schema_digest,
    parse_prisma_schema,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


SAMPLE_PRISMA = """\
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String?
  orders    Order[]
  createdAt DateTime @default(now())
}

model Order {
  id          String      @id @default(cuid())
  totalAmount Decimal
  status      OrderStatus @default(PENDING)
  userId      String
  user        User        @relation(fields: [userId], references: [id])
  items       OrderItem[]
}

model OrderItem {
  id       String @id @default(cuid())
  quantity Int
  price    Decimal
  orderId  String
  order    Order  @relation(fields: [orderId], references: [id])
}

enum OrderStatus {
  PENDING
  PROCESSING
  SHIPPED
  DELIVERED
  CANCELLED
}

enum Role {
  USER
  ADMIN
}
"""


class TestParsePrismaSchema:
    def test_parses_models(self, tmp_dir):
        schema_path = os.path.join(tmp_dir, "schema.prisma")
        with open(schema_path, "w") as f:
            f.write(SAMPLE_PRISMA)

        result = parse_prisma_schema(schema_path)
        model_names = [m.name for m in result.models]
        assert "User" in model_names
        assert "Order" in model_names
        assert "OrderItem" in model_names
        assert len(result.models) == 3

    def test_parses_fields(self, tmp_dir):
        schema_path = os.path.join(tmp_dir, "schema.prisma")
        with open(schema_path, "w") as f:
            f.write(SAMPLE_PRISMA)

        result = parse_prisma_schema(schema_path)
        user = next(m for m in result.models if m.name == "User")
        field_names = [f.name for f in user.fields]
        assert "id" in field_names
        assert "email" in field_names
        assert "name" in field_names
        assert "orders" in field_names

    def test_parses_field_attributes(self, tmp_dir):
        schema_path = os.path.join(tmp_dir, "schema.prisma")
        with open(schema_path, "w") as f:
            f.write(SAMPLE_PRISMA)

        result = parse_prisma_schema(schema_path)
        user = next(m for m in result.models if m.name == "User")

        id_field = next(f for f in user.fields if f.name == "id")
        assert id_field.is_id is True
        assert id_field.default == "cuid()"

        email_field = next(f for f in user.fields if f.name == "email")
        assert email_field.is_unique is True

        name_field = next(f for f in user.fields if f.name == "name")
        assert name_field.is_optional is True

    def test_parses_relations(self, tmp_dir):
        schema_path = os.path.join(tmp_dir, "schema.prisma")
        with open(schema_path, "w") as f:
            f.write(SAMPLE_PRISMA)

        result = parse_prisma_schema(schema_path)
        order = next(m for m in result.models if m.name == "Order")

        user_rel = next(f for f in order.fields if f.name == "user")
        assert user_rel.relation_to == "User"

        items_rel = next(f for f in order.fields if f.name == "items")
        assert items_rel.relation_to == "OrderItem"
        assert items_rel.is_list is True

    def test_parses_list_relations(self, tmp_dir):
        schema_path = os.path.join(tmp_dir, "schema.prisma")
        with open(schema_path, "w") as f:
            f.write(SAMPLE_PRISMA)

        result = parse_prisma_schema(schema_path)
        user = next(m for m in result.models if m.name == "User")
        orders_field = next(f for f in user.fields if f.name == "orders")
        assert orders_field.is_list is True
        assert orders_field.relation_to == "Order"

    def test_parses_enums(self, tmp_dir):
        schema_path = os.path.join(tmp_dir, "schema.prisma")
        with open(schema_path, "w") as f:
            f.write(SAMPLE_PRISMA)

        result = parse_prisma_schema(schema_path)
        enum_names = [e.name for e in result.enums]
        assert "OrderStatus" in enum_names
        assert "Role" in enum_names

        order_status = next(e for e in result.enums if e.name == "OrderStatus")
        assert order_status.values == ["PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]

        role = next(e for e in result.enums if e.name == "Role")
        assert role.values == ["USER", "ADMIN"]

    def test_missing_file_returns_empty(self, tmp_dir):
        result = parse_prisma_schema(os.path.join(tmp_dir, "nonexistent.prisma"))
        assert result.models == []
        assert result.enums == []


class TestFormatSchemaDigest:
    def test_formats_model_table(self):
        schema = ParsedSchema(models=[
            SchemaModel(name="User", fields=[
                SchemaField(name="id", type="String", is_id=True, default="cuid()"),
                SchemaField(name="email", type="String", is_unique=True),
                SchemaField(name="name", type="String", is_optional=True),
            ]),
        ])
        result = format_schema_digest(schema)
        assert "### User" in result
        assert "| id | String | @id, default(cuid()) |" in result
        assert "| email | String | @unique |" in result
        assert "| name | String? |  |" in result

    def test_formats_relations(self):
        schema = ParsedSchema(models=[
            SchemaModel(name="Order", fields=[
                SchemaField(name="user", type="User", relation_to="User"),
                SchemaField(name="items", type="OrderItem", is_list=True, relation_to="OrderItem"),
            ]),
        ])
        result = format_schema_digest(schema)
        assert "→ User" in result
        assert "→ OrderItem" in result

    def test_formats_enums(self):
        schema = ParsedSchema(enums=[
            SchemaEnum(name="Status", values=["ACTIVE", "INACTIVE"]),
        ])
        result = format_schema_digest(schema)
        assert "### Enums" in result
        assert "**Status**: ACTIVE, INACTIVE" in result

    def test_empty_schema_returns_empty(self):
        assert format_schema_digest(ParsedSchema()) == ""


class TestAppendSchemaDigest:
    def test_appends_to_existing_claudemd(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "prisma"))
        with open(os.path.join(tmp_dir, "prisma", "schema.prisma"), "w") as f:
            f.write(SAMPLE_PRISMA)
        with open(os.path.join(tmp_dir, "CLAUDE.md"), "w") as f:
            f.write("# My Project\n\nExisting content.\n")

        result = append_schema_digest_to_claudemd(tmp_dir)
        assert result is True

        content = open(os.path.join(tmp_dir, "CLAUDE.md")).read()
        assert "# My Project" in content
        assert "## Project Schema (auto-generated, readonly)" in content
        assert "### User" in content
        assert "### Order" in content
        assert "OrderStatus" in content

    def test_creates_claudemd_if_missing(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "prisma"))
        with open(os.path.join(tmp_dir, "prisma", "schema.prisma"), "w") as f:
            f.write(SAMPLE_PRISMA)

        result = append_schema_digest_to_claudemd(tmp_dir)
        assert result is True
        assert os.path.isfile(os.path.join(tmp_dir, "CLAUDE.md"))

    def test_idempotent_replace(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "prisma"))
        with open(os.path.join(tmp_dir, "prisma", "schema.prisma"), "w") as f:
            f.write(SAMPLE_PRISMA)
        with open(os.path.join(tmp_dir, "CLAUDE.md"), "w") as f:
            f.write("# Header\n\n## Project Schema (auto-generated, readonly)\n\nOLD CONTENT\n\n## Other Section\n\nKeep this.\n")

        result = append_schema_digest_to_claudemd(tmp_dir)
        assert result is True

        content = open(os.path.join(tmp_dir, "CLAUDE.md")).read()
        assert "OLD CONTENT" not in content
        assert "### User" in content
        assert "## Other Section" in content
        assert "Keep this." in content

    def test_no_prisma_returns_false(self, tmp_dir):
        result = append_schema_digest_to_claudemd(tmp_dir)
        assert result is False

    def test_accurate_field_names(self, tmp_dir):
        """The whole point: field names match the schema exactly."""
        os.makedirs(os.path.join(tmp_dir, "prisma"))
        with open(os.path.join(tmp_dir, "prisma", "schema.prisma"), "w") as f:
            f.write(SAMPLE_PRISMA)

        append_schema_digest_to_claudemd(tmp_dir)
        content = open(os.path.join(tmp_dir, "CLAUDE.md")).read()

        # Exact field names from schema — not LLM-hallucinated alternatives
        assert "totalAmount" in content   # NOT "total"
        assert "userId" in content        # NOT "user_id"
        assert "createdAt" in content     # NOT "created_at"
