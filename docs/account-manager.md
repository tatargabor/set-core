# Claude Code Account Manager

Manage multiple Claude Code accounts and manually switch between them.

> **IMPORTANT: Manual switching only.**
> This tool provides visibility and a convenient switch mechanism.
> **Automatic rotation to circumvent rate limits violates [Anthropic's Terms of Service](https://www.anthropic.com/policies/terms-of-service).**
> All switching MUST be user-initiated. Do NOT automate or script the `switch` command.

## Setup

### 1. Log in with your first account

```bash
claude login
```

### 2. Save the credentials

```bash
set-router add "Personal"
# Added account 'Personal'
```

### 3. Log in with another account

```bash
claude login
# (log in with a different email/account)
```

### 4. Save the second account

```bash
set-router add "Work"
# Added account 'Work'
```

Repeat for additional accounts. Each `claude login` + `set-router add` pair registers one account.

## Usage

### List accounts

```bash
set-router list
#   * Personal              plan: max        [ACTIVE]
#   o Work                  plan: max
```

### Switch accounts (manual)

```bash
set-router switch "Work"
# Switched to 'Work'. New CC instances will use this account.
#   Manual switch - automatic rotation is not supported.
```

**Running Claude Code instances are not affected** by a switch. They continue using whatever credentials they had at startup. Only new instances pick up the switched account.

### Check status

```bash
set-router status
# Active: Personal
# Plan:   max (default_claude_max_20x)
# Token:  expires in 5h 28m
```

### Remove an account

```bash
set-router remove "Work"
# Removed account 'Work'
```

You cannot remove the last remaining account.

## How It Works

```
                  ~/.claude/.credentials.json
                         |
                    CC reads at startup
                         |
    set-router           v
    +---------+     +---------+
    | Account |---->| Active  |---->  Claude Code
    |  Pool   |swap | Creds   |      (uses token
    |         |     |  File   |       in memory)
    +---------+     +---------+
    cc-accounts.json

    On switch:
    1. Lock credentials file (fcntl.flock)
    2. Write selected account's OAuth tokens
    3. Unlock
    4. New CC instances use the new token
    5. Running instances are unaffected
```

## GUI (set-control)

If you have set-control running:

- CC accounts appear in the usage panel alongside web accounts
- Active CC account shows a filled dot indicator
- **Hamburger menu > "Switch CC Account..."** for manual switching
- Usage bars show per-account session % and weekly %

The "Switch CC Account" menu item only appears when 2+ CC accounts are registered.

## Storage

- **Account pool**: `~/.config/set-core/cc-accounts.json` (permissions: 600)
- **Active credentials**: `~/.claude/.credentials.json` (managed by Claude Code)

Both files contain OAuth tokens in plaintext, matching Claude Code's own security model (filesystem permissions only).

## FAQ

**Q: Can I automate switching?**
A: No. Automating switches to circumvent rate limits violates Anthropic's ToS. This tool is for manual account management only.

**Q: What happens if a token expires?**
A: Claude Code handles token refresh internally using the stored refreshToken. If both tokens expire (account unused for a long time), run `claude login` again and `set-router add "<name>"` to update.

**Q: Does switching affect running agents?**
A: No. Running CC instances hold the token in memory. Only new instances started after the switch use the new credentials.

**Q: Can I use this with the sentinel?**
A: The sentinel can query `set-router status` to see which account is active and its usage level. But it will NOT automatically switch accounts.
