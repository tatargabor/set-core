"""Regression tests for ``required_components_gate``.

Witnessed in ``micro-web-run-20260426-1704`` contact-wizard-form: the
agent built ``src/components/contact-wizard.tsx`` (557 lines, all
testids, full shadcn composition) but ``src/app/contact/page.tsx``
stayed at ``<h1>Contact</h1>`` — never mounted ``ContactDialogTrigger``.
The dispatcher's "Required components / JSX (must be imported and
rendered)" promise was aspirational only; no gate enforced it. Result:
white screenshot in production, $120+ of agent fix-loop wasted.

These tests pin the gate's behavior so the missing-mount class of
failure can never reach merge again.
"""

from __future__ import annotations

import pytest

from set_project_web.required_components_gate import (
    _extract_required_components,
    _is_definition_file,
    _is_jsx_used,
    execute_required_components_gate,
)


class _MockChange:
    def __init__(self, scope: str = ""):
        self.scope = scope


# ─── _extract_required_components ───────────────────────────────────────


def test_extracts_pascal_case_jsx_tags():
    scope = (
        "wrap children in <ThemeProvider attribute='class'> and render "
        "<SiteHeader/>{children}<SiteFooter/><Toaster />"
    )
    components = _extract_required_components(scope)
    assert "ThemeProvider" in components
    assert "SiteHeader" in components
    assert "SiteFooter" in components
    # Toaster is library-component → filtered out
    assert "Toaster" not in components


def test_drops_library_primitives():
    """shadcn/lucide primitives are filtered — they compose inside
    feature components, no top-level mount required."""
    scope = "<Button> in <Card><Avatar/></Card> with <Menu/> icon"
    components = _extract_required_components(scope)
    assert components == []


def test_keeps_project_specific_components():
    scope = "Mount <ContactDialogTrigger/> on /contact route + <CommandPalette/>"
    components = _extract_required_components(scope)
    assert "ContactDialogTrigger" in components
    assert "CommandPalette" in components


def test_dedups_repeated_mentions():
    scope = "<Foo> twice: <Foo> and <Foo />"
    assert _extract_required_components(scope) == ["Foo"]


def test_strips_closing_tags():
    """``</Foo>`` should be deduped against ``<Foo>``, not double-counted."""
    scope = "<Foo>content</Foo>"
    assert _extract_required_components(scope) == ["Foo"]


def test_empty_scope_returns_empty():
    assert _extract_required_components("") == []
    assert _extract_required_components("plain text no jsx") == []


# ─── _is_definition_file / _is_jsx_used ─────────────────────────────────


def test_is_definition_named_export():
    content = "export function ContactDialogTrigger() { return <button/>; }"
    assert _is_definition_file(content, "ContactDialogTrigger")
    assert not _is_definition_file(content, "Other")


def test_is_definition_const_export():
    content = "export const SiteHeader = () => <header />"
    assert _is_definition_file(content, "SiteHeader")


def test_is_definition_default_export():
    content = "function MyPage() {}\nexport default MyPage;"
    assert _is_definition_file(content, "MyPage")


def test_is_definition_named_braces():
    content = "function Foo() {}\nexport { Foo, Bar };"
    assert _is_definition_file(content, "Foo")
    assert _is_definition_file(content, "Bar")


def test_is_jsx_used_self_closing():
    content = "return <ContactDialogTrigger />;"
    assert _is_jsx_used(content, "ContactDialogTrigger")


def test_is_jsx_used_with_children():
    content = "<ContactDialogTrigger>click me</ContactDialogTrigger>"
    assert _is_jsx_used(content, "ContactDialogTrigger")


def test_is_jsx_used_with_props():
    content = "<ContactDialogTrigger className='foo' onClick={fn} />"
    assert _is_jsx_used(content, "ContactDialogTrigger")


def test_is_jsx_used_word_boundary():
    """``<Toaster>`` should NOT match ``<ToasterPortal>``."""
    content = "<ToasterPortal />"
    assert not _is_jsx_used(content, "Toaster")


def test_is_jsx_used_negative():
    content = "import { ContactDialogTrigger } from './foo'; export const X = 1;"
    assert not _is_jsx_used(content, "ContactDialogTrigger")


# ─── Gate end-to-end ────────────────────────────────────────────────────


def _setup_worktree(tmp_path):
    """Create a minimal Next.js-ish src/ tree."""
    (tmp_path / "src" / "app" / "contact").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)
    return tmp_path


def test_gate_skipped_when_no_worktree():
    change = _MockChange(scope="<Foo />")
    result = execute_required_components_gate("ch", change, "")
    assert result.status == "skipped"


def test_gate_skipped_when_no_components_in_scope(tmp_path):
    _setup_worktree(tmp_path)
    change = _MockChange(scope="just plain text")
    result = execute_required_components_gate("ch", change, str(tmp_path))
    assert result.status == "skipped"


def test_gate_skipped_when_no_src_tsx(tmp_path):
    """No src/ → can't enforce mount; pass-through."""
    change = _MockChange(scope="<Foo />")
    result = execute_required_components_gate("ch", change, str(tmp_path))
    assert result.status == "skipped"


def test_gate_witnessed_failure_caught(tmp_path):
    """Reproduces ``contact-wizard-form``: component defined, never mounted."""
    p = _setup_worktree(tmp_path)
    # Component defined here
    (p / "src" / "components" / "contact-wizard.tsx").write_text(
        "export function ContactDialogTrigger() { return <button>Open</button>; }\n"
    )
    # Page does NOT mount it (the bug)
    (p / "src" / "app" / "contact" / "page.tsx").write_text(
        "export default function ContactPage() { return <h1>Contact</h1>; }\n"
    )
    change = _MockChange(scope="Mount <ContactDialogTrigger /> on /contact")

    result = execute_required_components_gate("contact-wizard", change, str(p))

    assert result.status == "fail"
    assert "ContactDialogTrigger" in result.output
    assert "ContactDialogTrigger" in (result.retry_context or "")
    assert result.stats["missing_mounts"] == ["ContactDialogTrigger"]


