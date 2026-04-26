"""Unit tests for v0 fidelity gate — skeleton check + config + registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass
class FakeRoute:
    path: str
    files: list = field(default_factory=list)
    component_deps: list = field(default_factory=list)
    scope_keywords: list = field(default_factory=list)
    fidelity_threshold: float = None


@dataclass
class FakeManifest:
    routes: list
    shared: list = field(default_factory=list)
    shared_aliases: dict = field(default_factory=dict)
    deferred_design_routes: list = field(default_factory=list)


def _make_agent_tree(root: Path, routes: list[str], shared_files: list[str] = None) -> None:
    """Create a fake agent worktree with Next.js app router."""
    app = root / "app"
    app.mkdir(parents=True, exist_ok=True)
    for rp in routes:
        if rp == "/":
            target = app / "page.tsx"
        else:
            d = app
            for seg in rp.strip("/").split("/"):
                d = d / seg
            d.mkdir(parents=True, exist_ok=True)
            target = d / "page.tsx"
        target.write_text("export default function P(){return null}")
    for sh in shared_files or []:
        target = root / sh
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("export function X(){return null}")


def test_skeleton_check_matching(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()

    _make_agent_tree(agent, ["/", "/kavek"], ["components/ui/button.tsx", "components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/"), FakeRoute("/kavek")],
        shared=[
            "v0-export/components/ui/**",
            "v0-export/components/header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )

    violations = run_skeleton_check(agent, v0, manifest)
    assert violations == []


def test_skeleton_check_missing_route(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/"], ["components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/"), FakeRoute("/kavek")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "missing-route" and "/kavek" in v.detail for v in violations)


def test_skeleton_check_extra_route(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/", "/bonus"], ["components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "extra-route" and "/bonus" in v.detail for v in violations)


def test_skeleton_check_scope_aware_ignores_siblings(tmp_path: Path):
    """A change's skeleton check must not flag routes owned by sibling changes."""
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    # Agent built only admin pages — shop routes belong to a sibling change
    _make_agent_tree(
        agent, ["/", "/admin", "/admin/termekek"],
        ["components/header.tsx", "app/layout.tsx"],
    )
    manifest = FakeManifest(
        routes=[
            FakeRoute("/", scope_keywords=["home"]),
            FakeRoute("/admin", scope_keywords=["admin"]),
            FakeRoute("/admin/termekek", scope_keywords=["admin", "termekek"]),
            FakeRoute("/kosar", scope_keywords=["kosar"]),      # sibling's
            FakeRoute("/penztar", scope_keywords=["penztar"]),  # sibling's
        ],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    scope = "Build admin dashboard and product management (/admin, /admin/termekek)"
    violations = run_skeleton_check(agent, v0, manifest, change_scope=scope)
    # Must NOT flag sibling-owned routes
    assert not any("/kosar" in v.detail for v in violations), violations
    assert not any("/penztar" in v.detail for v in violations), violations


def test_skeleton_check_scope_catches_own_missing(tmp_path: Path):
    """Scope-matched missing routes still fire as violations."""
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/admin"], ["components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[
            FakeRoute("/admin", scope_keywords=["admin"]),
            FakeRoute("/admin/termekek", scope_keywords=["admin", "termekek"]),
        ],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest, change_scope="admin termekek")
    # /admin/termekek must be flagged as missing
    assert any(v.status == "missing-route" and "/admin/termekek" in v.detail for v in violations)


def test_skeleton_check_missing_shared_file(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/"], ["app/layout.tsx"])  # no header.tsx
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "missing-shared-file" and "header.tsx" in v.detail for v in violations)


def test_skeleton_check_alias_tolerance(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/"], ["components/site-header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
        shared_aliases={"header.tsx": "site-header.tsx"},
    )
    violations = run_skeleton_check(agent, v0, manifest)
    # With alias, header.tsx → site-header.tsx should be tolerated
    assert not any("header.tsx" in v.detail for v in violations)


def test_skeleton_check_decomposition_collapsed(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    (agent / "components").mkdir(parents=True)
    # File exists but no export → decomposition collapsed
    (agent / "components" / "header.tsx").write_text("// nothing exported")
    (agent / "app").mkdir()
    (agent / "app" / "layout.tsx").write_text("export default function L(){return null}")
    (agent / "app" / "page.tsx").write_text("export default function P(){return null}")
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "decomposition-collapsed" for v in violations)


def test_gate_registered_in_web_profile():
    from set_project_web.project_type import WebProjectType

    wp = WebProjectType()
    names = [g.name for g in wp.register_gates()]
    assert "design-fidelity" in names


