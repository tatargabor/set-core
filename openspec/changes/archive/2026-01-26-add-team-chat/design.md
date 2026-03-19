# Design: Encrypted Team Chat

## Overview

End-to-end encrypted chat in the Control Center, using NaCl (libsodium) encryption and git-based synchronization.

## Encryption Design

### Algorithm Choice: NaCl Box

**Choice:** `nacl.public.Box` (Curve25519 + XSalsa20 + Poly1305)

**Rationale:**
- Industry standard, audited implementation
- PyNaCl is stable, well-documented
- Simple API, hard to misuse
- Box automatically computes the shared secret

### Key Management

```
Keypair generation:
  private_key = PrivateKey.generate()
  public_key = private_key.public_key

Encryption (A -> B):
  box = Box(my_private_key, their_public_key)
  encrypted = box.encrypt(plaintext)  # Includes random nonce

Decryption (B receives):
  box = Box(my_private_key, their_public_key)  # Same shared key!
  plaintext = box.decrypt(ciphertext, nonce)
```

### Key Storage

| Location | Content | Permissions |
|----------|---------|-------------|
| `~/.set-core/chat-keys/{project}.key` | Private key (base64) | 0600 |
| `.wt-control/members/{name}.json` | Public key + fingerprint | git tracked |

**Fingerprint:** SHA256(public_key)[:8] - 8 hex characters, for human verification

## Message Format

### Wire Format (messages.jsonl)

```json
{
  "id": "uuid-v4",
  "ts": "2026-01-25T14:30:00Z",
  "from": "john@workstation",
  "to": "peter@laptop",
  "enc": "base64-ciphertext",
  "nonce": "base64-24-bytes"
}
```

### Plaintext Content (before encryption)

```json
{
  "text": "Hey, can you review my PR?"
}
```

**Why JSON in plaintext?** Future extensibility (reactions, formatting, etc.)

## Sync Mechanism

### Send Flow

```
1. User types message, clicks Send
2. Encrypt: Box(my_priv, their_pub).encrypt(plaintext)
3. Append to .wt-control/chat/messages.jsonl
4. git add && git commit --amend && git push --force-with-lease
```

**Why amend + force-push?**
- Less commit noise in history
- Messages.jsonl in a single "Chat update" commit
- Force-with-lease is safe: doesn't overwrite others' changes

### Receive Flow

```
1. ChatWorker poll (10s interval)
2. git pull --rebase .wt-control
3. Read messages.jsonl
4. Filter: to == my_name OR from == my_name
5. Decrypt each with appropriate key
6. Display in UI
```

### Unread Tracking

```
~/.set-core/chat-read-state.json:
{
  "last_read_id": {"project1": "uuid", "project2": "uuid"},
  "last_read_ts": {"project1": "2026-01-25T14:35:00Z", ...}
}
```

## UI Components

### ChatDialog Layout

```
┌─────────────────────────────────────────────────────┐
│  Team Chat                                    [X]   │
├─────────────────────────────────────────────────────┤
│  To: [Peter@laptop        ▼]                        │  <- QComboBox
├─────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────┐  │
│  │ [14:30] Me: Hey, review my PR?                │  │  <- QTextEdit (readonly)
│  │ [14:32] Peter: Sure, give me 5 min            │  │
│  └───────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────┤
│  [Type message...                    ] [Send]       │  <- QLineEdit + QPushButton
│  🔒 Encrypted                                       │  <- QLabel
└─────────────────────────────────────────────────────┘
```

### Chat Button States

| State | Appearance | Condition |
|-------|------------|-----------|
| Normal | `[💬]` | No unread, team enabled |
| Unread | `[💬*]` bold | unread_count > 0 |
| Disabled | grayed | Team sync disabled |
| Hidden | invisible | Team not configured |

### Team Worktrees Display

```
┌─────────────────────────────────────────────────────┐
│  myproj   add-auth    ● run   1234  45%   J        │  <- Own
│  myproj   fix-bug     ○ idle  -     -     -        │  <- Own
│  ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈  │  <- Separator
│  peter:   refactor    ● run   -     -     -        │  <- Team (gray, italic)
│  anna:    add-tests   ⚡ wait  -     -     -        │  <- Team (gray, italic)
└─────────────────────────────────────────────────────┘
```

**Team row properties:**
- Gray text, italic font
- Member name prefix (abbreviated)
- Not clickable (no row_to_worktree mapping)
- Only status icon, no PID/Ctx%/J

## Security Considerations

### Guarantees

- **Confidentiality:** Only sender and recipient can read
- **Integrity:** Poly1305 MAC ensures it
- **Authenticity:** Keypair ownership = identity

### Limitations

- **No forward secrecy:** Compromised private key = all old messages readable
- **Metadata visible:** Timestamps, sender/recipient in git history
- **Trust on first use:** No key verification (fingerprint is manual)

### Mitigations

- Private key 0600 permissions
- Key directory 0700
- Recommend: don't use on shared machines

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No key for project | "Generate key in Settings" message |
| Recipient has no key | Not shown in dropdown |
| Decryption fails | "[Decryption failed]" placeholder |
| Network/git error | Silent retry, no UI error |
| PyNaCl not installed | "Install PyNaCl" message in Settings |

## File Changes Summary

| File | Changes |
|------|---------|
| `gui/chat_crypto.py` | NEW: Encryption module |
| `gui/main.py` | ChatDialog, ChatWorker, button, team rows |
| `gui/requirements.txt` | + PyNaCl>=1.5.0 |
| `bin/wt-control-chat` | NEW: CLI chat commands |
| `bin/wt-control-sync` | + chat_public_key in member.json |
| `bin/wt-status` | Filter .wt-control worktree |
