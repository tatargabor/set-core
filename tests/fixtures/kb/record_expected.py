#!/usr/bin/env python3
"""Record the oracle: run the REFERENCE engine over the fixture corpus.

The kb-search oracle is a set of result pages recorded from the reference
TypeScript engine (see openspec/changes/kb-search, tasks 1.2/1.3). This script
runs that engine over the committed fixture and writes one JSON page per
fixture query under ``expected/``.

The reference engine lives in another project's repository. This script never
names it: point ``KB_REFERENCE_CLI`` at its CLI entry file (a ``node``-runnable
``*.ts``) before running:

    KB_REFERENCE_CLI=/path/to/reference/cli.ts \
        python3 tests/fixtures/kb/record_expected.py

Everything the recorded pages must not carry (the machine's paths) is stripped
here: the reference embeds its ``cwd`` in the page, and the oracle stores only
repository-relative data. Run this only when deliberately re-pinning the
oracle (engine freeze changed), and record the new reference commit in
``expected/README.md``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent


def check_nfc_names(corpus: Path) -> None:
    """The oracle requires NFC file names, so both engines key rows identically."""
    for p in sorted(corpus.rglob("*")):
        rel = p.relative_to(corpus).as_posix()
        if unicodedata.normalize("NFC", rel) != rel:
            raise SystemExit(f"fixture path is not NFC: {rel!r}")


def main() -> int:
    ref_cli = os.environ.get("KB_REFERENCE_CLI")
    if not ref_cli:
        print("set KB_REFERENCE_CLI to the reference engine's CLI entry file", file=sys.stderr)
        return 2
    ref_cli = str(Path(ref_cli).resolve())

    queries = json.loads((FIXTURE_DIR / "queries.json").read_text(encoding="utf-8"))
    check_nfc_names(FIXTURE_DIR / "corpus")

    with tempfile.TemporaryDirectory(prefix="kb-oracle-") as td:
        work = Path(td)
        for name in ("corpus", "kb.config.json", "queries.json"):
            src = FIXTURE_DIR / name
            (shutil.copytree if src.is_dir() else shutil.copy2)(src, work / name)

        def run(args: list[str]) -> dict:
            cmd = ["node", ref_cli, "--cwd", str(work), "--config", str(work / "kb.config.json"), *args, "--json"]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise SystemExit(f"reference engine failed ({proc.returncode}):\n{proc.stderr}")
            return json.loads(proc.stdout)

        run(["index"])

        out_dir = FIXTURE_DIR / "expected"
        out_dir.mkdir(exist_ok=True)
        for spec in queries:
            page = run(["search", spec["q"], "--no-reindex", *spec["args"]])
            page.pop("cwd", None)  # machine-local; the oracle stores relative data only
            (out_dir / f"{spec['id']}.json").write_text(
                json.dumps(page, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            ties = [
                (a["root"], a["path"], a["score"])
                for i, a in enumerate(page["hits"])
                for b in page["hits"][i + 1 :]
                if a["score"] == b["score"] and (a["root"], a["path"]) != (b["root"], b["path"])
            ]
            flag = f"  WARNING score tie, order is implementation-defined: {ties}" if ties else ""
            print(f"{spec['id']}: {page['total']} sources, {len(page['hits'])} hits{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
