## Why

A project that works on top of a shared knowledge repository has no way to search it
from where it works. Asked on the bus on 2026-11-12: a content-producing project needs
the answers held in a separate data repository (a wiki of a few thousand pages, indexed
by its own `kb.json` with its own language, stemming and lane settings) without leaving its
own checkout. The answer today is "open the other repository and search there". An agent
does not do that on its own, so the shared knowledge exists and is never found.

The upstream engine solves a related need with merged sources: the other repository's
folders become roots of this project's index. That copies the other corpus into every
index that names it (tens of thousands of chunks each time), and it searches that corpus
with **this** project's configuration, losing the language, stemming, channels and lane the
owner measured for it.

## What Changes

- A new `kb.json` key `linked`: `[{project, scope?, about?}]`. `project` is a set-core
  registry name. A data repository that should not receive a framework deploy enters the
  registry through `set-project register` (shipped in `project-register-no-deploy`).
- `set-kb search` also searches every linked project **in its own index, with its own
  configuration**, adding only the link's `scope`. Each linked project is its own block on
  the page. In JSON it is `linked[]`, and each hit carries `project`.
- One level only: a linked project's own links are not followed.
- A link that cannot be searched (an unregistered name, a missing checkout, a broken config)
  is shown as `NOT SEARCHED: <reason>` / `"searched": false`, and it never costs the rest of
  the page.
- `--no-linked` searches this project only. `set-kb get <path> --project <name>` fetches from
  a linked project and refuses a name the config does not link.
- MCP: `kb_search(linked=True)` and `kb_get(project=...)` pass both through.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `kb-search-engine`: linked projects searched beside the own index. Added as new
  requirements. The capability's base spec is still in the unarchived `kb-search` change.
- `kb-search-access`: the CLI and MCP surfaces of the above (`--no-linked`, `get --project`,
  the MCP parameters).

## Impact

- `lib/set_kb/config.py`: the `linked` key, validated, kept out of the corpus-config hash.
- `lib/set_kb/lifecycle.py`: registry lookup, `linked_project`, `search_linked`, `LinkedSearch`.
- `lib/set_kb/cli.py`: the page blocks, the JSON `linked` list, `--no-linked`, `get --project`.
- `mcp-server/set_mcp_server.py`: two parameters.
- `docs/reference/kb-search.md`: the key and its rules.
- Not touched: the index schema, the indexer, ranking. No new dependency.
