"""One-shot data migrations for set-core orchestration state.

Each migration is idempotent and gated by a per-project marker file so
the same migration runs at most once for a given project tree.
"""
