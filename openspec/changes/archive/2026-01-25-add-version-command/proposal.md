# Change: Add Version Command

JIRA Key: EXAMPLE-561
Story: EXAMPLE-466

## Why
Currently there's no easy way to check which version of set-core is installed. This makes troubleshooting and support difficult.

## What Changes
- New `wt-version` command that displays:
  - Git branch name
  - Commit hash (short)
  - Commit date
  - Source directory path
- Add to install.sh script list
- Dynamic version reading from source repo (scripts are symlinked)

## Impact
- Affected specs: none (new command)
- Affected code: bin/wt-version, install.sh
