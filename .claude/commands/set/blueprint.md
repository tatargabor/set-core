Architecture blueprint before the offer — research the open questions, then write the architecture plan the price is built from.

Usage: /set:blueprint [decisions-path]

This runs the set:blueprint skill, which:
1. Reads the internal decisions first, then the requirement list, then meeting notes
2. Researches every open question with a sourced verdict (works / works with caveat / doesn't / unknown) → docs/research-<date>.md
3. Writes docs/architecture-plan.md: where things run, how they talk, data ownership, requirement→component map, sub-processors, hours vs the price band, running costs, tests that gate the price
4. Optionally builds a private visual page from the two documents
5. Commits only those files and reports the findings that change the price or the architecture

The offer is written after this, and after the hands-on tests.

Arguments:
- decisions-path: the internal decisions document (default: ask, or the newest docs/*decisions*.md)

Example: `/set:blueprint docs/2026-01-15-internal-decisions.md`
