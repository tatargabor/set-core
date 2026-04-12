## 1. Dispatcher — DEBUG for all return paths

- [x] 1.01 `_build_rule_injection()`: log DEBUG when rules_dir missing (~L96), when no matched globs (~L113), when no parts (~L139), when rule file unreadable (except at ~L127)
- [x] 1.02 `_find_design_brief()`: log DEBUG showing which 3 paths were checked and none found (~L150)
- [x] 1.03 `_build_per_change_design()`: log DEBUG when brief_path missing (~L168), bridge_path missing (~L172), command fails (~L183)
- [x] 1.04 `_reinstall_deps_if_needed()`: log DEBUG when sha same (~L287), git diff fails (~L290), no lockfile changes (~L293), no package manager (~L296)
- [x] 1.05 `copy_env_files()`: log DEBUG when wt_path missing (~L442)
- [x] 1.06 `prune_worktree_context()`: log DEBUG when .claude dir missing (~L516), commands dir missing (~L520)
- [x] 1.07 `_build_conventions_summary()`: log DEBUG when file missing (~L937), parse fails (~L942), categories empty (~L946)
- [x] 1.08 `_detect_i18n_sidecar()`: log DEBUG when package.json missing (~L967), no i18n lib (~L984), no message dir (~L995)
- [x] 1.09 `_load_requirements_lookup()`: log DEBUG when digest_dir empty (~L1172), requirements.json missing (~L1175)
- [x] 1.10 `_build_review_learnings()`: log DEBUG when findings_path missing (~L1232), no patterns (~L1263)
- [x] 1.11 `_build_pk_context()`: log DEBUG showing pk_candidates checked (~L1325), which condition failed (~L1330)
- [x] 1.12 `_inject_feature_rules()`: log DEBUG when pk_file/yq missing (~L1383), feature names cmd fails (~L1390)
- [x] 1.13 `_setup_digest_context()`: log DEBUG when index.json missing (~L1901), parse fails (~L1907), change not found (~L1913)

## 2. Dispatcher — except handler upgrades

- [x] 2.1 `_build_rule_injection()` L127: `except OSError: continue` → add `logger.debug("Rule file unreadable: %s", full_path)`
- [x] 2.2 `dispatch_change()` L1603: `except Exception: pass` (env_vars) → `logger.warning("Failed to write env_vars to .env: %s", e)`
- [x] 2.3 `_redispatch_change()` L748: `except: pass` (loop-state read) → `logger.debug("Could not read loop-state for iter_count: %s", e)`
- [x] 2.4 `_load_serialize_triggers()` L2076: `except: return []` → `logger.warning("Failed to load serialize triggers: %s", e)`
- [x] 2.5 `pause_change()` L2221: `except: pass` (PID/signal) → `logger.warning("Failed to pause %s: %s", change_name, e)`

## 3. Merger — SetRuntime elimination and digest_dir fix

- [x] 3.1 `_run_integration_gates()` L1276: replace `SetRuntime().digest_dir` with state_file-relative + log resolved path
- [x] 3.2 `_archive_worktree_logs()` L208: log WARNING on SetRuntime fallback
- [x] 3.3 Add `logger.debug("Coverage gate: digest_dir=%s, plan_exists=%s", ...)` before the coverage check

## 4. Merger — `_detect_own_spec_files` rewrite

- [x] 4.1 Primary detection: `git ls-tree main tests/e2e/` vs `os.listdir(wt_path/tests/e2e/)` — own = worktree - main
- [x] 4.2 Secondary: `git log --no-merges --diff-filter=AM main..HEAD -- tests/e2e/` for modified specs
- [x] 4.3 Manifest fallback: validate file existence, fuzzy match change name in filenames
- [x] 4.4 Log every detection step: `logger.debug("Own spec detection: main_specs=%s, wt_specs=%s, own=%s", ...)`
- [x] 4.5 Log WARNING if all methods return empty: `"Could not detect own spec files for %s — two-phase E2E disabled"`

## 5. Merger — DEBUG for all return paths

- [x] 5.01 `_final_token_collect()`: log DEBUG when wt_path missing (~L57), loop-state missing (~L60)
- [x] 5.02 `_archive_worktree_logs()`: log DEBUG showing which logs_src path used (primary vs legacy fallback, ~L200)
- [x] 5.03 `_resolve_retention()`: log DEBUG showing config path used and result (~L274)
- [x] 5.04 `_apply_merge_strategies()`: log DEBUG when NullProfile (~L356), when no strategies (~L359)
- [x] 5.05 `_clean_untracked_merge_conflicts()`: log DEBUG when diff fails or no added files (~L404)
- [x] 5.06 `_post_merge_deps_install()`: log DEBUG when no lockfile detected (~L1817)
- [x] 5.07 `_persist_review_learnings()`: log DEBUG when findings_path missing (~L1839)

## 6. Merger — except handler upgrades

