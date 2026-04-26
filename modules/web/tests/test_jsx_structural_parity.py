"""Tests for `_extract_jsx_signature` and `_check_jsx_structural_parity`.

These checks catch JSX structural drift that the existing checks miss:

- `_check_shell_mounting` only verifies file existence at canonical paths
- `_check_shadcn_primitive_parity` only verifies imports
- `run_token_guard_check` only verifies hex/rgb literals

None of those catch *structural* divergence: same primitives imported,
files mounted at right paths, but the JSX is composed differently. The
canonical witnessed regression is `blog-list-and-data` from
`micro-web-run-20260426-1302`:

  v0 `app/blog/page.tsx`             agent `src/components/blog-list.tsx`
  - 2 CommandGroups (Categories,    - 1 CommandGroup (Categories only)
    Posts)
  - `space-y-6` post list           - `grid grid-cols-3` post grid
  - HoverCardTrigger contains       - HoverCardTrigger contains
    `<Avatar>` + `<span>`             only `<button>` (no Avatar)

All three differences pass shell mounting + primitive parity + token
guard checks today, yet they are unmistakable design regressions. This
gate's job is to reject them before merge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from set_project_web.v0_fidelity_gate import (
    _check_jsx_structural_parity,
    _extract_jsx_signature,
)


# ─── _extract_jsx_signature ─────────────────────────────────────────────


def test_signature_counts_pascalcase_elements():
    """Every `<PascalCase>` element appears in `element_counts`."""
    src = """
    export function X() {
      return <Card><CardHeader><CardTitle>Hi</CardTitle></CardHeader></Card>
    }
    """
    sig = _extract_jsx_signature(src)
    assert sig["element_counts"]["Card"] == 1
    assert sig["element_counts"]["CardHeader"] == 1
    assert sig["element_counts"]["CardTitle"] == 1


def test_signature_ignores_lowercase_html():
    """`<div>`, `<button>`, `<span>` are HTML — not user/library components."""
    src = "<div><button><span>x</span></button></div>"
    sig = _extract_jsx_signature(src)
    assert "div" not in sig["element_counts"]
    assert "button" not in sig["element_counts"]
    assert "span" not in sig["element_counts"]


def test_signature_extracts_layout_classes():
    """Layout-determining classes (grid, flex, space-y, grid-cols-N) end up
    in `layout_classes`. Spacing variants (space-y-6 vs space-y-4) are
    normalized so equivalent layouts don't drift on number tweaks. Column
    counts (grid-cols-3) keep their version since they're visually
    distinct."""
    src = '''
      <div className="grid grid-cols-3 gap-6 mt-8">x</div>
      <div className="flex flex-col space-y-4">y</div>
    '''
    sig = _extract_jsx_signature(src)
    layout = sig["layout_classes"]
    assert "grid" in layout
    assert "grid-cols-3" in layout  # column count kept
    assert "gap" in layout
    assert "flex" in layout
    assert "flex-col" in layout
    assert "space-y" in layout  # version stripped


def test_signature_extracts_command_group_headings():
    """`<CommandGroup heading="Categories">` headings are captured —
    detects the witnessed `Categories+Posts` → `Categories` regression."""
    src = '''
      <CommandGroup heading="Categories">...</CommandGroup>
      <CommandGroup heading="Recent posts">...</CommandGroup>
      <CommandGroup heading="Theme">...</CommandGroup>
    '''
    sig = _extract_jsx_signature(src)
    assert sig["command_group_headings"] == {"Categories", "Recent posts", "Theme"}


def test_signature_extracts_anchor_inner_elements():
    """For trigger-style elements (HoverCardTrigger, PopoverTrigger,
    SheetTrigger), capture the set of element types appearing inside —
    detects the witnessed `Avatar inside HoverCardTrigger` → `(none)`
    regression."""
    src = '''
      <HoverCardTrigger asChild>
        <button>
          <Avatar><AvatarFallback>X</AvatarFallback></Avatar>
          <span>Name</span>
        </button>
      </HoverCardTrigger>
      <SheetTrigger>
        <Button><Menu /></Button>
      </SheetTrigger>
    '''
    sig = _extract_jsx_signature(src)
    assert "Avatar" in sig["anchor_inner"]["HoverCardTrigger"]
    assert "AvatarFallback" in sig["anchor_inner"]["HoverCardTrigger"]
    assert "Button" in sig["anchor_inner"]["SheetTrigger"]


def test_signature_self_closing_elements():
    """Self-closing elements (`<Toaster />`) count as one occurrence."""
    src = '<><Toaster /><ThemeProvider /><Sonner /></>'
    sig = _extract_jsx_signature(src)
    assert sig["element_counts"]["Toaster"] == 1
    assert sig["element_counts"]["ThemeProvider"] == 1
    assert sig["element_counts"]["Sonner"] == 1


def test_signature_handles_multiline_jsx():
    """Real-world JSX spans many lines per element."""
    src = '''
      <Popover
        open={open}
        onOpenChange={setOpen}
      >
        <PopoverTrigger asChild>
          <Button variant="outline">Trigger</Button>
        </PopoverTrigger>
      </Popover>
    '''
    sig = _extract_jsx_signature(src)
    assert sig["element_counts"]["Popover"] == 1
    assert sig["element_counts"]["PopoverTrigger"] == 1
    assert sig["element_counts"]["Button"] == 1


# ─── _check_jsx_structural_parity ───────────────────────────────────────


def test_parity_blog_list_regression(tmp_path: Path):
    """Reproduce the witnessed blog-list regression and verify it gets
    flagged. v0 has 2 CommandGroups + space-y layout + Avatar in
    HoverCardTrigger; agent has 1 CommandGroup + grid layout + no
    Avatar in trigger."""
    v0 = tmp_path / "v0-export"
    agent = tmp_path / "src"
    (v0 / "app" / "blog").mkdir(parents=True)
    (v0 / "components").mkdir(parents=True)
    (agent / "components").mkdir(parents=True)
    (agent / "app" / "blog").mkdir(parents=True)

    (v0 / "app" / "blog" / "page.tsx").write_text('''
      "use client"
      export default function BlogPage() {
        return (
          <main>
            <Popover>
              <PopoverTrigger><Button /></PopoverTrigger>
              <PopoverContent>
                <Command>
                  <CommandInput />
                  <CommandList>
                    <CommandEmpty>None</CommandEmpty>
                    <CommandGroup heading="Categories"><CommandItem /></CommandGroup>
                    <CommandGroup heading="Posts"><CommandItem /></CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            <div className="mt-8 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle><Link>T</Link></CardTitle>
                  <Badge>cat</Badge>
                </CardHeader>
                <CardContent>
                  <HoverCard>
                    <HoverCardTrigger>
                      <button>
                        <Avatar><AvatarFallback>A</AvatarFallback></Avatar>
                        <span>Name</span>
                      </button>
                    </HoverCardTrigger>
                    <HoverCardContent>
                      <Avatar><AvatarFallback>A</AvatarFallback></Avatar>
                    </HoverCardContent>
                  </HoverCard>
                </CardContent>
              </Card>
            </div>
          </main>
        )
      }
    ''')

    (agent / "app" / "blog" / "page.tsx").write_text('''
      import { BlogList } from "@/components/blog-list"
      export default function BlogPage() {
        return <main><BlogList posts={[]} /></main>
      }
    ''')
    (agent / "components" / "blog-list.tsx").write_text('''
      "use client"
      export function BlogList() {
        return (
          <div>
            <Popover>
              <PopoverTrigger><Button /></PopoverTrigger>
              <PopoverContent>
                <Command>
                  <CommandInput />
                  <CommandList>
                    <CommandEmpty>None</CommandEmpty>
                    <CommandGroup heading="Categories"><CommandItem /></CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle><Link>T</Link></CardTitle>
                  <Badge>cat</Badge>
                </CardHeader>
                <CardContent>
                  <HoverCard>
                    <HoverCardTrigger>
                      <button>Name</button>
                    </HoverCardTrigger>
                    <HoverCardContent>
                      <Avatar><AvatarFallback>A</AvatarFallback></Avatar>
                    </HoverCardContent>
                  </HoverCard>
                </CardContent>
              </Card>
            </div>
          </div>
        )
      }
    ''')

    violations = _check_jsx_structural_parity(agent_worktree=tmp_path, v0_export=v0)

    statuses = [v.status for v in violations]
    messages = "\n".join(v.detail for v in violations)

    # Expect a CommandGroup-headings violation (v0 has Categories+Posts,
    # agent has Categories only)
    assert "jsx-command-group-missing" in statuses, (
        f"expected jsx-command-group-missing — got: {statuses}\n{messages}"
    )
    assert "Posts" in messages, (
        "violation should mention the missing 'Posts' heading"
    )

    # Expect a layout-class violation (v0 has space-y, agent has grid)
    assert "jsx-layout-divergence" in statuses, (
        f"expected jsx-layout-divergence — got: {statuses}"
    )

    # Expect an anchor-inner violation (v0 has Avatar in HoverCardTrigger,
    # agent doesn't)
    assert "jsx-anchor-inner-divergence" in statuses, (
        f"expected jsx-anchor-inner-divergence — got: {statuses}"
    )
    assert "Avatar" in messages, (
        "anchor-inner violation should mention Avatar"
    )
    assert "HoverCardTrigger" in messages


def test_parity_clean_implementation(tmp_path: Path):
    """When agent reproduces v0 structure faithfully, no violations."""
    v0 = tmp_path / "v0-export"
    agent = tmp_path / "src"
    (v0 / "components").mkdir(parents=True)
    (agent / "components").mkdir(parents=True)

    src = '''
      "use client"
      export function X() {
        return (
          <Popover>
            <PopoverTrigger>
              <Button><Avatar /></Button>
            </PopoverTrigger>
            <PopoverContent>
              <Command>
                <CommandGroup heading="Categories"><CommandItem /></CommandGroup>
                <CommandGroup heading="Posts"><CommandItem /></CommandGroup>
              </Command>
            </PopoverContent>
          </Popover>
        )
      }
    '''
    (v0 / "components" / "x.tsx").write_text(src)
    (agent / "components" / "x.tsx").write_text(src)

    violations = _check_jsx_structural_parity(agent_worktree=tmp_path, v0_export=v0)
    assert violations == [], (
        f"clean copy should yield no violations; got: "
        f"{[v.status + ': ' + v.detail for v in violations]}"
    )


def test_parity_skips_ui_directory(tmp_path: Path):
    """`src/components/ui/` is the shadcn primitives library — its
    contents are vendored upstream and should NOT be compared. Only
    application code under src/{app,components} is checked."""
    v0 = tmp_path / "v0-export"
    agent = tmp_path / "src"
    (v0 / "components" / "ui").mkdir(parents=True)
    (agent / "components" / "ui").mkdir(parents=True)

    # v0 has an extra <Tooltip /> in its primitives — agent shouldn't
    # be flagged for this.
    (v0 / "components" / "ui" / "tooltip.tsx").write_text(
        'export function Tooltip() { return <Popover><Custom /></Popover> }'
    )
    # No corresponding agent file in ui/ — should be ignored.

    violations = _check_jsx_structural_parity(agent_worktree=tmp_path, v0_export=v0)
    assert violations == []


def test_parity_no_v0_export_returns_empty(tmp_path: Path):
    """No v0-export → nothing to check against → no violations."""
    agent = tmp_path / "src"
    agent.mkdir()
    violations = _check_jsx_structural_parity(
        agent_worktree=tmp_path, v0_export=tmp_path / "missing-v0",
    )
    assert violations == []
