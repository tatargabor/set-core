# Design: Claude Session Management

## Research Summary

### Existing Open-Source Solutions

| Tool | Method | Cross-Platform | Notes |
|------|--------|----------------|-------|
| [ccusage](https://ccusage.com) | Local JSONL parsing | Yes | CLI tool, reads `~/.claude/projects/` |
| [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) | Local + predictions | Yes | Real-time monitor with burn rate |
| [Claudia](https://github.com/getAsterisk/claudia) | GUI wrapper | Yes | Open-source Claude Code GUI |

### Official Anthropic Methods

| Method | Availability | Real-time | Notes |
|--------|--------------|-----------|-------|
| Local JSONL files | All users | Yes | `~/.claude/projects/*/\*.jsonl` |
| OpenTelemetry | All users | Yes | Requires OTEL setup, env vars |
| Admin API | Org admins only | No (daily) | Requires `sk-ant-admin...` key |
| Claude.ai web | All users | Yes | Requires browser session |

### Recommendation

**Use local JSONL parsing** as primary method (like ccusage does). This is:
- Cross-platform
- No authentication needed
- Used by established open-source tools
- Official data source (Claude Code writes it)

## Architecture Decision

### Option A: Local JSONL Aggregation (Recommended Primary)

**How it works:**
1. Scan `~/.claude/projects/*/\*.jsonl` files
2. Parse each line for `usage` object containing:
   - `input_tokens`, `output_tokens`
   - `cache_read_input_tokens`, `cache_creation_input_tokens`
3. Filter by timestamp for 5h and 7-day windows
4. Sum tokens and estimate percentage based on known limits

**Pros:**
- No authentication required
- Works offline
- Cross-platform (same file structure on all OS)
- No external dependencies
- Data already exists locally
- Same approach as ccusage (proven)

**Cons:**
- Estimates only (don't know exact limits per subscription tier)
- Slight delay (files written after response complete)

**Token structure in JSONL:**
```json
{
  "message": {
    "usage": {
      "input_tokens": 10,
      "output_tokens": 50,
      "cache_read_input_tokens": 15000,
      "cache_creation_input_tokens": 3600
    }
  },
  "timestamp": "2026-01-26T20:59:15.519Z"
}
```

### Option B: OpenTelemetry Integration (Advanced)

**How it works:**
1. User enables telemetry: `CLAUDE_CODE_ENABLE_TELEMETRY=1`
2. Claude Code exports metrics via OTEL protocol
3. set-core runs local OTEL collector or reads Prometheus endpoint

**Metrics available:**
- `claude_code.token.usage` - token counts by type
- `claude_code.cost.usage` - cost in USD
- `claude_code.session.count` - session counts

**Pros:**
- Official, supported method
- Accurate real-time data
- No hacking or scraping

**Cons:**
- Requires OTEL setup (complexity)
- User must enable env vars
- Overkill for simple usage display

### Option C: WebView Login (Secondary/Optional)

**How it works:**
1. Open WebView to `https://claude.ai/login`
2. User completes OAuth login in embedded browser
3. Monitor cookies for `sessionKey`
4. Store session for later API calls

**Improvements needed:**
- Better cookie capture (current implementation works but fragile)
- Handle OAuth popups properly
- Add "Open in default browser" option for OAuth

**Pros:**
- Exact real-time usage data from claude.ai
- Works for all subscription tiers

**Cons:**
- Requires user login
- Session expires periodically
- WebView can have compatibility issues

## Recommended Implementation

1. **Default to JSONL parsing** - works immediately, no setup
2. **Show "Login for accurate data" option** - for users who want exact numbers
3. **Remove browser_cookie3 dependency** - unreliable and hacky
4. **Keep cloudscraper for API calls** - only used after user explicitly logs in
5. **Future: Add OTEL support** - for advanced users who want official metrics

## Usage Limits (Estimated)

Based on Claude subscription tiers:

| Tier | 5h Window | Weekly Window | Notes |
|------|-----------|---------------|-------|
| Pro | ~45 messages | ~225 messages | Message-based |
| Max | ~500k tokens | ~5M tokens | Token-based |
| API | Unlimited | Unlimited | Cost-based |

For token estimation, use configurable defaults with option to customize.

## Cross-Platform Considerations

### File Paths

| Path | Linux | macOS | Windows |
|------|-------|-------|---------|
| Config | `~/.config/set-core/` | `~/Library/Application Support/set-core/` | `%APPDATA%\set-core\` |
| Claude data | `~/.claude/` | `~/.claude/` | `%USERPROFILE%\.claude\` |

Claude Code uses `~/.claude/` on all platforms (including Windows with forward slashes).

### Python Path Handling

```python
from pathlib import Path

# Cross-platform Claude directory
def get_claude_dir():
    return Path.home() / ".claude"

# Cross-platform project sessions
def get_project_sessions():
    claude_dir = get_claude_dir()
    projects_dir = claude_dir / "projects"
    if projects_dir.exists():
        for session_dir in projects_dir.iterdir():
            if session_dir.is_dir():
                for jsonl in session_dir.glob("*.jsonl"):
                    yield jsonl
```

### GUI Framework

PySide6/Qt is already cross-platform. WebView (QWebEngineView) works on all platforms.

## Testing Strategy

### Unit Tests (pytest)

```python
def test_parse_jsonl_usage():
    """Test parsing token usage from JSONL line"""
    line = '{"message":{"usage":{"input_tokens":10,"output_tokens":50}},"timestamp":"2026-01-26T20:59:15.519Z"}'
    usage = parse_usage_line(line)
    assert usage.input_tokens == 10
    assert usage.output_tokens == 50

def test_filter_by_time_window():
    """Test filtering usage data by 5h window"""
    # Create test data spanning multiple hours
    ...

def test_calculate_percentage():
    """Test percentage calculation with configurable limits"""
    ...
```

### Integration Tests

- Test JSONL file discovery on each platform
- Test WebView login flow
- Test usage display updates

### Manual Test Matrix

| Platform | JSONL Parse | WebView Login | Usage Display |
|----------|-------------|---------------|---------------|
| Linux (Ubuntu) | ☐ | ☐ | ☐ |
| macOS (14+) | ☐ | ☐ | ☐ |
| Windows 11 | ☐ | ☐ | ☐ |
