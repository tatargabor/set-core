"""Required-components mount gate (web module).

For each ``<PascalCase>`` JSX tag mentioned in the change scope (the
"Required components / JSX (must be imported and rendered)" entries
the dispatcher surfaces in input.md), verify the worktree actually
mounts it: at least one ``.tsx``/``.jsx`` file under ``src/`` other
than the component's own definition file references it as JSX.

Witnessed in ``micro-web-run-20260426-1704`` contact-wizard-form: the
agent built ``src/components/contact-wizard.tsx`` with all 557 lines
of the component (``ContactDialogTrigger``, ``ContactWizardDialog``,
shadcn primitives, testids), but ``src/app/contact/page.tsx`` was
just ``<h1>Contact</h1>``. The dispatcher had told the agent both
``<ContactDialogTrigger>`` and ``<ContactWizardDialog>`` "must
appear in the rendered tree" — but no gate actually checked. Result:
white screenshot, ~$120 of agent fix-loop spent before merge.

This gate makes that promise enforceable.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from set_orch.gate_runner import GateResult
    from set_orch.state import Change

logger = logging.getLogger(__name__)


# JSX tag mention in scope — same shape as scope_manifest_extras.
_SCOPE_TAG_RE = re.compile(r"<(/?[A-Z][\w]*)\b[^>]*/?>")

# Standard library / framework components we don't enforce mounting on.
# These come from external packages (shadcn/ui primitives, lucide
# icons, next/* utilities). The agent can compose them inside other
# components without each needing a top-level mount.
_LIBRARY_COMPONENTS: frozenset[str] = frozenset({
    # shadcn/ui primitives — composed within feature components
    "Button", "Input", "Label", "Textarea", "Select", "Checkbox",
    "Switch", "Slider", "Progress", "Badge", "Avatar", "Card",
    "Form", "FormField", "FormItem", "FormLabel", "FormControl",
    "FormMessage", "FormDescription",
    "Dialog", "DialogContent", "DialogTrigger", "DialogHeader",
    "DialogTitle", "DialogDescription", "DialogFooter", "DialogClose",
    "Sheet", "SheetContent", "SheetTrigger", "SheetHeader",
    "SheetTitle", "SheetDescription",
    "Popover", "PopoverContent", "PopoverTrigger",
    "HoverCard", "HoverCardContent", "HoverCardTrigger",
    "Command", "CommandInput", "CommandList", "CommandItem",
    "CommandGroup", "CommandEmpty", "CommandSeparator",
    "Breadcrumb", "Separator", "Skeleton", "Tabs", "TabsList",
    "TabsTrigger", "TabsContent", "Alert", "AlertTitle",
    "AlertDescription",
    # lucide-react icons — frequently mentioned in scope but compose
    # inside feature components
    "Menu", "X", "Search", "ChevronDown", "ChevronUp", "ChevronLeft",
    "ChevronRight", "Check", "Plus", "Minus", "Loader2",
    # next/* HOCs that wrap content
    "Link", "Image", "Script",
    # sonner toast library — typically imported directly from `sonner`,
    # not re-exported as a project component, so the gate has no
    # definition to anchor on.
    "Toaster",
    # React fragments and built-ins
    "Fragment", "Suspense", "StrictMode",
})


# Files that count as "definition" of a component — exclude from the
# mount search since a component referencing itself doesn't prove it's
# mounted in a render tree.
_DEFINITION_FILE_INDICATORS = (
    "export function ",
    "export default function ",
    "export const ",
    "export default ",
    "export { ",
)

# Files we don't consider as user-visible mount sites.
_EXCLUDED_PATH_FRAGMENTS = (
    "/v0-export/",
    "/tests/",
    "/node_modules/",
    "/.next/",
)


def _extract_required_components(scope: str) -> list[str]:
    """Pull ``<PascalCase>`` mentions from scope, dedup, drop closing
    tags and library primitives."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _SCOPE_TAG_RE.finditer(scope or ""):
        tag = m.group(1).lstrip("/")
        if not tag or tag in seen:
            continue
        seen.add(tag)
        if tag in _LIBRARY_COMPONENTS:
            continue
        out.append(tag)
    return out


