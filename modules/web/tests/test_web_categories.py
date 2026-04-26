"""Tests for ``WebProjectType``'s seven category-resolver overrides.

Pins the contract from
``openspec/specs/change-category-resolver/spec.md`` from the web
profile's perspective.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_project_web.project_type import WebProjectType


@pytest.fixture
def web():
    return WebProjectType()


# ─── detect_project_categories ──────────────────────────────────────────


def test_minimal_web_project_only_general_frontend(web, tmp_path):
    """No auth/db/api signals → just general + frontend."""
    cats = web.detect_project_categories(tmp_path)
    assert cats == {"general", "frontend"}


def test_middleware_ts_at_root_triggers_auth(web, tmp_path):
    (tmp_path / "middleware.ts").write_text("export const config = {}")
    cats = web.detect_project_categories(tmp_path)
    assert "auth" in cats


def test_middleware_ts_in_src_triggers_auth(web, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "middleware.ts").write_text("export const config = {}")
    cats = web.detect_project_categories(tmp_path)
    assert "auth" in cats


def test_next_auth_dep_triggers_auth(web, tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"next-auth": "^5.0.0", "next": "^14"},
    }))
    cats = web.detect_project_categories(tmp_path)
    assert "auth" in cats


def test_clerk_dep_triggers_auth(web, tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"@clerk/nextjs": "^4.0.0"},
    }))
    assert "auth" in web.detect_project_categories(tmp_path)


def test_prisma_dep_triggers_database(web, tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"@prisma/client": "^5"},
        "devDependencies": {"prisma": "^5"},
    }))
    cats = web.detect_project_categories(tmp_path)
    assert "database" in cats


def test_drizzle_dep_triggers_database(web, tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"drizzle-orm": "^0.30"},
    }))
    assert "database" in web.detect_project_categories(tmp_path)


def test_app_api_dir_triggers_api(web, tmp_path):
    (tmp_path / "src" / "app" / "api").mkdir(parents=True)
    cats = web.detect_project_categories(tmp_path)
    assert "api" in cats


def test_pages_api_dir_triggers_api(web, tmp_path):
    """Pages Router projects also detected."""
    (tmp_path / "pages" / "api").mkdir(parents=True)
    assert "api" in web.detect_project_categories(tmp_path)


def test_full_stack_project_all_categories(web, tmp_path):
    """E-commerce shape: auth + db + api + frontend (all the things)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "middleware.ts").write_text("export {}")
    (tmp_path / "src" / "app" / "api").mkdir(parents=True)
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"next-auth": "^5", "@prisma/client": "^5", "next": "^14"},
    }))
    cats = web.detect_project_categories(tmp_path)
    assert {"general", "frontend", "auth", "database", "api"} <= cats


# ─── detect_scope_categories ────────────────────────────────────────────


def test_scope_oauth_triggers_auth(web):
    assert "auth" in web.detect_scope_categories("Add OAuth login flow")


def test_scope_password_triggers_auth(web):
    assert "auth" in web.detect_scope_categories("Form to reset password")


def test_scope_design_tokens_does_not_trigger_auth(web):
    """Bug #2 fix: 'token' must NOT match auth via substring.
    Witnessed in micro-web foundation scope where 'design tokens'
    activated the auth category."""
    cats = web.detect_scope_categories("Configure design tokens for the theme")
    assert "auth" not in cats


def test_scope_page_routes_does_not_trigger_api(web):
    """Bug #2 fix: 'route' must NOT match api via substring."""
    cats = web.detect_scope_categories("Add 4 page routes for the marketing site")
    assert "api" not in cats


def test_scope_post_endpoint_triggers_api(web):
    assert "api" in web.detect_scope_categories("Add POST /api/users endpoint")


def test_scope_router_post_triggers_api(web):
    assert "api" in web.detect_scope_categories("Wire up router.post('/users', handler)")


def test_scope_prisma_migration_triggers_database(web):
    assert "database" in web.detect_scope_categories("Run prisma migration to add column")


def test_scope_checkout_triggers_payment(web):
    assert "payment" in web.detect_scope_categories("Add checkout flow with Stripe")


def test_scope_pure_frontend_no_domain_categories(web):
    """A scope that mentions only UI work returns empty (frontend
    comes from change_type/paths, not scope detection)."""
    cats = web.detect_scope_categories(
        "Build sticky header with Cmd+K trigger and mobile sheet drawer"
    )
    assert cats == set()


# ─── categories_from_paths ──────────────────────────────────────────────


def test_paths_app_api_triggers_api(web):
    assert "api" in web.categories_from_paths(["src/app/api/users/route.ts"])


def test_paths_pages_api_triggers_api(web):
    assert "api" in web.categories_from_paths(["pages/api/auth.ts"])


