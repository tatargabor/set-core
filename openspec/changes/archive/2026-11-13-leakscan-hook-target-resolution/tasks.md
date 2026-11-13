## 1. Hook

- [x] 1.1 Resolve every `cd`/`pushd` before the verb in order, then `-C`; expand `~` and variables; report certainty [REQ: both-actors-are-bound-at-commit-time]
- [x] 1.2 A certain non-repository target is not refused and is announced; an uncertain one falls back and never fails open [REQ: both-actors-are-bound-at-commit-time]
- [x] 1.3 A scanner traceback is refused with a message naming the crash [REQ: both-actors-are-bound-at-commit-time]

## 2. Scanner

- [x] 2.1 `sh()` and `_sh_timeout()` decode with `errors="replace"` [REQ: both-actors-are-bound-at-commit-time]

## 3. Tests

- [x] 3.1 cd chain clean/leaking, `-C`, certain non-repo, uncertain never fails open, crash message, non-UTF-8 staged file found and clean. Against the old code 6 of 8 fail; the two that pass there guard against a hole, and a mutant that fails open on any non-repo target is caught [REQ: both-actors-are-bound-at-commit-time]
