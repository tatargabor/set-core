## Context

set-core manages git worktrees with integrated AI coding via Claude Code. Currently hardcoded to Zed editor. Users need flexibility to use their preferred editor while maintaining core functionality: opening worktrees and launching Claude Code terminal.

### Editor Comparison Research

Based on research, these editors support Claude Code integration:

| Editor | Claude Integration | Terminal Launch Method | Window Class | Notes |
|--------|-------------------|----------------------|--------------|-------|
| **Zed** | ACP (Agent Client Protocol) native | `cmd-?` then new Claude thread, or custom keybind | `Zed` | Best native integration, macOS/Linux only |
| **VS Code** | Extension + CLI in terminal | Extension panel or `claude` in integrated terminal | `Code` | Most cross-platform, extension auto-includes CLI |
| **Cursor** | VSIX manual install + CLI | Extension panel or `claude` in terminal | `Cursor` | VS Code fork, needs manual VSIX install |
| **Windsurf** | Cascade AI + API key for Claude | `@terminal` in Cascade, or CLI | `Windsurf` | Has own AI, can use Claude via API |

### Key Requirements

1. **Open worktree folder**: All editors support `<editor> <path>` CLI pattern
2. **Launch Claude Code terminal**: Different per editor
3. **Window focus**: Requires knowing window class for xdotool

## Goals / Non-Goals

### Goals
- Support Zed, VS Code, Cursor, Windsurf
- Auto-detect available editors
- Persist user preference in config
- Maintain existing workflow for Zed users
- Automated tests for editor detection

### Non-Goals
- Support every possible editor (just these 4)
- IDE-specific features beyond opening + Claude
- Editor installation/management
- Deep integration with each editor's AI features

## Decisions

### Decision 1: Configuration location
Store editor preference in existing `~/.config/set-core/config.json`:
```json
{
  "editor": {
    "name": "vscode",
    "command": "code",
    "claude_launch": "terminal"
  }
}
```

Rationale: Reuse existing config infrastructure, keep settings together.

### Decision 2: Editor detection chain
1. Check user config
2. Auto-detect in order: Zed > VS Code > Cursor > Windsurf
3. Error if none found

Rationale: Zed has best native Claude integration, others fallback.

### Decision 3: Claude Code launch strategy
- **Zed**: Use xdotool Ctrl+Shift+L (existing) or skip if ACP detected
- **VS Code/Cursor**: Open editor, user manually starts Claude (extension handles it)
- **Windsurf**: Open editor, user uses Cascade or terminal

Rationale: Can't reliably automate Claude launch in all editors; focus on opening folder.

### Decision 4: Window focus implementation
Each editor has different xdotool class:
```bash
case "$EDITOR" in
  zed) xdotool search --class "Zed" ;;
  vscode) xdotool search --class "Code" ;;
  cursor) xdotool search --class "Cursor" ;;
  windsurf) xdotool search --class "Windsurf" ;;
esac
```

## Alternatives Considered

### Alternative: Generic editor variable
Just use `$EDITOR` or `$VISUAL` environment variable.
Rejected: Doesn't provide Claude launch method or window class info.

### Alternative: Plugin system per editor
Create separate plugin files for each editor.
Rejected: Over-engineered for 4 editors with similar patterns.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Editor CLI changes | Document known working versions, test regularly |
| xdotool not available on macOS | Use AppleScript for macOS window focus |
| Cursor VSIX install complexity | Document manual steps, test in install script |
| Windsurf AI conflicts with Claude | Document as "use terminal mode" |

## Testing Strategy

### Automated Tests (`tests/test_editor_integration.py`)

```python
# Test editor detection
def test_detect_zed():
    """Test Zed detection when installed"""

def test_detect_vscode():
    """Test VS Code detection"""

def test_detect_cursor():
    """Test Cursor detection"""

def test_detect_windsurf():
    """Test Windsurf detection"""

def test_detection_fallback_chain():
    """Test fallback when preferred editor not found"""

# Test configuration
def test_config_persistence():
    """Test editor preference is saved/loaded"""

def test_config_invalid_editor():
    """Test error handling for invalid editor name"""

# Test CLI commands
def test_editor_cli_command():
    """Test correct CLI is used for each editor"""

# Integration tests (require editors installed)
@pytest.mark.integration
def test_open_worktree_vscode():
    """Test opening worktree in VS Code"""
```

### Manual Test Checklist
- [ ] Fresh install detects available editors
- [ ] `wt-config editor vscode` changes preference
- [ ] `wt-work <id>` opens correct editor
- [ ] `wt-focus <id>` focuses correct window
- [ ] GUI shows current editor
- [ ] Switching editor in GUI works

## Migration Plan

1. Add new config field, default to "zed" for backward compat
2. Update `find_zed()` to `find_editor()` with same interface
3. Update scripts to use new function
4. Add `wt-config` command
5. Update GUI
6. Update install scripts to detect all editors
7. Document editor-specific Claude Code setup

## Parallel Development Strategy

Development and testing can run alongside active set-core usage:

### Isolated Test Environment
```bash
# Use separate config directory for tests
export WT_CONFIG_DIR="/tmp/set-core-test"
mkdir -p "$WT_CONFIG_DIR"

# Tests won't affect ~/.config/set-core/
```

### Backward Compatibility Approach
1. Keep `find_zed()` as wrapper around new `find_editor()`
2. New `editor` config key - existing configs without it default to "zed"
3. GUI changes are additive (new settings panel)

### Safe Rollout Order
1. Add `find_editor()` to `wt-common.sh` (no behavior change yet)
2. Add `wt-config` command (new, doesn't affect existing)
3. Write and run tests with isolated config
4. Replace `find_zed()` internals to use `find_editor()`
5. Update GUI last (requires restart anyway)

### Live Testing
- Scripts: Changes are immediate, test with `wt-work <test-worktree>`
- GUI: Restart required after handler changes
- Config: Can switch back to zed anytime with `wt-config editor set zed`

## Open Questions

- Should we support Neovim/terminal editors? (Probably not - no window focus)
- Should we auto-install Claude Code extension in VS Code? (Probably not - too invasive)