def test_paths_prisma_dir_triggers_database(web):
    assert "database" in web.categories_from_paths(["prisma/schema.prisma"])


def test_paths_middleware_triggers_auth(web):
    assert "auth" in web.categories_from_paths(["src/middleware.ts"])


def test_paths_tsx_triggers_frontend(web):
    assert "frontend" in web.categories_from_paths(["src/components/x.tsx"])


def test_paths_css_triggers_frontend(web):
    assert "frontend" in web.categories_from_paths(["src/app/globals.css"])


def test_paths_empty_list(web):
    assert web.categories_from_paths([]) == set()


def test_paths_combined_full_stack(web):
    """Multiple paths combine into the union of their categories."""
    cats = web.categories_from_paths([
        "src/app/api/users/route.ts",      # api
        "prisma/schema.prisma",            # database
        "src/middleware.ts",               # auth
        "src/components/user-list.tsx",    # frontend
    ])
    assert cats == {"api", "database", "auth", "frontend"}


# ─── categories_from_change_type ────────────────────────────────────────


def test_change_type_foundational(web):
    assert web.categories_from_change_type("foundational") == {"frontend", "scaffolding"}


def test_change_type_feature(web):
    assert web.categories_from_change_type("feature") == {"frontend"}


def test_change_type_schema(web):
    assert web.categories_from_change_type("schema") == {"database"}


def test_change_type_infrastructure(web):
    assert web.categories_from_change_type("infrastructure") == {"ci-build-test"}


def test_change_type_cleanup(web):
    assert web.categories_from_change_type("cleanup-before") == {"refactor"}
    assert web.categories_from_change_type("cleanup-after") == {"refactor"}


def test_change_type_unknown_returns_empty(web):
    assert web.categories_from_change_type("nonsense") == set()


# ─── categories_from_requirements ───────────────────────────────────────


def test_req_auth_prefix_triggers_auth(web):
    assert "auth" in web.categories_from_requirements(["REQ-AUTH-001"])


def test_req_with_ac_suffix(web):
    assert "auth" in web.categories_from_requirements(["REQ-AUTH-001:AC-1"])


def test_req_api_prefix_triggers_api(web):
    assert "api" in web.categories_from_requirements(["REQ-API-USERS-002"])


def test_req_db_prefix_triggers_database(web):
    assert "database" in web.categories_from_requirements(["REQ-DB-USER-001"])


def test_req_nav_prefix_triggers_frontend(web):
    assert "frontend" in web.categories_from_requirements(["REQ-NAV-007"])


def test_req_test_prefix_triggers_ci_build_test(web):
    assert "ci-build-test" in web.categories_from_requirements(["REQ-TEST-002:AC-1"])


def test_req_payment_prefix_triggers_payment(web):
    assert "payment" in web.categories_from_requirements(["REQ-CART-001", "REQ-CHECKOUT-002"])


def test_req_unknown_prefix_returns_empty(web):
    assert web.categories_from_requirements(["REQ-XYZZY-001"]) == set()


def test_req_multi_category_compound(web):
    """A scope assigned multiple REQs aggregates their domains."""
    cats = web.categories_from_requirements([
        "REQ-AUTH-001", "REQ-API-USERS-002:AC-1", "REQ-NAV-007",
    ])
    assert cats == {"auth", "api", "frontend"}


# ─── category_taxonomy ──────────────────────────────────────────────────


def test_taxonomy_is_documented_set(web):
    assert web.category_taxonomy() == [
        "general", "frontend",
        "auth", "api", "database", "payment",
        "scaffolding", "ci-build-test",
        "refactor", "schema", "i18n",
    ]


def test_taxonomy_includes_general_first(web):
    """Universal baseline must be first per ABC docstring convention."""
    assert web.category_taxonomy()[0] == "general"


# ─── project_summary_for_classifier ─────────────────────────────────────


def test_summary_minimal_project(web, tmp_path):
    """Without package.json, returns generic 'web project.'"""
    summary = web.project_summary_for_classifier(tmp_path)
    assert "web" in summary.lower()


def test_summary_nextjs_project(web, tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"next": "^14", "react": "^18"},
    }))
    assert "Next.js" in web.project_summary_for_classifier(tmp_path)


def test_summary_with_prisma_and_auth(web, tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"next": "^14", "@prisma/client": "^5", "next-auth": "^5"},
    }))
    summary = web.project_summary_for_classifier(tmp_path)
    assert "Next.js" in summary
    assert "Prisma" in summary
    assert "auth-provider" in summary


def test_summary_under_100_chars(web, tmp_path):
    """Token budget on the LLM prompt — keep summary terse."""
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"next": "^14", "@prisma/client": "^5", "next-auth": "^5"},
    }))
    summary = web.project_summary_for_classifier(tmp_path)
    assert len(summary) < 100