def test_gate_passes_when_component_mounted(tmp_path):
    """Same setup as above but page does mount the component → pass."""
    p = _setup_worktree(tmp_path)
    (p / "src" / "components" / "contact-wizard.tsx").write_text(
        "export function ContactDialogTrigger() { return <button>Open</button>; }\n"
    )
    (p / "src" / "app" / "contact" / "page.tsx").write_text(
        "import { ContactDialogTrigger } from '@/components/contact-wizard';\n"
        "export default function ContactPage() {\n"
        "  return <ContactDialogTrigger />;\n"
        "}\n"
    )
    change = _MockChange(scope="Mount <ContactDialogTrigger /> on /contact")

    result = execute_required_components_gate("contact-wizard", change, str(p))

    assert result.status == "pass"
    assert "ContactDialogTrigger" in result.stats["found_mounts"]


def test_gate_definition_file_self_reference_does_not_count(tmp_path):
    """A component referenced ONLY in its own definition file (e.g. via
    return statement) is not considered mounted."""
    p = _setup_worktree(tmp_path)
    (p / "src" / "components" / "self.tsx").write_text(
        "export function Self() {\n"
        "  return <div>I am <Self /></div>;  // recursive ref\n"
        "}\n"
    )
    change = _MockChange(scope="Mount <Self />")

    result = execute_required_components_gate("ch", change, str(p))

    assert result.status == "fail"
    assert "Self" in result.stats["missing_mounts"]


def test_gate_skips_v0_export_directory(tmp_path):
    """v0-export/ is a read-only design source — usage there doesn't
    count as the agent mounting the component."""
    p = _setup_worktree(tmp_path)
    (p / "src" / "components" / "wizard.tsx").write_text(
        "export function Wizard() { return <div/>; }"
    )
    (p / "v0-export" / "app" / "contact").mkdir(parents=True)
    (p / "v0-export" / "app" / "contact" / "page.tsx").write_text(
        "import { Wizard } from '@/components/wizard'\n"
        "export default function() { return <Wizard /> }\n"
    )
    # Agent's actual page does NOT mount it
    (p / "src" / "app" / "contact" / "page.tsx").write_text(
        "export default function ContactPage() { return <h1>Contact</h1>; }\n"
    )
    change = _MockChange(scope="Mount <Wizard />")

    result = execute_required_components_gate("ch", change, str(p))

    # v0-export usage doesn't satisfy → still missing
    assert result.status == "fail"
    assert "Wizard" in result.stats["missing_mounts"]


def test_gate_skips_test_directories(tmp_path):
    """Test files don't count as production mount sites."""
    p = _setup_worktree(tmp_path)
    (p / "src" / "components" / "wizard.tsx").write_text(
        "export function Wizard() { return <div/>; }"
    )
    (p / "src" / "app" / "contact" / "page.tsx").write_text(
        "export default function ContactPage() { return <h1>Contact</h1>; }\n"
    )
    (p / "tests").mkdir()
    (p / "tests" / "wizard.test.tsx").write_text(
        "import { Wizard } from '@/components/wizard';\n"
        "test('renders', () => { render(<Wizard />); });\n"
    )
    change = _MockChange(scope="<Wizard />")

    result = execute_required_components_gate("ch", change, str(p))

    # Test usage doesn't count → still missing
    assert result.status == "fail"


def test_gate_library_components_skipped_silently(tmp_path):
    """If scope mentions only library components, gate skips entirely."""
    p = _setup_worktree(tmp_path)
    change = _MockChange(scope="Render <Button>Click</Button> with <Menu/> icon")

    result = execute_required_components_gate("ch", change, str(p))
    assert result.status == "skipped"


def test_gate_skips_undefined_components_to_avoid_false_positives(tmp_path):
    """If a scope-mentioned component has NO definition in src/, we
    don't enforce — could be an external library import we couldn't
    classify upfront. Build gate would catch real missing imports."""
    p = _setup_worktree(tmp_path)
    (p / "src" / "app" / "page.tsx").write_text(
        "export default function() { return <h1>Home</h1>; }"
    )
    change = _MockChange(scope="Mount <UnknownLibComponent />")

    result = execute_required_components_gate("ch", change, str(p))

    # No definition → no enforcement; skipped category in stats
    assert result.status == "pass"  # nothing to fail on
    assert "UnknownLibComponent" in result.stats["skipped_library"]


def test_gate_multiple_components_partial_failure(tmp_path):
    """Some mounted, some missing → report only the missing ones."""
    p = _setup_worktree(tmp_path)
    (p / "src" / "components" / "header.tsx").write_text(
        "export function SiteHeader() { return <header/>; }"
    )
    (p / "src" / "components" / "footer.tsx").write_text(
        "export function SiteFooter() { return <footer/>; }"
    )
    (p / "src" / "app" / "layout.tsx").write_text(
        "import { SiteHeader } from '@/components/header';\n"
        "export default function() { return <SiteHeader />; }\n"
    )
    change = _MockChange(scope="<SiteHeader/>{children}<SiteFooter/>")

    result = execute_required_components_gate("ch", change, str(p))

    assert result.status == "fail"
    assert result.stats["missing_mounts"] == ["SiteFooter"]
    assert "SiteHeader" in result.stats["found_mounts"]