def test_design_fidelity_runs_on_shell_mounting_change_types():
    """Shell-mounting work appears under either `foundational` or
    `infrastructure` change_type depending on planner mood — both classes
    routinely mount site-header, site-footer, theme-provider, etc.
    The gate MUST run on both so structural checks (shell mounting +
    primitive parity) catch stub mounts.

    Witnessed regressions:
    - micro-web-run-20260426-1057: shell-foundation (foundational) merged
      with 3/6 shells; gate was set to "skip" on foundational.
    - micro-web-run-20260426-1127: test-and-layout-foundation
      (infrastructure) merged with 0/2 missing shells (theme-provider,
      mobile-nav) and 4 missing dependencies (next-themes, sonner,
      react-hook-form, zod) — gate was set to "skip" on infrastructure.
    """
    from set_project_web.project_type import WebProjectType

    wp = WebProjectType()
    gate = next(g for g in wp.register_gates() if g.name == "design-fidelity")
    for ct in ("foundational", "infrastructure", "feature"):
        assert gate.defaults.get(ct) == "run", (
            f"design-fidelity gate MUST run on `{ct}` change_type — shell "
            "mounting + primitive parity are validated there. If you need "
            "to skip the visual screenshot diff specifically, factor that "
            "check into a separate gate, but never skip structural checks."
        )


def test_warn_only_flag_read(tmp_path: Path):
    import yaml

    from set_project_web.v0_fidelity_gate import _read_warn_only_flag

    cfg = tmp_path / "set" / "orchestration" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(yaml.safe_dump({"gates": {"design-fidelity": {"warn_only": True}}}))
    assert _read_warn_only_flag(tmp_path) is True
    assert _read_warn_only_flag(tmp_path.parent) is False


# ─── Token guard + className preservation ──────────────────────────

def _init_git_repo(root: Path) -> None:
    """Initialize a tiny git repo with a baseline commit so diff works."""
    import subprocess
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
    (root / "README.md").write_text("x")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)


def _commit_file(root: Path, rel: str, content: str, msg: str) -> None:
    import subprocess
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    subprocess.run(["git", "add", rel], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=root, check=True)


