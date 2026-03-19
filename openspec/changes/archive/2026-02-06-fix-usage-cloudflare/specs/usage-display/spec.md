## MODIFIED Requirements

### Requirement: Usage Data Sources
Usage data SHALL be fetched from multiple sources with automatic fallback.

#### Scenario: Primary - Claude.ai API via curl-cffi
Given a saved session key exists in `~/.config/set-core/claude-session.json`
And `curl-cffi` Python package is installed
When fetching usage data
Then the worker calls the claude.ai organizations API using `curl-cffi` with `impersonate='chrome'`
And retrieves exact utilization percentages and reset times

#### Scenario: Fallback chain
Given a saved session key exists
When fetching usage data
Then the worker tries sources in this order:
1. `curl-cffi` (Chrome TLS fingerprint, bypasses Cloudflare)
2. Plain `curl` subprocess
3. `urllib.request` (stdlib)
4. Local JSONL parsing (no auth needed)
And uses the first source that returns valid data

#### Scenario: Graceful degradation without curl-cffi
Given `curl-cffi` is not installed
When the worker first attempts an API call
Then it logs a one-time warning suggesting `pip install curl-cffi`
And falls back to curl subprocess and urllib

#### Scenario: Fallback - Local JSONL Parsing
Given no session key is available or all API call methods fail
When fetching usage data
Then the worker parses `~/.claude/projects/*/*.jsonl` files
And calculates token usage for 5h and 7d windows

#### Scenario: Configurable estimation limits
Given local JSONL parsing is used
When calculating percentages
Then `usage.estimated_5h_limit` config (default 500000) is used for 5h percentage
And `usage.estimated_weekly_limit` config (default 5000000) is used for weekly percentage
