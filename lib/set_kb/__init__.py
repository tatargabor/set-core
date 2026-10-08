"""set_kb — the shared knowledge-base search engine.

A stdlib-only Python port (SQLite FTS5, section-level BM25F over markdown,
source dedup, a reserved channel lane) of an MIT-licensed retrieval engine.
The upstream licence notice, the upstream commit it derives from and the port
lineage live in `LICENSE-UPSTREAM` beside this package; every ported module
carries a one-line attribution pointing there.

Layout: `store` (schema + CRUD), `search` (ranking + the page), `chunker`,
`frontmatter`, `lang`/`lang_hu`, `glob`, `channels`, `indexer` (walk + the
atomic index run), `get_section` (verbatim section fetch), `runtime` (the FTS5
probe). The CLI (`set-kb`) is the single external surface and lives in `bin/`.
"""

from set_kb.types import Chunk, FileState, KbHit, SearchOpts, SearchPage

__version__ = "0.1.0"

__all__ = ["Chunk", "FileState", "KbHit", "SearchOpts", "SearchPage", "__version__"]