def _head_sha(root: Path) -> str:
    import subprocess
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_token_guard_flags_hex_color(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_token_guard_check

    root = tmp_path / "repo"
    _init_git_repo(root)
    base = _head_sha(root)
    _commit_file(
        root, "src/components/card.tsx",
        'export const C = () => <div style={{background:"#ff00aa"}} />',
        "add card with hex color",
    )
    vs = run_token_guard_check(root, base)
    assert any(v.status == "hardcoded-color" and "card.tsx" in v.detail for v in vs), vs


def test_token_guard_allows_tokens(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_token_guard_check

    root = tmp_path / "repo"
    _init_git_repo(root)
    base = _head_sha(root)
    _commit_file(
        root, "src/components/card.tsx",
        'export const C = () => <div className="bg-primary text-foreground" />',
        "add card with tokens",
    )
    vs = run_token_guard_check(root, base)
    assert not any(v.status == "hardcoded-color" for v in vs)


def test_token_guard_exempts_chart(tmp_path: Path):
    """shadcn's canonical chart.tsx ships literal CSS vars — not a violation."""
    from set_project_web.v0_fidelity_gate import run_token_guard_check

    root = tmp_path / "repo"
    _init_git_repo(root)
    base = _head_sha(root)
    _commit_file(
        root, "src/components/ui/chart.tsx",
        'export const C = () => <style>{`:root { --primary: #abc123; }`}</style>',
        "add canonical chart",
    )
    vs = run_token_guard_check(root, base)
    assert not any(v.status == "hardcoded-color" for v in vs)


def test_classname_preservation_detects_rewrite(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_classname_preservation_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    # v0 has a button with rich Tailwind tokens
    (v0 / "components").mkdir(parents=True)
    (v0 / "components" / "btn.tsx").write_text(
        'export const B = () => <button className="rounded-lg bg-primary '
        'text-primary-foreground px-4 py-2 hover:bg-primary/90 '
        'focus-visible:ring-2 focus-visible:ring-ring shadow-sm '
        'transition-colors inline-flex items-center" />'
    )
    # Agent "rewrote" — only 1 token overlap
    (agent / "src" / "components").mkdir(parents=True)
    (agent / "src" / "components" / "btn.tsx").write_text(
        'export const B = () => <button className="my-custom-btn alt-style" />'
    )
    manifest = FakeManifest(
        routes=[FakeRoute(
            "/x", component_deps=["v0-export/components/btn.tsx"],
            scope_keywords=["x"],
        )],
    )
    vs = run_classname_preservation_check(agent, v0, manifest, change_scope="x")
    assert any(v.status == "classname-rewritten" and "btn.tsx" in v.detail for v in vs), vs


def test_classname_preservation_allows_mostly_kept(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_classname_preservation_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    (v0 / "components").mkdir(parents=True)
    (v0 / "components" / "btn.tsx").write_text(
        'export const B = () => <button className="rounded-lg bg-primary '
        'text-primary-foreground px-4 py-2 hover:bg-primary/90" />'
    )
    (agent / "src" / "components").mkdir(parents=True)
    (agent / "src" / "components" / "btn.tsx").write_text(
        'export const B = () => <button className="rounded-lg bg-primary '
        'text-primary-foreground px-4 py-2 hover:bg-primary/90 " />'
    )
    manifest = FakeManifest(
        routes=[FakeRoute(
            "/x", component_deps=["v0-export/components/btn.tsx"],
            scope_keywords=["x"],
        )],
    )
    vs = run_classname_preservation_check(agent, v0, manifest, change_scope="x")
    assert not vs


def test_classname_preservation_credits_shadcn_imports(tmp_path: Path):
    """Using <Button>/<Card> shadcn components should count as preserved tokens."""
    from set_project_web.v0_fidelity_gate import run_classname_preservation_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"

    # v0 has inline Tailwind soup
    (v0 / "components").mkdir(parents=True)
    (v0 / "components" / "btn.tsx").write_text(
        'export const B = () => <button className="rounded-lg bg-primary '
        'text-primary-foreground px-4 py-2 hover:bg-primary/90 '
        'focus-visible:ring-2 focus-visible:ring-ring shadow-sm '
        'transition-colors inline-flex items-center" />'
    )
    # Agent rewrites using <Button> from shadcn — own file has FEW tokens
    (agent / "src" / "components").mkdir(parents=True)
    (agent / "src" / "components" / "btn.tsx").write_text(
        'import { Button } from "@/components/ui/button"\n'
        'export const B = () => <Button>X</Button>'
    )
    # The shadcn Button ships the class vocabulary v0 inlined
    (agent / "src" / "components" / "ui").mkdir(parents=True, exist_ok=True)
    (agent / "src" / "components" / "ui" / "button.tsx").write_text(
        'export const Button = ({children}) => <button className='
        '"rounded-lg bg-primary text-primary-foreground px-4 py-2 '
        'hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring '
        'shadow-sm transition-colors inline-flex items-center">{children}</button>'
    )
    manifest = FakeManifest(
        routes=[FakeRoute(
            "/x", component_deps=["v0-export/components/btn.tsx"],
            scope_keywords=["x"],
        )],
    )
    vs = run_classname_preservation_check(agent, v0, manifest, change_scope="x")
    # Must NOT flag: the agent uses shadcn Button which contains the tokens
    assert not vs, vs


def test_deferred_design_routes_accepts_dict_entries(tmp_path: Path):
    """Schema declares list[dict] for deferred_design_routes; check must not crash."""
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/"], ["components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/", scope_keywords=["home"]), FakeRoute("/zzz", scope_keywords=["zzz"])],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
        deferred_design_routes=[{"route": "/zzz", "reason": "not yet implemented"}],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    # /zzz is deferred → must not fire as missing-route
    assert not any("/zzz" in v.detail for v in violations), violations


def test_classname_extract_includes_cva_base(tmp_path: Path):
    """Shadcn cva(...) first-arg class string must be captured."""
    from set_project_web.v0_fidelity_gate import _extract_classname_tokens

    text = (
        'const buttonVariants = cva('
        '  "inline-flex items-center justify-center rounded-md gap-2",'
        '  { variants: { size: { default: "h-9 px-4" } } }'
        ')'
    )
    toks = _extract_classname_tokens(text)
    assert "inline-flex" in toks
    assert "items-center" in toks
    assert "rounded-md" in toks


def test_classname_token_includes_bracket_modifier(tmp_path: Path):
    """`text-[1.125rem]` should be one token, not split on `.`."""
    from set_project_web.v0_fidelity_gate import _extract_classname_tokens

    toks = _extract_classname_tokens('<div className="text-[1.125rem] leading-[1.5]" />')
    assert "text-[1.125rem]" in toks
    assert "leading-[1.5]" in toks


# ─── design-fidelity-shell-hardening: stricter shell mounting ───────────


def _make_shell_test_layout(tmp_path: Path):
    """Build a fake worktree + v0-export with one shell that requires mounting."""
    agent = tmp_path / "agent"
    v0 = tmp_path / "agent" / "v0-export"
    (v0 / "components").mkdir(parents=True)
    # Realistic v0 shell with multiple shadcn imports
    (v0 / "components" / "site-header.tsx").write_text(
        "import { Button } from '@/components/ui/button'\n"
        "import { CommandDialog, CommandInput } from '@/components/ui/command'\n"
        "export function SiteHeader() { return <header /> }\n"
    )
    (v0 / "app").mkdir(parents=True)
    (v0 / "app" / "layout.tsx").write_text("export default function L(){return null}")
    (agent / "app").mkdir(parents=True, exist_ok=True)
    (agent / "app" / "page.tsx").write_text("export default function P(){return null}")
    (agent / "app" / "layout.tsx").write_text("export default function L(){return null}")
    return agent, v0


def test_shell_mounting_missing_canonical_filename(tmp_path: Path):
    """If v0 has site-header.tsx but src/components/ has only Navbar.tsx
    (different name), the gate must emit shell-not-mounted (CRITICAL/blocking).
    """
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent, v0 = _make_shell_test_layout(tmp_path)
    src_components = agent / "src" / "components"
    src_components.mkdir(parents=True)
    # Agent created their own custom Navbar.tsx (PascalCase) — the exact
    # craftbrew-run-20260425-2328 failure pattern
    (src_components / "Navbar.tsx").write_text(
        "import { Button } from '@/components/ui/button'\n"
        "export function Navbar() { return <nav /> }\n"
    )

    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=[
            "v0-export/components/site-header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "shell-not-mounted" for v in violations), \
        f"Expected shell-not-mounted, got: {[(v.status, v.detail) for v in violations]}"


def test_shell_mounting_shadow_alias_blocks(tmp_path: Path):
    """If src/components/site-header.tsx exists but only re-exports a sibling
    local Navbar.tsx, the gate must emit shadow-alias (CRITICAL/blocking).
    This is the exact pattern from craftbrew-run-20260425-2328.
    """
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent, v0 = _make_shell_test_layout(tmp_path)
    src_components = agent / "src" / "components"
    src_components.mkdir(parents=True)
    (src_components / "Navbar.tsx").write_text(
        "export function Navbar() { return <nav /> }\n"
    )
    # The shadow-alias trick — site-header.tsx exists but only re-exports Navbar
    (src_components / "site-header.tsx").write_text(
        'import { Navbar } from "./Navbar";\n'
        '// Manifest shell mounts here.\n'
        'export const SiteHeader = Navbar;\n'
        'export default SiteHeader;\n'
    )

    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=[
            "v0-export/components/site-header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "shadow-alias" for v in violations), \
        f"Expected shadow-alias, got: {[(v.status, v.detail) for v in violations]}"


def test_shell_mounting_v0_reexport_passes(tmp_path: Path):
    """A re-export from `@/v0-export/components/X` is a LEGITIMATE shell mount
    pattern and must NOT be flagged as shadow-alias.
    """
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent, v0 = _make_shell_test_layout(tmp_path)
    src_components = agent / "src" / "components"
    src_components.mkdir(parents=True)
    # Legitimate re-export from v0-export
    (src_components / "site-header.tsx").write_text(
        "export { SiteHeader } from '@/v0-export/components/site-header';\n"
        "export { default } from '@/v0-export/components/site-header';\n"
    )

    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=[
            "v0-export/components/site-header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert not any(v.status == "shadow-alias" for v in violations), \
        f"Legitimate v0 re-export should pass; got: {[(v.status, v.detail) for v in violations]}"
    assert not any(v.status == "shell-not-mounted" for v in violations)


def test_shell_mounting_forked_content_passes(tmp_path: Path):
    """A forked v0 shell (copy-paste of the v0 content into src/components/)
    is a LEGITIMATE pattern. The file has real implementation lines, even
    though it imports siblings, so shadow-alias must NOT fire.
    """
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent, v0 = _make_shell_test_layout(tmp_path)
    src_components = agent / "src" / "components"
    src_components.mkdir(parents=True)
    (src_components / "site-header.tsx").write_text(
        'import { Button } from "@/components/ui/button";\n'
        'import { Logo } from "./logo";\n'
        'export function SiteHeader() {\n'
        '  return (\n'
        '    <header className="border-b">\n'
        '      <Logo />\n'
        '      <nav>\n'
        '        <Button>Sign in</Button>\n'
        '      </nav>\n'
        '    </header>\n'
        '  );\n'
        '}\n'
    )
    (src_components / "logo.tsx").write_text(
        'export function Logo() { return <span>Brand</span> }\n'
    )

    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=[
            "v0-export/components/site-header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert not any(v.status == "shadow-alias" for v in violations), \
        f"Forked v0 shell should pass; got: {[(v.status, v.detail) for v in violations]}"


def test_shell_mounting_alias_override_skips(tmp_path: Path):
    """Operators can waive a specific shell via shared_aliases — that path
    should skip both shell-not-mounted and shadow-alias checks.
    """
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent, v0 = _make_shell_test_layout(tmp_path)
    src_components = agent / "src" / "components"
    src_components.mkdir(parents=True)
    (src_components / "Navbar.tsx").write_text("export function Navbar() {}\n")
    # No site-header.tsx at all — but the alias whitelists it

    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=[
            "v0-export/components/site-header.tsx",
            "v0-export/app/layout.tsx",
        ],
        shared_aliases={"site-header.tsx": "Navbar.tsx"},
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert not any(v.status == "shell-not-mounted" for v in violations)
    assert not any(v.status == "shadow-alias" for v in violations)


# ─── design-fidelity-shell-hardening: shadcn primitive parity ────────────


def test_shadcn_primitive_parity_command_dialog_missing(tmp_path: Path):
    """If v0 uses CommandDialog but no src/ file imports it, the gate must
    emit shadcn-primitive-missing (WARN, non-blocking)."""
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent, v0 = _make_shell_test_layout(tmp_path)
    src_components = agent / "src" / "components"
    src_components.mkdir(parents=True)
    # Mount the shell properly so other checks pass
    (src_components / "site-header.tsx").write_text(
        "export { default } from '@/v0-export/components/site-header';\n"
    )
    # Implementation doesn't import CommandDialog anywhere
    (agent / "src" / "app").mkdir(parents=True, exist_ok=True)
    (agent / "src" / "app" / "page.tsx").write_text(
        "import { Card } from '@/components/ui/card'\n"
        "export default function Page() { return <Card>hi</Card> }\n"
    )

    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=[
            "v0-export/components/site-header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    cd_violations = [v for v in violations if v.status == "shadcn-primitive-missing"]
    assert cd_violations, \
        f"Expected shadcn-primitive-missing, got: {[(v.status, v.detail) for v in violations]}"
    # Should specifically call out CommandDialog
    assert any("CommandDialog" in v.detail for v in cd_violations)


def test_shadcn_primitive_parity_present_in_src_passes(tmp_path: Path):
    """If v0 uses CommandDialog AND some src/ file imports it, no violation."""
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent, v0 = _make_shell_test_layout(tmp_path)
    src_components = agent / "src" / "components"
    src_components.mkdir(parents=True)
    (src_components / "site-header.tsx").write_text(
        "export { default } from '@/v0-export/components/site-header';\n"
    )
    # Implementation DOES import CommandDialog and CommandInput
    (agent / "src" / "app").mkdir(parents=True, exist_ok=True)
    (agent / "src" / "app" / "page.tsx").write_text(
        "import { CommandDialog, CommandInput } from '@/components/ui/command'\n"
        "export default function Page() { return <CommandDialog open={false} /> }\n"
    )

    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=[
            "v0-export/components/site-header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert not any(v.status == "shadcn-primitive-missing" for v in violations), \
        f"CommandDialog is imported in src/, should pass; got: {[(v.status, v.detail) for v in violations]}"


def test_is_shadow_alias_pattern_detection():
    """Direct unit test of _is_shadow_alias pattern recognition."""
    from set_project_web.v0_fidelity_gate import _is_shadow_alias

    # Pattern 1: export const X = Y where Y from sibling
    assert _is_shadow_alias(
        'import { Navbar } from "./Navbar";\n'
        'export const SiteHeader = Navbar;\n'
        'export default SiteHeader;\n'
    )

    # Pattern 2: export default Y where Y from sibling
    assert _is_shadow_alias(
        'import Foo from "./Foo";\n'
        'export default Foo;\n'
    )

    # Pattern 3: re-export from v0-export — NOT a shadow alias
    assert not _is_shadow_alias(
        "export { default } from '@/v0-export/components/site-header';\n"
    )

    # Pattern 4: real implementation that imports a sibling but has logic
    assert not _is_shadow_alias(
        'import { Logo } from "./Logo";\n'
        'import { Button } from "@/components/ui/button";\n'
        'export function SiteHeader() {\n'
        '  return (\n'
        '    <header>\n'
        '      <Logo />\n'
        '      <Button>Sign in</Button>\n'
        '    </header>\n'
        '  );\n'
        '}\n'
    )