- [x] 6.1 L220: `except Exception: pass` (log file copy) → `logger.debug("Failed to copy log %s: %s", f, e)`
- [x] 6.2 L306: `except Exception: pass` (milestone cleanup) → `logger.debug("Milestone cleanup failed: %s", e)`
- [x] 6.3 L340: `logger.debug` → `logger.warning` (merge strategy failure)
- [x] 6.4 L385: `except Exception: pass` (untracked conflict cleanup) → `logger.debug("Untracked cleanup failed: %s", e)`
- [x] 6.5 L492, L582: `logger.debug` → `logger.warning` (coverage update failure)
- [x] 6.6 L592: silent profile fallback → `logger.warning("Profile post-merge failed, using legacy: %s", e)`
- [x] 6.7 L856: `except Exception: pass` in `_detect_own_spec_files` → `logger.debug("Git spec detection failed: %s", e)`

## 7. Merger — load_profile() path fixes

- [x] 7.1 L354 `_apply_merge_strategies()`: `load_profile()` → `load_profile(os.getcwd())` + log which path
- [x] 7.2 L589 post-merge deps: add `logger.debug("load_profile for post-merge: cwd=%s", os.getcwd())`
- [x] 7.3 L1453 `execute_merge_queue()`: add `logger.debug("Profile for merge queue: %s", type(profile).__name__)`
- [x] 7.4 L1994 `_parse_test_coverage_if_applicable()`: pass explicit path instead of default

## 8. Engine — digest_dir and SetRuntime fixes

- [x] 8.1 `_dispatch_ready_safe()`: log the resolved _project_dir and _digest_dir at DEBUG
- [x] 8.2 `_gap_check_skip_replan()` L1767: log resolved digest_dir
- [x] 8.3 Replan L1944: log resolved digest_dir
- [x] 8.4 Terminal completion L2459: state_file-relative + SetRuntime fallback with WARNING

## 9. Engine — except handler upgrades

- [x] 9.1 L928: `except Exception: pass` (watchdog event) → `logger.debug("Watchdog event emit failed: %s", e)`
- [x] 9.2 L1303: `except Exception: pass` (git diff test classification) → `logger.debug("Git diff for test classification failed: %s", e)`
- [x] 9.3 L1370: `except Exception: pass` (git history) → `logger.debug("Git history extraction failed: %s", e)`
- [x] 9.4 L2513: `except Exception: pass` (HTML report) → `logger.debug("HTML report generation failed: %s", e)`
- [x] 9.5 L2527: `except Exception: pass` (review findings summary) → `logger.debug("Review findings summary failed: %s", e)`

## 10. Verifier — gate executor entry/exit logging

- [x] 10.1 `_execute_build_gate()`: add `logger.info("Gate[build] START %s wt=%s cmd=%s", ...)`
- [x] 10.2 `_execute_test_gate()`: add `logger.info("Gate[test] START %s wt=%s cmd=%s", ...)`
- [x] 10.3 `_execute_e2e_coverage_gate()`: add entry log with scope and requirement count
- [x] 10.4 `_execute_review_gate()`: add entry log with model and wt_path
- [x] 10.5 `_execute_spec_verify_gate()`: add entry log with wt_path
- [x] 10.6 All gate executors: add `Gate[name] END` at every return point

## 11. Verifier — manifest update at agent completion

- [x] 11.1 In `handle_change_done()`, scan `tests/e2e/*.spec.{ts,js}` and update e2e-manifest.json with actual filenames
- [x] 11.2 Log: `"Updated e2e-manifest.json: %d spec files found: %s"`

## 12. Verifier — except handler upgrades

- [x] 12.1 L2617: `except Exception: pass` (0-commits check) → `logger.debug("Git commit count check failed: %s", e)`
- [x] 12.2 L2628: `except Exception: pass` (model resolution) → `logger.debug("Model resolution from state failed: %s", e)`
- [x] 12.3 L1363: `except Exception: pass` (profile rules) → `logger.warning("Profile verification rules failed: %s", e)`
- [x] 12.4 L1882: `except (ValueError, TypeError): pass` (started_at parse) → `logger.debug("started_at parse failed: %s", e)`
- [x] 12.5 L1921: `except: pass` (set-usage JSON) → `logger.debug("set-usage JSON parse failed: %s", e)`

## 13. Verifier — DEBUG for silent paths

- [x] 13.1 `_read_loop_state()`: log DEBUG when file missing or parse fails
- [x] 13.2 `_execute_build_gate()`: log DEBUG when package.json missing
- [x] 13.3 `handle_change_done()`: log WARNING when wt_path is empty and checks are skipped

## 14. Bash script logging

- [x] 14.1 `lib/orchestration/dispatcher.sh`: log_info at all 3 Python exec points showing state_file, directives, cwd
- [x] 14.2 `bin/set-merge`: bash merge logging deferred — Python merger.py handles all merge logging now
- [x] 14.3 `bin/set-new`: bash worktree logging deferred — Python dispatcher.py handles worktree creation logging
- [x] 14.4 Bash scripts already have common `log_info()`/`log_warn()` in set-orchestrate

## 15. Sentinel log awareness

- [x] 15.1 Update `templates/core/rules/sentinel-autonomy.md`: add directive to scan logs for `[ANOMALY]` and WARNING
- [x] 15.2 Add to sentinel prompt: "When fixing a bug, also check if the failure path has adequate logging"
- [x] 15.3 Add to sentinel prompt: "After each poll cycle, check orchestration log for new [ANOMALY] entries"
