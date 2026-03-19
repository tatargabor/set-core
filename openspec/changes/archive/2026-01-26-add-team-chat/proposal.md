# Proposal: Add Encrypted Team Chat

JIRA Key: TBD
Story: EXAMPLE-466

## Summary

End-to-end encrypted 1:1 chat between team members in the Control Center, with git-based synchronization via the wt-control branch.

## Motivation

Team sync (Phase 1-2) is already working - we can see who's working on what. A simple, secure communication channel is needed:

- No need to switch to Slack for quick questions
- Secure communication (E2E encrypted)
- Integrated into the existing workflow
- Offline-first: git-based, no server needed

### Use Cases

1. **Quick questions**: "Need a review for my PR?"
2. **Coordination**: "Don't touch file X, I'm modifying it right now"
3. **Status updates**: "5 minutes and the feature will be ready"

## Proposed Solution

### End-to-end Encryption (NaCl)

- PyNaCl library (libsodium wrapper)
- Asymmetric keypair per user per project
- Public key: `member.json` (synced via git)
- Private key: `~/.set-core/chat-keys/{project}.key` (local, NEVER in git!)

### Architecture

```
~/.set-core/
  chat-keys/
    {project}.key           # Private key (0600 permissions)

.wt-control/                # Hidden worktree in the project
  chat/
    messages.jsonl          # Encrypted messages (append-only)
  members/
    {name}.json             # + chat_public_key, chat_key_fingerprint
```

## Scope

### In Scope

- 1:1 encrypted chat
- Key generation in Settings
- Chat button in toolbar (unread indicator)
- ChatDialog: recipient dropdown, history, send
- CLI: `wt-control-chat send/read`
- `.wt-control` worktree filtered from the list

### Out of Scope

- Group chat
- File attachments
- Read receipts
- Message editing/deletion
- Key rotation

## Dependencies

- PyNaCl >= 1.5.0
- Existing: wt-control-init, wt-control-sync
- Team sync enabled in Settings
