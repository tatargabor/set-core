"""set-watchdog — the fleet's continuous self-check (change `fleet-watchdog`).

A stateless tick on a user timer runs deterministic probes, keeps one finding per
fingerprint in a local store, has GLM triage only the new ones, and hands a real
finding to the project that owns it. Nothing here edits a tree, deploys, or sends a
message to a person.
"""
