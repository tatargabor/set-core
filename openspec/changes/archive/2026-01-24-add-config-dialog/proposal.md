# Change: Add Configuration Dialog

## Why
The Control Center GUI currently uses hardcoded values (opacity, colors, timings). Making these configurable improves the user experience and enables customization. Stored in a unified config file, settings persist across restarts.

## What Changes

### GUI Config Dialog
- New "Settings" menu item in the ≡ menu
- Config window divided into categories:
  - **Control Center**: opacity, window width, refresh interval
  - **JIRA**: default project, URL, credentials path
  - **Git**: default branch name pattern, fetch timeout
  - **Notifications**: enable, sounds

### Config File
- Location: `~/.config/set-core/gui-config.json`
- Read at startup, saved on change
- Defaults if no config exists

### Configurable Values

#### Control Center group
| Setting | Current | Default |
|---------|---------|---------|
| `opacity.default` | 0.5 | 0.5 |
| `opacity.hover` | 1.0 | 1.0 |
| `window.width` | 500 | 500 |
| `refresh.interval_ms` | 2000 | 2000 |
| `blink.interval_ms` | 500 | 500 |

#### JIRA group
| Setting | Current | Default |
|---------|---------|---------|
| `jira.base_url` | - | null |
| `jira.default_project` | - | null |
| `jira.credentials_path` | hardcoded | ~/.config/set-core/jira.json |

#### Git group
| Setting | Current | Default |
|---------|---------|---------|
| `git.branch_prefix` | "change/" | "change/" |
| `git.fetch_timeout_s` | 10 | 10 |

#### Notifications group
| Setting | Current | Default |
|---------|---------|---------|
| `notifications.enabled` | true | true |
| `notifications.sound` | false | false |

## Impact
- Affected specs: control-center (MODIFIED - new config requirement)
- Affected code: gui/main.py (config loading, Settings dialog)