def _walk_tsx_files(src_root: Path) -> list[Path]:
    """All ``.tsx``/``.jsx`` files under ``src/``, excluding test/
    library/build paths."""
    if not src_root.is_dir():
        return []
    out: list[Path] = []
    for root, dirs, files in os.walk(src_root):
        # Prune excluded directories early
        rel = root.replace(str(src_root), "")
        if any(frag in rel for frag in _EXCLUDED_PATH_FRAGMENTS):
            dirs[:] = []
            continue
        for fn in files:
            if fn.endswith((".tsx", ".jsx")):
                out.append(Path(root) / fn)
    return out


def _is_definition_file(content: str, comp: str) -> bool:
    """Heuristic: file defines ``comp`` if it has an ``export`` line
    naming it. Accepts both named and default exports."""
    patterns = (
        f"export function {comp}",
        f"export default function {comp}",
        f"export const {comp}",
        f"export default {comp}",
        f"export {{ {comp}",
        f"export {{{comp}",
        f", {comp} ",
        f", {comp},",
        f", {comp}}}",
    )
    for line in content.splitlines():
        ls = line.strip()
        if not ls.startswith("export"):
            continue
        if any(p in line for p in patterns):
            return True
    return False


def _is_jsx_used(content: str, comp: str) -> bool:
    """Check if ``<comp>`` or ``<comp />`` appears in JSX position.

    We require word-boundary at end so ``<Toaster>`` doesn't match
    ``<ToasterPortal>``.
    """
    return bool(re.search(rf"<{re.escape(comp)}\b", content))


def execute_required_components_gate(
    change_name: str,
    change: "Change",
    wt_path: str,
    profile=None,
) -> "GateResult":
    """Verify each scope-required component is JSX-rendered somewhere
    other than its own definition file.

    Skipped when:
      - no worktree path
      - scope mentions no PascalCase tags
      - none of the mentioned tags are project-defined (all library)
    """
    from set_orch.gate_runner import GateResult

    if not wt_path:
        return GateResult(
            "required-components", "skipped", output="no worktree path",
        )

    scope = getattr(change, "scope", "") or ""
    required = _extract_required_components(scope)
    if not required:
        return GateResult(
            "required-components", "skipped",
            output="no <PascalCase> tags in scope",
        )

    src_root = Path(wt_path) / "src"
    files = _walk_tsx_files(src_root)
    if not files:
        return GateResult(
            "required-components", "skipped",
            output="no src/*.tsx files",
        )

    # Read every file once.
    file_contents: dict[Path, str] = {}
    for f in files:
        try:
            file_contents[f] = f.read_text(encoding="utf-8")
        except OSError:
            continue

    missing: list[str] = []
    skipped: list[str] = []
    found: list[str] = []
    for comp in required:
        # Find files that define the component — exclude from mount
        # search (a component referencing itself doesn't count).
        defs = {f for f, c in file_contents.items() if _is_definition_file(c, comp)}

        # Find files that JSX-render the component, excluding defs.
        mount_sites = [
            f for f, c in file_contents.items()
            if f not in defs and _is_jsx_used(c, comp)
        ]

        # If the component has no definition anywhere, it's a library
        # import we couldn't classify upfront. Skip enforcement to
        # avoid false positives — a missing definition means the
        # build gate would have caught it already.
        if not defs:
            skipped.append(comp)
            continue

        if mount_sites:
            found.append(comp)
        else:
            missing.append(comp)

    if missing:
        retry_msg = (
            f"Required components defined but never mounted: "
            f"{', '.join(missing)}. Each component listed in `Required "
            "components / JSX` must appear as JSX (e.g. "
            "`<MyComponent />`) in at least one src/ file other than "
            "its own definition file. Currently the component "
            "compiles but no page or layout renders it — so its UI "
            "never reaches the user."
        )
        logger.warning(
            "required-components gate: %s missing %d mount(s): %s",
            change_name, len(missing), missing,
        )
        return GateResult(
            "required-components", "fail",
            output=f"missing-mounts: {', '.join(missing)}",
            retry_context=retry_msg,
            stats={
                "missing_mounts": missing,
                "found_mounts": found,
                "skipped_library": skipped,
            },
        )

    return GateResult(
        "required-components", "pass",
        output=(
            f"verified {len(found)} component mount(s)"
            + (f"; {len(skipped)} library skipped" if skipped else "")
        ),
        stats={"found_mounts": found, "skipped_library": skipped},
    )
