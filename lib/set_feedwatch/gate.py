"""The copy gate: run the project's declared checker over each outgoing block of a draft.

The gate command is the project's — set-core does not know what good copy is. Each block's
text goes to the command on stdin; `{kind}` and `{file}` in the command are substituted.
No shell is involved. With no gate declared the answer is "no gate configured", which is
NOT a pass: an unchecked draft must not read as a checked one.
"""
from __future__ import annotations

import logging
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from .declaration import Declaration

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    kind: str
    chars: int
    ok: bool
    output: str


def outgoing_blocks(text: str, decl: Declaration) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    if decl.drafts.blocks:
        langs = "|".join(re.escape(b) for b in decl.drafts.blocks)
        found += [(k, b.strip()) for k, b in
                  re.findall(rf"^```({langs})[ \t]*\n(.*?)^```", text, re.M | re.S)]
    subj = re.compile(rf"^{re.escape(decl.labels.subject)}:\s*(.+)$", re.M)
    found += [("subject", s.strip()) for s in subj.findall(text)]
    return found


def run_gate(path: Path, decl: Declaration) -> List[GateResult]:
    text = path.read_text(encoding="utf-8")
    results = []
    for kind, body in outgoing_blocks(text, decl):
        argv = [a.replace("{kind}", kind).replace("{file}", str(path)) for a in shlex.split(decl.drafts.gate)]
        try:
            p = subprocess.run(argv, input=body, capture_output=True, text=True, cwd=decl.root, timeout=120)
            ok, out = p.returncode == 0, (p.stdout + p.stderr).strip()
        except (OSError, subprocess.SubprocessError) as e:
            ok, out = False, f"gate could not run: {e}"
        logger.info("feed-watch gate [%s]: %s", kind, "pass" if ok else "fail")  # no file name: it is a slug of the item
        results.append(GateResult(kind, len(body), ok, out))
    return results
