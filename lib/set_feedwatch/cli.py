"""set-feed-watch — the deterministic half of feed-watch. It never touches the network.

    set-feed-watch show                       # the resolved declaration (what the skill reads)
    set-feed-watch seen                       # id <TAB> text-hash <TAB> file, one line per item
    set-feed-watch check-new [--link URL] < item.txt
                                              # exit 0 = new, 3 = already collected (prints the file)
    set-feed-watch digest YYYY-MM-DD [--all]  # writes the declared digest file
    set-feed-watch gate FILE...               # the project's copy gate over each outgoing block
    set-feed-watch optin on [--times 08:30,18:30] | off | status | remove | import PATH

Exit status: 0 ok, 1 failure (a failing gate, unscored items are NOT failures), 2 the
declaration is missing or invalid, 3 already collected.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import adapters, items as items_mod, optin, scoring
from .declaration import DeclarationError, load, project_root
from .gate import run_gate

logger = logging.getLogger(__name__)


def _rel(decl, p: Path) -> str:
    try:
        return str(p.relative_to(decl.root))
    except ValueError:
        return str(p)


def cmd_show(a, decl):
    out = {
        "root": str(decl.root), "dir": _rel(decl, decl.dir),
        "sources": [{**s.__dict__, "permalink_hint": adapters.ADAPTERS[s.kind].permalink_hint,
                     "sort_hint": adapters.ADAPTERS[s.kind].sort_hint} for s in decl.sources],
        "item_template": decl.item_template, "labels": decl.labels.__dict__,
        "rubric": None if decl.rubric is None else {
            "marker": decl.rubric.marker, "guidance": decl.rubric.guidance,
            "dimensions": [d.__dict__ for d in decl.rubric.dimensions],
            "threshold": {"total_min": decl.rubric.total_min, "dimension_min": decl.rubric.dimension_min}},
        "drafts": decl.drafts.__dict__, "digest_filename": decl.digest_filename,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_seen(a, decl):
    for it in items_mod.items(decl):
        print(f"{it.id or '-'}\t{it.hash}\t{_rel(decl, it.path)}")
    return 0


def cmd_check_new(a, decl):
    known = items_mod.find_known(decl, sys.stdin.read(), a.link)
    if known:
        print(f"KNOWN: {_rel(decl, known.path)}")
        return 3
    print("NEW")
    return 0


def cmd_digest(a, decl):
    rows = scoring.digest_rows(decl, None if a.all else a.date)
    out = decl.digest_path(a.date)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(scoring.render_digest(decl, a.date, rows, a.all), encoding="utf-8")
    print(_rel(decl, out))
    for w in scoring.warnings(rows):
        print(f"WARNING: {w}", file=sys.stderr)
    logger.info("feed-watch digest %s: %d item(s), %d warning(s)", a.date, len(rows), len(scoring.warnings(rows)))
    return 0


def cmd_gate(a, decl):
    if not decl.drafts.gate:
        print("no gate configured (drafts.gate is not declared) — the drafts are UNCHECKED")
        return 1
    bad = 0
    for f in a.files:
        p = Path(f)
        results = run_gate(p, decl)
        if not results:
            print(f"FAIL {p.name}: no outgoing block ({', '.join(decl.drafts.blocks) or 'none declared'}) and no subject")
            bad += 1
            continue
        for r in results:
            print(f"{'PASS' if r.ok else 'FAIL'} {p.name} [{r.kind}] {r.chars} chars")
            if not r.ok and r.output:
                print("  " + r.output.replace("\n", "\n  "))
            bad += not r.ok
    return 1 if bad else 0


def cmd_optin(a, root: Path):
    email = optin.account_email()
    if a.action == "on":
        if not email:
            print(f"cannot read the Claude account e-mail from {optin.claude_json()}; log in to Claude Code first",
                  file=sys.stderr)
            return 1
        try:
            times = optin.parse_times(a.times, (optin.entry(root) or {}).get("times") or optin.DEFAULT_TIMES)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        optin.set_entry(root, enabled=True, account=email, times=times)
        if optin.load_plugin():
            print(f"pane plugin added to env.CLAUDE_CODE_PLUGIN_DIRS in {optin._settings_path()} (backup written)")
        print(f"on for {email} in {root}, at {', '.join(times)}. Start a new Claude Code session to see the pane.")
        return 0
    if a.action == "off":
        if optin.entry(root) is None:
            print("not opted in here; nothing to switch off")
            return 0
        optin.set_entry(root, enabled=False)
        print("off (the plugin stays loaded but does not ask). To remove it as well: set-feed-watch optin remove")
        return 0
    if a.action == "remove":
        if optin.entry(root) is not None:
            optin.set_entry(root, enabled=False)
        others = [p for p, e in optin._load()["projects"].items() if p != str(root) and e.get("enabled")]
        if others:
            print(f"opt-in off here; plugin kept loaded for {len(others)} other project(s)")
        elif optin.unload_plugin():
            print("opt-in off; plugin removed from CLAUDE_CODE_PLUGIN_DIRS")
        else:
            print("opt-in off; plugin was not loaded")
        return 0
    if a.action == "import":
        if not a.path:
            print("import needs a PATH to an existing opt-in file", file=sys.stderr)
            return 1
        try:
            e = optin.import_from(root, Path(a.path).expanduser())
        except ValueError as err:
            print(str(err), file=sys.stderr)
            return 1
        print(f"imported into {optin.optin_path()}: enabled={e['enabled']}, times={', '.join(e['times'])}")
        if e["enabled"] and optin.load_plugin():
            print("pane plugin added to env.CLAUDE_CODE_PLUGIN_DIRS (backup written)")
        return 0
    e = optin.entry(root)
    print(f"project:       {root}")
    print(f"account:       {email or '-'}")
    print(f"opt-in file:   {optin.optin_path()}{'' if optin.optin_path().exists() else ' (absent)'}")
    print(f"active here:   {'yes' if optin.is_active(e, email) else 'no'}")
    print(f"times:         {', '.join((e or {}).get('times') or []) or '-'}")
    print(f"plugin loaded: {'yes' if str(optin.PLUGIN_DIR) in optin.plugin_dirs() else 'no'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="set-feed-watch", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show").set_defaults(fn=cmd_show)
    sub.add_parser("seen").set_defaults(fn=cmd_seen)
    c = sub.add_parser("check-new")
    c.add_argument("--link", default="")
    c.set_defaults(fn=cmd_check_new)
    d = sub.add_parser("digest")
    d.add_argument("date")
    d.add_argument("--all", action="store_true")
    d.set_defaults(fn=cmd_digest)
    g = sub.add_parser("gate")
    g.add_argument("files", nargs="+")
    g.set_defaults(fn=cmd_gate)
    o = sub.add_parser("optin")
    o.add_argument("action", choices=["on", "off", "status", "remove", "import"])
    o.add_argument("path", nargs="?")
    o.add_argument("--times", help="e.g. 08:30,18:30")
    o.set_defaults(fn=None)
    return ap


def main(argv=None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    a = build_parser().parse_args(argv)
    if a.cmd == "optin":
        # The opt-in is about this user and this project; it does not need the declaration
        # to be valid, but the pane only ever activates where one exists.
        return cmd_optin(a, project_root())
    try:
        decl = load()
        if a.cmd == "digest":
            decl.require_rubric()
    except DeclarationError as e:
        print(f"set-feed-watch: {e}", file=sys.stderr)
        return 2
    return a.fn(a, decl) or 0


if __name__ == "__main__":
    sys.exit(main())
