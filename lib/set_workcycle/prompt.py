"""What one work unit is handed.

A slice, not a file. The whole reason this engine exists is that handing an agent the entire
`tasks.md` and letting it work until it stops produces an implementation that dilutes: the
fortieth message decides the same questions the fifth did, with less of the file in view.

Four things travel, and the third is the one that is easy to forget:

1. **the slice** — this group's block, and no other group's;
2. **the reading list** — every markdown artifact in the change's directory except the task
   file, including ones earlier runs wrote;
3. **carry-over** — the notes of the most recent run for this group and for the one before
   it, because a fresh context forgets a discovery as readily as it forgets noise;
4. **the verdict schema**, verbatim, so what the unit is asked for and what the parser accepts
   cannot drift apart.
"""

from __future__ import annotations

import json
import logging
from typing import Iterable, Sequence

from .groups import RunNote, Slice
from .verdict import VERDICT_SCHEMA

logger = logging.getLogger(__name__)

__all__ = ["build_unit_prompt"]

_INSTRUCTIONS = """\
You are implementing ONE section of a change, in a fresh context, in this working tree.

Work only on the tasks in "Your slice" below. Do not start work belonging to another
section — another run will take it, and it has its own context.

As you complete a task, mark its checkbox in the change's task file: `- [ ]` becomes `- [x]`.
Mark only what you actually finished.

When you are done — or when you cannot go further — end your reply with a single fenced JSON
block matching the schema below, and nothing after it.

Two rules about that verdict, both of which change what happens next:

* `open_decisions` is the ONLY thing that stops the cycle for a person. A decision written in
  `notes` is read as context by the next run and answered on the human's behalf. If a person
  must decide, put it in `open_decisions`.
* `completed` is checked against the task file. Claiming a task you did not mark, or marking
  one you do not claim, is reported as a divergence — so keep the two in step.
"""


def build_unit_prompt(
    change: str,
    slice_: Slice,
    *,
    reading_list: Sequence[str] = (),
    background: Sequence[str] = (),
    carry_over: Iterable[RunNote] = (),
    tasks_path: str = "",
    answers: Sequence[tuple] = (),
) -> str:
    """Assemble everything one run receives."""
    notes = list(carry_over)
    parts = [
        _INSTRUCTIONS,
        f"## The change\n\n`{change}`, section `{slice_.group_key}` — {slice_.title}",
    ]
    if tasks_path:
        parts.append(f"Its task file is `{tasks_path}`. Mark your checkboxes there.")

    parts.append("## Your slice\n\n" + slice_.block)
    if slice_.truncated:
        parts.append(
            "> This slice was cut to a task limit: it holds part of the section, not all of "
            "it. Finish what is here and return `PARTIAL`."
        )

    if reading_list:
        parts.append(
            "## Read these first\n\n"
            + "\n".join(f"- `{p}`" for p in reading_list)
            + "\n\nThey are this change's own artifacts, including any an earlier run wrote."
        )

    if background:
        # Separate from the change's own artifacts on purpose: one is the work,
        # the other is what the project wants known while doing it. Merging them
        # into one list tells the unit that a standing reference is part of this
        # change, which is a different instruction.
        parts.append(
            "## The project's own background\n\n"
            + "\n".join(f"- `{p}`" for p in background)
            + "\n\nDeclared by the project, not by this change. Read what is relevant; "
              "these are standing references rather than this change's artifacts."
        )

    if notes:
        parts.append(
            "## Carried over from earlier runs\n\n"
            + "\n\n".join(
                f"**{n.group_key}** (run {n.run_id or 'unknown'}, {n.finished_at or 'undated'}):\n"
                f"{n.notes}"
                for n in notes
            )
        )

    if answers:
        parts.append(
            "## Questions that have been answered\n\n"
            + "\n".join(f"- **{task}**: {answer}" for task, answer in answers)
            + "\n\nThese were open decisions from an earlier run. They are decided now — "
              "act on them rather than asking again."
        )

    parts.append(
        "## Your verdict\n\nEnd with exactly one fenced JSON block matching:\n\n"
        "```json\n" + json.dumps(VERDICT_SCHEMA, indent=2) + "\n```"
    )
    prompt = "\n\n".join(parts)
    logger.info(
        "unit prompt built for %s/%s: %d chars, %d artifact(s), %d carry-over note(s)",
        change, slice_.group_key, len(prompt), len(reading_list), len(notes),
    )
    return prompt
