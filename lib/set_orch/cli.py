from __future__ import annotations

"""CLI entry point for set-orch-core.

This module is the canonical implementation. bin/set-orch-core delegates here.
pyproject.toml [project.scripts] also points here for pip-installed environments.
"""

import argparse
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)


def _default_plan_output() -> str:
    """CLI default for --output: filename of the live lineage's plan file.

    Delegates to LineagePaths so the literal lives in the resolver alone.
    """
    from .paths import LineagePaths
    return os.path.basename(LineagePaths(os.getcwd()).plan_file)


def _default_digest_dir() -> str:
    """CLI default for --dir: project-relative digest directory path.

    Delegates to LineagePaths so the literal lives in the resolver alone.
    """
    from .paths import LineagePaths
    lp = LineagePaths(os.getcwd())
    return os.path.relpath(lp.digest_dir, os.getcwd())


def cmd_process(args):
    """Dispatch process subcommands."""
    from .process import check_pid, safe_kill, find_orphans

    if args.process_cmd == "check-pid":
        result = check_pid(args.pid, args.expect_cmd)
        json.dump({"alive": result.alive, "match": result.match}, sys.stdout)
        print()
        sys.exit(0 if (result.alive and result.match) else 1)

    elif args.process_cmd == "safe-kill":
        result = safe_kill(args.pid, args.expect_cmd, timeout=args.timeout)
        json.dump({"result": result.outcome, "signal": result.signal}, sys.stdout)
        print()
        sys.exit(0)

    elif args.process_cmd == "find-orphans":
        known = set()
        if args.known_pids:
            known = {int(p) for p in args.known_pids.split(",") if p.strip()}
        orphans = find_orphans(args.expect_cmd, known)
        json.dump(
            [{"pid": o.pid, "cmdline": o.cmdline, "change": o.change} for o in orphans],
            sys.stdout,
        )
        print()
        sys.exit(0)


def cmd_state(args):
    """Dispatch state subcommands."""
    from .state import (
        advance_phase,
        cascade_failed_deps,
        count_changes_by_status,
        deps_satisfied,
        get_change_status,
        get_changes_by_status,
        init_state,
        load_state,
        query_changes,
        reconstruct_state_from_events,
        topological_sort,
        update_change_field,
        update_state_field,
    )

    if args.state_cmd == "init":
        init_state(
            args.plan_file,
            args.output,
            spec_path=getattr(args, "spec", None),
            project_path=getattr(args, "project", None),
            sentinel_session_id=getattr(args, "session_id", None),
        )
        sys.exit(0)

    elif args.state_cmd == "query":
        state = load_state(args.file)
        changes = query_changes(state, status=args.status)
        json.dump([c.to_dict() for c in changes], sys.stdout, indent=2)
        print()
        sys.exit(0)

    elif args.state_cmd == "get":
        state = load_state(args.file)
        for c in state.changes:
            if c.name == args.change:
                val = getattr(c, args.field, None)
                if val is None and args.field in c.extras:
                    val = c.extras[args.field]
                # Serialize dataclass objects to dict for JSON output
                if hasattr(val, "to_dict"):
                    val = val.to_dict()
                if isinstance(val, (dict, list)):
                    json.dump(val, sys.stdout)
                    print()
                else:
                    print(val if val is not None else "")
                sys.exit(0)
        print(f"Change not found: {args.change}", file=sys.stderr)
        sys.exit(1)

    elif args.state_cmd == "update-field":
        value = json.loads(args.value)
        update_state_field(args.file, args.field, value)
        sys.exit(0)

    elif args.state_cmd == "update-change":
        value = json.loads(args.value)
        event_bus = _make_event_bus(args.file)
        update_change_field(
            args.file, args.name, args.field, value, event_bus=event_bus
        )
        sys.exit(0)

    elif args.state_cmd == "get-status":
        state = load_state(args.file)
        status = get_change_status(state, args.name)
        print(status)
        sys.exit(0)

    elif args.state_cmd == "count-by-status":
        state = load_state(args.file)
        count = count_changes_by_status(state, args.status)
        print(count)
        sys.exit(0)

    elif args.state_cmd == "changes-by-status":
        state = load_state(args.file)
        names = get_changes_by_status(state, args.status)
        for n in names:
            print(n)
        sys.exit(0)

    elif args.state_cmd == "deps-satisfied":
        state = load_state(args.file)
        satisfied = deps_satisfied(state, args.name)
        sys.exit(0 if satisfied else 1)

    elif args.state_cmd == "cascade-failed":
        from .state import locked_state
        event_bus = _make_event_bus(args.file)
        with locked_state(args.file) as state:
            count = cascade_failed_deps(state, event_bus=event_bus)
        print(count)
        sys.exit(0)

    elif args.state_cmd == "topo-sort":
        with open(args.plan_file, "r") as f:
            plan = json.load(f)
        names = topological_sort(plan.get("changes", []))
        for n in names:
            print(n)
        sys.exit(0)

    elif args.state_cmd == "advance-phase":
        from .state import locked_state
        event_bus = _make_event_bus(args.file)
        with locked_state(args.file) as state:
            advanced = advance_phase(state, event_bus=event_bus)
        sys.exit(0 if advanced else 1)

    elif args.state_cmd == "reconstruct":
        success = reconstruct_state_from_events(
            args.file, events_path=args.events
        )
        sys.exit(0 if success else 1)


def _make_event_bus(state_file: str):
    """Create an EventBus from a state file path."""
    from pathlib import Path
    from .events import EventBus

    stem = Path(state_file).stem.replace("-state", "")
    log_path = str(Path(state_file).parent / f"{stem}-events.jsonl")
    return EventBus(log_path=log_path)


def cmd_template(args):
    """Dispatch template subcommands."""
    from . import templates

    input_data = {}
    if args.input_file:
        src = sys.stdin if args.input_file == "-" else open(args.input_file)
        input_data = json.load(src)
        if src is not sys.stdin:
            src.close()

    if args.template_cmd == "proposal":
        print(templates.render_proposal(
            change_name=args.change or input_data.get("change_name", ""),
            scope=args.scope or input_data.get("scope", ""),
            roadmap_item=args.roadmap or input_data.get("roadmap_item", ""),
            memory_ctx=input_data.get("memory_ctx", ""),
            spec_ref=input_data.get("spec_ref", ""),
        ))

    elif args.template_cmd == "review":
        print(templates.render_review_prompt(
            scope=input_data.get("scope", ""),
            diff_output=input_data.get("diff_output", ""),
            req_section=input_data.get("req_section", ""),
            design_compliance=input_data.get("design_compliance", ""),
            security_rules=input_data.get("security_rules", ""),
            change_name=input_data.get("change_name", ""),
        ))

    elif args.template_cmd == "fix":
        print(templates.render_fix_prompt(
            change_name=input_data.get("change_name", ""),
            scope=input_data.get("scope", ""),
            output_tail=input_data.get("output_tail", ""),
            smoke_cmd=input_data.get("smoke_cmd", ""),
            modified_files=input_data.get("modified_files", ""),
            multi_change_context=input_data.get("multi_change_context", ""),
            variant=input_data.get("variant", "smoke"),
        ))

    elif args.template_cmd == "planning":
        print(templates.render_planning_prompt(
            input_content=input_data.get("input_content", ""),
            specs=input_data.get("specs", ""),
            memory=input_data.get("memory", ""),
            replan_ctx=input_data.get("replan_ctx", {}),
            mode=args.mode or input_data.get("mode", "spec"),
            phase_instruction=input_data.get("phase_instruction", ""),
            input_mode=input_data.get("input_mode", ""),
            test_infra_context=input_data.get("test_infra_context", ""),
            pk_context=input_data.get("pk_context", ""),
            req_context=input_data.get("req_context", ""),
            active_changes=input_data.get("active_changes", ""),
            coverage_info=input_data.get("coverage_info", ""),
            design_context=input_data.get("design_context", ""),
            team_mode=input_data.get("team_mode", False),
        ))

    elif args.template_cmd == "audit":
        print(templates.render_audit_prompt(
            spec_text=input_data.get("spec_text", ""),
            requirements=input_data.get("requirements", []),
            changes=input_data.get("changes", []),
            coverage=input_data.get("coverage", ""),
            mode=input_data.get("mode", "spec"),
        ))


def cmd_config(args):
    """Dispatch config subcommands.

    Migrated from: utils.sh (parse_directives, resolve_directives, load_config_file,
    parse_duration, format_duration, brief_hash, parse_next_items, find_input)
    """
    from .config import (
        brief_hash,
        find_input,
        format_duration,
        load_config_file,
        parse_directives,
        parse_duration,
        parse_next_items,
        resolve_directives,
    )

    if args.config_cmd == "parse-directives":
        result = parse_directives(args.file)
        json.dump(result, sys.stdout, indent=2)
        print()

    elif args.config_cmd == "resolve-directives":
        cli_overrides = {}
        if args.override:
            for item in args.override:
                k, _, v = item.partition("=")
                if v.isdigit():
                    cli_overrides[k] = int(v)
                elif v in ("true", "false"):
                    cli_overrides[k] = v == "true"
                else:
                    cli_overrides[k] = v
        result = resolve_directives(
            args.file,
            config_path=args.config,
            cli_overrides=cli_overrides or None,
        )
        json.dump(result, sys.stdout, indent=2)
        print()

    elif args.config_cmd == "load-config":
        result = load_config_file(args.file)
        json.dump(result, sys.stdout, indent=2)
        print()

    elif args.config_cmd == "parse-duration":
        print(parse_duration(args.value))

    elif args.config_cmd == "format-duration":
        print(format_duration(int(args.value)))

    elif args.config_cmd == "brief-hash":
        print(brief_hash(args.file))

    elif args.config_cmd == "parse-next-items":
        items = parse_next_items(args.file)
        json.dump(items, sys.stdout)
        print()

    elif args.config_cmd == "find-input":
        try:
            mode, path = find_input(
                spec_override=args.spec,
                brief_override=args.brief,
            )
            json.dump({"mode": mode, "path": path}, sys.stdout)
            print()
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)


def cmd_events(args):
    """Dispatch events subcommand.

    Migrated from: events.sh:cmd_events() L143-155, query_events() L92-139
    """
    from .events import EventBus

    log_path = args.log
    if not log_path:
        import os
        state_file = os.environ.get("STATE_FILENAME", "")
        if state_file:
            from pathlib import Path
            stem = Path(state_file).stem.replace("-state", "")
            log_path = str(Path(state_file).parent / f"{stem}-events.jsonl")

    if not log_path:
        print("No events log specified. Use --log or set STATE_FILENAME.", file=sys.stderr)
        sys.exit(1)

    bus = EventBus(log_path=log_path, enabled=False)  # read-only, no writing
    events = bus.query(
        event_type=args.type,
        change=args.change,
        since=args.since,
        last_n=args.last,
    )

    if args.json:
        json.dump(events, sys.stdout, indent=2)
        print()
    else:
        print(bus.format_table(events))


def cmd_plan(args):
    """Dispatch plan subcommands.

    Migrated from: lib/orchestration/planner.sh (validate_plan, detect_test_infra,
    check_triage_gate, check_scope_overlap, build_decomposition_context,
    enrich_plan_metadata, summarize_spec, collect_replan_context)
    """
    from .planner import (
        build_decomposition_context,
        check_scope_overlap,
        check_triage_gate,
        collect_replan_context,
        detect_test_infra,
        enrich_plan_metadata,
        summarize_spec,
        validate_plan,
    )

    if args.plan_cmd == "validate":
        result = validate_plan(args.plan_file, digest_dir=args.digest_dir)
        json.dump(result.to_dict(), sys.stdout)
        print()
        sys.exit(0 if result.ok else 1)

    elif args.plan_cmd == "detect-test-infra":
        infra = detect_test_infra(args.project_dir or ".")
        json.dump(infra.to_dict(), sys.stdout)
        print()
        sys.exit(0)

    elif args.plan_cmd == "check-triage":
        status = check_triage_gate(args.digest_dir, auto_defer=args.auto_defer)
        print(status.status)
        sys.exit(0)

    elif args.plan_cmd == "check-scope-overlap":
        overlaps = check_scope_overlap(
            args.plan_file,
            state_path=args.state_file,
            pk_path=args.pk_file,
        )
        json.dump(
            {"warnings": [o.to_dict() for o in overlaps]},
            sys.stdout,
        )
        print()
        sys.exit(0)

    elif args.plan_cmd == "build-context":
        input_data = {}
        if args.input_file:
            src = sys.stdin if args.input_file == "-" else open(args.input_file)
            input_data = json.load(src)
            if src is not sys.stdin:
                src.close()

        from . import templates

        ctx = build_decomposition_context(
            input_mode=input_data.get("input_mode", input_data.get("mode", "spec")),
            input_path=input_data.get("input_path", ""),
            phase_hint=input_data.get("phase_instruction", ""),
            existing_specs=input_data.get("specs", ""),
            active_changes=input_data.get("active_changes", ""),
            memory_context=input_data.get("memory", ""),
            design_context=input_data.get("design_context", ""),
            pk_context=input_data.get("pk_context", ""),
            req_context=input_data.get("req_context", ""),
            test_infra_context=input_data.get("test_infra_context", ""),
            coverage_info=input_data.get("coverage_info", ""),
            replan_ctx=input_data.get("replan_ctx"),
            team_mode=input_data.get("team_mode", False),
        )
        print(templates.render_planning_prompt(**ctx))
        sys.exit(0)

    elif args.plan_cmd == "enrich-metadata":
        import os

        with open(args.plan_file, "r") as f:
            plan_data = json.load(f)

        # Determine plan version
        plan_version = args.plan_version or 1
        if plan_version == 1 and os.path.exists(args.plan_file):
            plan_version = plan_data.get("plan_version", 0) + 1

        enriched = enrich_plan_metadata(
            plan_data,
            hash_val=args.hash,
            input_mode=args.input_mode,
            input_path=args.input_path,
            plan_version=plan_version,
            replan_cycle=args.replan_cycle,
            state_path=args.state_file,
        )
        with open(args.plan_file, "w") as f:
            json.dump(enriched, f, indent=2)
        sys.exit(0)

    elif args.plan_cmd == "summarize-spec":
        summary = summarize_spec(
            args.spec_file,
            phase_hint=args.phase_hint or "",
            model=args.model or "haiku",
        )
        print(summary)
        sys.exit(0)

    elif args.plan_cmd == "replan-context":
        ctx = collect_replan_context(args.state_file)
        json.dump(ctx, sys.stdout)
        print()
        sys.exit(0)

    elif args.plan_cmd == "run":
        from .planner import run_planning_pipeline, plan_via_agent
        import os as _os

        plan_method = getattr(args, "method", "api")

        if plan_method == "agent":
            ok = plan_via_agent(
                spec_path=args.input_path,
                plan_filename=args.output or _default_plan_output(),
                phase_hint=getattr(args, "phase_hint", "") or "",
            )
            if ok:
                print(json.dumps({"status": "ok", "method": "agent"}))
                sys.exit(0)
            else:
                print(json.dumps({"status": "error", "method": "agent"}), file=sys.stderr)
                sys.exit(1)
        else:
            try:
                plan_data = run_planning_pipeline(
                    input_mode=args.input_mode,
                    input_path=args.input_path,
                    state_path=getattr(args, "state_file", "") or "",
                    model=getattr(args, "model", "opus") or "opus",
                    team_mode=getattr(args, "team", False),
                    replan_cycle=getattr(args, "replan_cycle", None),
                )
                output_path = args.output or _default_plan_output()
                with open(output_path, "w") as f:
                    json.dump(plan_data, f, indent=2)
                print(json.dumps({
                    "status": "ok",
                    "method": "api",
                    "changes": len(plan_data.get("changes", [])),
                    "output": output_path,
                }))
                sys.exit(0)
            except RuntimeError as e:
                print(json.dumps({"status": "error", "error": str(e)}), file=sys.stderr)
                sys.exit(1)


def cmd_report(args):
    """Dispatch report subcommands.

    Migrated from: lib/orchestration/reporter.sh generate_report()
    """
    from .reporter import generate_report

    if args.report_cmd == "generate":
        output = generate_report(
            state_path=args.state or "",
            plan_path=args.plan or "",
            digest_dir=args.digest_dir or "",
            output_path=args.output,
        )
        print(output)
        sys.exit(0)


def cmd_dispatch(args):
    """Dispatch dispatcher subcommands.

    Migrated from: lib/orchestration/dispatcher.sh
    """
    from .dispatcher import (
        bootstrap_worktree,
        dispatch_change,
        dispatch_ready_changes,
        dispatch_via_wt_loop,
        pause_change,
        recover_orphaned_changes,
        redispatch_change,
        resolve_change_model,
        resume_change,
        resume_stalled_changes,
        resume_stopped_changes,
        retry_failed_builds,
        prune_worktree_context,
        sync_worktree_with_main,
    )

    event_bus = _make_event_bus(args.state) if hasattr(args, "state") and args.state else None

    if args.dispatch_cmd == "sync-worktree":
        result = sync_worktree_with_main(args.wt_path, args.change)
        json.dump({"ok": result.ok, "message": result.message, "behind_count": result.behind_count, "auto_resolved": result.auto_resolved}, sys.stdout)
        print()
        sys.exit(0 if result.ok else 1)

    elif args.dispatch_cmd == "bootstrap":
        copied = bootstrap_worktree(args.project_path, args.wt_path)
        print(copied)
        sys.exit(0)

    elif args.dispatch_cmd == "prune-context":
        pruned = prune_worktree_context(args.wt_path)
        print(pruned)
        sys.exit(0)

    elif args.dispatch_cmd == "resolve-model":
        from .state import load_state
        state = load_state(args.state)
        for c in state.changes:
            if c.name == args.change:
                model = resolve_change_model(c, args.default_model, args.model_routing)
                print(model)
                sys.exit(0)
        print(f"Change not found: {args.change}", file=sys.stderr)
        sys.exit(1)

    elif args.dispatch_cmd == "dispatch-change":
        ok = dispatch_change(
            args.state, args.change,
            default_model=args.default_model or "opus",
            model_routing=args.model_routing or "off",
            team_mode=args.team,
            context_pruning=not args.no_prune,
            event_bus=event_bus,
            input_mode=args.input_mode or "",
            input_path=args.input_path or "",
            digest_dir=args.digest_dir or "",
        )
        sys.exit(0 if ok else 1)

    elif args.dispatch_cmd == "dispatch-ready":
        count = dispatch_ready_changes(
            args.state, args.max_parallel,
            default_model=args.default_model or "opus",
            model_routing=args.model_routing or "off",
            team_mode=args.team,
            context_pruning=not args.no_prune,
            event_bus=event_bus,
            input_mode=args.input_mode or "",
            input_path=args.input_path or "",
            digest_dir=args.digest_dir or "",
        )
        print(count)
        sys.exit(0)

    elif args.dispatch_cmd == "pause":
        ok = pause_change(args.state, args.change, event_bus=event_bus)
        sys.exit(0 if ok else 1)

    elif args.dispatch_cmd == "resume":
        ok = resume_change(
            args.state, args.change,
            default_model=args.default_model or "opus",
            model_routing=args.model_routing or "off",
            team_mode=args.team,
            event_bus=event_bus,
        )
        sys.exit(0 if ok else 1)

    elif args.dispatch_cmd == "resume-stopped":
        count = resume_stopped_changes(args.state, event_bus=event_bus)
        print(count)
        sys.exit(0)

    elif args.dispatch_cmd == "resume-stalled":
        count = resume_stalled_changes(args.state, event_bus=event_bus)
        print(count)
        sys.exit(0)

    elif args.dispatch_cmd == "recover-orphans":
        count = recover_orphaned_changes(args.state, event_bus=event_bus)
        print(count)
        sys.exit(0)

    elif args.dispatch_cmd == "redispatch":
        redispatch_change(
            args.state, args.change,
            failure_pattern=args.failure_pattern or "stuck",
            event_bus=event_bus,
            max_redispatch=args.max_redispatch,
        )
        sys.exit(0)

    elif args.dispatch_cmd == "retry-builds":
        count = retry_failed_builds(args.state, max_retries=args.max_retries, event_bus=event_bus)
        print(count)
        sys.exit(0)


def cmd_verify(args):
    """Dispatch verifier subcommands.

    Migrated from: lib/orchestration/verifier.sh
    """
    from .verifier import (
        build_req_review_section,
        evaluate_verification_rules,
        extract_health_check_url,
        handle_change_done,
        health_check,
        poll_change,
        review_change,
        run_phase_end_e2e,
        run_tests_in_worktree,
        smoke_fix_scoped,
        verify_implementation_scope,
        verify_merge_scope,
    )

    event_bus = _make_event_bus(args.state) if hasattr(args, "state") and args.state else None

    if args.verify_cmd == "run-tests":
        result = run_tests_in_worktree(
            args.wt_path, args.command,
            test_timeout=args.timeout,
            max_chars=args.max_chars,
        )
        json.dump({
            "passed": result.passed,
            "output": result.output,
            "exit_code": result.exit_code,
            "stats": result.stats,
        }, sys.stdout)
        print()
        sys.exit(0 if result.passed else 1)

    elif args.verify_cmd == "review":
        result = review_change(
            args.change, args.wt_path, args.scope,
            review_model=args.model or "sonnet",
            state_file=args.state or "",
        )
        json.dump({
            "has_critical": result.has_critical,
            "output": result.output[:2000],
        }, sys.stdout)
        print()
        sys.exit(1 if result.has_critical else 0)

    elif args.verify_cmd == "evaluate-rules":
        result = evaluate_verification_rules(
            args.change, args.wt_path,
            pk_file=args.pk_file or "",
            event_bus=event_bus,
        )
        json.dump({"errors": result.errors, "warnings": result.warnings}, sys.stdout)
        print()
        sys.exit(1 if result.errors > 0 else 0)

    elif args.verify_cmd == "check-merge-scope":
        result = verify_merge_scope(args.change)
        json.dump({"has_implementation": result.has_implementation, "first_impl_file": result.first_impl_file}, sys.stdout)
        print()
        sys.exit(0 if result.has_implementation else 1)

    elif args.verify_cmd == "check-impl-scope":
        result = verify_implementation_scope(args.change, args.wt_path)
        json.dump({"has_implementation": result.has_implementation, "first_impl_file": result.first_impl_file}, sys.stdout)
        print()
        sys.exit(0 if result.has_implementation else 1)

    elif args.verify_cmd == "health-check":
        ok = health_check(args.url, timeout_secs=args.timeout)
        sys.exit(0 if ok else 1)

    elif args.verify_cmd == "extract-health-url":
        url = extract_health_check_url(args.smoke_cmd)
        print(url)
        sys.exit(0)

    elif args.verify_cmd == "build-req-section":
        section = build_req_review_section(args.change, args.state)
        print(section)
        sys.exit(0)

    elif args.verify_cmd == "poll":
        status = poll_change(
            args.change, args.state,
            test_command=args.test_command or "",
            merge_policy=args.merge_policy or "eager",
            test_timeout=args.test_timeout,
            max_verify_retries=args.max_verify_retries,
            review_before_merge=args.review_before_merge,
            review_model=args.review_model or "sonnet",
            smoke_command=args.smoke_command or "",
            smoke_timeout=args.smoke_timeout,
            e2e_command=args.e2e_command or "",
            e2e_timeout=args.e2e_timeout,
            event_bus=event_bus,
        )
        print(status or "skipped")
        sys.exit(0)

    elif args.verify_cmd == "handle-done":
        handle_change_done(
            args.change, args.state,
            test_command=args.test_command or "",
            merge_policy=args.merge_policy or "eager",
            test_timeout=args.test_timeout,
            max_verify_retries=args.max_verify_retries,
            review_before_merge=args.review_before_merge,
            review_model=args.review_model or "sonnet",
            smoke_command=args.smoke_command or "",
            smoke_timeout=args.smoke_timeout,
            e2e_command=args.e2e_command or "",
            e2e_timeout=args.e2e_timeout,
            event_bus=event_bus,
        )
        sys.exit(0)

    elif args.verify_cmd == "smoke-fix":
        ok = smoke_fix_scoped(
            args.change, args.smoke_cmd, args.smoke_timeout,
            args.smoke_output, args.state,
            max_retries=args.max_retries,
            max_turns=args.max_turns,
        )
        sys.exit(0 if ok else 1)

    elif args.verify_cmd == "phase-e2e":
        ok = run_phase_end_e2e(
            args.command, args.state,
            e2e_timeout=args.timeout,
            event_bus=event_bus,
        )
        sys.exit(0 if ok else 1)


def cmd_serve(args):
    """Start the web dashboard server."""
    import os
    import signal
    import uvicorn

    from .server import create_app

    port = args.port or int(os.environ.get("SET_WEB_PORT", "7400"))
    host = args.host or "0.0.0.0"

    app = create_app()
    print(f"set-web dashboard running at http://{host}:{port}")

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    # Graceful shutdown on SIGTERM
    def handle_sigterm(signum, frame):
        server.should_exit = True

    signal.signal(signal.SIGTERM, handle_sigterm)

    server.run()


def cmd_merge(args):
    """Dispatch merge subcommands.

    Migrated from: lib/orchestration/merger.sh
    """
    from .merger import (
        archive_change,
        cleanup_all_worktrees,
        cleanup_worktree,
        execute_merge_queue,
        merge_change,
        retry_merge_queue,
    )

    event_bus = _make_event_bus(args.state) if hasattr(args, "state") and args.state else None

    if args.merge_cmd == "merge-change":
        result = merge_change(args.change, args.state, event_bus=event_bus)
        json.dump({
            "success": result.success,
            "status": result.status,
            "smoke_result": result.smoke_result,
        }, sys.stdout)
        print()
        sys.exit(0 if result.success else 1)

    elif args.merge_cmd == "execute-queue":
        merged = execute_merge_queue(args.state, event_bus=event_bus)
        json.dump({"merged": merged}, sys.stdout)
        print()
        sys.exit(0)

    elif args.merge_cmd == "retry-queue":
        merged = retry_merge_queue(args.state, event_bus=event_bus)
        json.dump({"merged": merged}, sys.stdout)
        print()
        sys.exit(0)

    elif args.merge_cmd == "archive":
        ok = archive_change(args.change)
        sys.exit(0 if ok else 1)

    elif args.merge_cmd == "cleanup-worktree":
        cleanup_worktree(args.change, args.wt_path)
        sys.exit(0)

    elif args.merge_cmd == "cleanup-all":
        cleaned = cleanup_all_worktrees(args.state)
        json.dump({"cleaned": cleaned}, sys.stdout)
        print()
        sys.exit(0)


def cmd_milestone(args):
    """Dispatch milestone subcommands.

    Migrated from: lib/orchestration/milestone.sh
    """
    from .milestone import (
        cleanup_milestone_servers,
        cleanup_milestone_worktrees,
        run_milestone_checkpoint,
    )

    event_bus = _make_event_bus(args.state) if hasattr(args, "state") and args.state else None

    if args.milestone_cmd == "checkpoint":
        run_milestone_checkpoint(
            args.phase,
            base_port=args.base_port,
            max_worktrees=args.max_worktrees,
            state_file=args.state,
            milestone_dev_server=args.dev_server or "",
            event_bus=event_bus,
        )
        sys.exit(0)

    elif args.milestone_cmd == "cleanup-servers":
        killed = cleanup_milestone_servers(args.state)
        json.dump({"killed": killed}, sys.stdout)
        print()
        sys.exit(0)

    elif args.milestone_cmd == "cleanup-worktrees":
        cleaned = cleanup_milestone_worktrees()
        json.dump({"cleaned": cleaned}, sys.stdout)
        print()
        sys.exit(0)


def cmd_loop(args):
    """Dispatch loop subcommands.

    Ralph loop engine utilities (state, tasks, prompt, error classification).
    """
    if args.loop_cmd == "classify-error":
        from .loop import classify_api_error
        result = classify_api_error(args.log_file)
        json.dump({"error_type": result.error_type, "message": result.message}, sys.stdout)
        print()
        sys.exit(0)

    elif args.loop_cmd == "check-budget":
        from .loop import check_token_budget
        result = check_token_budget(args.used, args.budget)
        json.dump({"action": result}, sys.stdout)
        print()
        sys.exit(0)

    elif args.loop_cmd == "check-done":
        from .loop_tasks import is_done
        done = is_done(args.wt_path, args.done_criteria)
        json.dump({"done": done}, sys.stdout)
        print()
        sys.exit(0 if done else 1)

    elif args.loop_cmd == "detect-action":
        from .loop_prompt import detect_next_change_action
        action = detect_next_change_action(args.wt_path, targeted=args.change or None)
        json.dump({"action": action.action, "change": action.change}, sys.stdout)
        print()
        sys.exit(0)

    elif args.loop_cmd == "build-prompt":
        from .loop_prompt import build_claude_prompt
        prompt_args = build_claude_prompt(
            args.wt_path,
            args.task,
            done_criteria=args.done_criteria,
            change_name=args.change or "",
            previous_commits=args.previous_commits or "",
            manual_task_text=args.manual_tasks or "",
            team_mode=args.team,
        )
        json.dump({"prompt_args": prompt_args}, sys.stdout)
        print()
        sys.exit(0)

    elif args.loop_cmd == "task-status":
        from .loop_tasks import find_tasks_file, check_completion
        tasks_file = find_tasks_file(args.wt_path)
        if not tasks_file:
            json.dump({"found": False}, sys.stdout)
            print()
            sys.exit(1)
        status = check_completion(tasks_file)
        json.dump({
            "found": True,
            "file": tasks_file,
            "total": status.total,
            "done": status.done,
            "pending": status.pending,
            "percent": status.percent,
        }, sys.stdout)
        print()
        sys.exit(0)


def cmd_engine(args):
    """Dispatch engine subcommands.

    Migrated from: lib/orchestration/monitor.sh
    When running as the monitor, registers signal handlers and atexit cleanup.
    """
    import atexit
    import signal

    from .engine import cleanup_orchestrator, monitor_loop, parse_directives

    event_bus = _make_event_bus(args.state) if hasattr(args, "state") and args.state else None

    if args.engine_cmd == "monitor":
        # Parse directives for cleanup context
        directives = None
        try:
            import os
            raw = None
            if os.path.isfile(args.directives):
                with open(args.directives) as f:
                    raw = json.load(f)
            else:
                try:
                    raw = json.loads(args.directives)
                except (json.JSONDecodeError, ValueError):
                    # Temp file deleted — try state file
                    from .engine import load_state
                    st = load_state(args.state)
                    raw = st.extras.get("directives")
            if raw is not None:
                directives = parse_directives(raw)
                # Apply CLI flag overrides
                if getattr(args, "checkpoint_auto_approve", False):
                    directives.checkpoint_auto_approve = True
                cli_timeout = getattr(args, "checkpoint_timeout", 0)
                if cli_timeout:
                    directives.checkpoint_timeout = cli_timeout
        except Exception:
            pass

        # NOTE: atexit cleanup is registered INSIDE monitor_loop after lock acquisition.
        # Registering it here would cause duplicate monitors to set status=stopped on exit.

        # Signal handlers: SIGTERM, SIGINT, SIGHUP → sys.exit(0) → triggers atexit
        # cleanup → _graceful_shutdown_ralph_pids → time.sleep(1) loop.
        #
        # Re-entrancy: the atexit cleanup path sleeps for up to 90s waiting
        # for Ralph PIDs to exit. If a second signal arrives during that
        # window (common case: orchestrator exits voluntarily AND the
        # supervisor sends SIGTERM in parallel) the handler would raise
        # SystemExit from inside the atexit callback, producing:
        #   "Exception ignored in atexit callback: cleanup_orchestrator"
        # Caught on nano-run-20260412-1941. Swapping the handlers to
        # SIG_IGN on first entry keeps the cleanup path atomic — SIGKILL
        # still kills us if the supervisor decides we've timed out.
        def _signal_handler(signum, frame):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
            sys.exit(0)

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGHUP, _signal_handler)

        monitor_loop(
            args.directives,
            args.state,
            poll_interval=args.poll_interval,
            event_bus=event_bus,
            checkpoint_auto_approve=getattr(args, "checkpoint_auto_approve", False),
            checkpoint_timeout=getattr(args, "checkpoint_timeout", 0),
        )
        sys.exit(0)


def cmd_digest(args):
    """Dispatch digest subcommands."""
    from .digest import (
        _clear_cache,
        check_coverage_gaps,
        check_digest_freshness,
        final_coverage_check,
        generate_triage_md,
        merge_planner_resolutions,
        merge_triage_to_ambiguities,
        parse_triage_md,
        populate_coverage,
        run_digest,
        scan_spec_directory,
        update_coverage_status,
        validate_digest,
    )

    # Normalise --dir: None means "use the resolver's live digest dir".
    if getattr(args, "dir", None) is None and hasattr(args, "dir"):
        args.dir = _default_digest_dir()

    if args.digest_cmd == "run":
        if getattr(args, "digest_cache_clear", False):
            _clear_cache()
            logger.info("digest cache cleared (--digest-cache-clear flag)")
        result = run_digest(
            args.spec,
            model=args.model,
            dry_run=args.dry_run,
            digest_dir=getattr(args, "dir", None) or _default_digest_dir(),
            bypass_cache=getattr(args, "no_digest_cache", False),
        )
        if result.validation_warnings:
            for w in result.validation_warnings:
                print(f"WARNING: {w}", file=sys.stderr)
        if not result.ok:
            print(json.dumps({"status": "error", "error": result.error}))
            sys.exit(1)
        print(json.dumps({
            "status": "ok",
            "file_count": result.file_count,
            "req_count": result.req_count,
            "domain_count": result.domain_count,
            "source_hash": result.source_hash,
        }))
        sys.exit(0)

    elif args.digest_cmd == "validate":
        from pathlib import Path
        reqs_path = Path(args.dir) / "requirements.json"
        if not reqs_path.is_file():
            print(json.dumps({"valid": False, "errors": ["No requirements.json found"]}))
            sys.exit(1)
        data = json.loads(reqs_path.read_text())
        errors = validate_digest(data)
        print(json.dumps({"valid": len(errors) == 0, "errors": errors}))
        sys.exit(0 if not errors else 1)

    elif args.digest_cmd == "coverage":
        gaps = check_coverage_gaps(args.dir)
        print(json.dumps({"uncovered": gaps, "count": len(gaps)}))
        sys.exit(0)

    elif args.digest_cmd == "freshness":
        result = check_digest_freshness(args.spec, args.dir)
        print(json.dumps({"freshness": result}))
        sys.exit(0)

    elif args.digest_cmd == "scan":
        scan = scan_spec_directory(args.spec)
        print(json.dumps({
            "file_count": scan.file_count,
            "source_hash": scan.source_hash,
            "master_file": scan.master_file or None,
            "spec_base_dir": scan.spec_base_dir,
            "files": scan.files,
        }))
        sys.exit(0)

    elif args.digest_cmd == "build-prompt":
        from .digest import build_digest_prompt
        scan = scan_spec_directory(args.spec)
        prompt = build_digest_prompt(args.spec, scan)
        print(prompt)
        sys.exit(0)

    elif args.digest_cmd == "populate-coverage":
        from pathlib import Path
        plan_path = Path(args.plan_file)
        if not plan_path.is_file():
            print(json.dumps({"error": f"Plan file not found: {args.plan_file}"}))
            sys.exit(1)
        plan_data = json.loads(plan_path.read_text())
        coverage = populate_coverage(plan_data, args.dir)
        print(json.dumps({"status": "ok", "mapped_count": len(coverage)}))
        sys.exit(0)

    elif args.digest_cmd == "update-coverage":
        update_coverage_status(args.change, args.status, args.dir)
        print(json.dumps({"status": "ok"}))
        sys.exit(0)

    elif args.digest_cmd == "final-coverage":
        summary = final_coverage_check(args.dir)
        print(json.dumps({"summary": summary}))
        sys.exit(0)

    elif args.digest_cmd == "generate-triage":
        from pathlib import Path
        amb_path = Path(args.amb_file)
        if not amb_path.is_file():
            print(json.dumps({"error": "Ambiguities file not found"}))
            sys.exit(1)
        amb_data = json.loads(amb_path.read_text())
        ambiguities = amb_data.get("ambiguities", [])
        existing = args.existing_triage if hasattr(args, "existing_triage") and args.existing_triage else None
        generate_triage_md(ambiguities, args.output, existing)
        print(json.dumps({"status": "ok"}))
        sys.exit(0)

    elif args.digest_cmd == "parse-triage":
        decisions = parse_triage_md(args.triage_file)
        print(json.dumps(decisions))
        sys.exit(0)

    elif args.digest_cmd == "merge-triage":
        decisions = json.loads(args.decisions)
        merge_triage_to_ambiguities(args.amb_file, decisions, args.resolved_by)
        print(json.dumps({"status": "ok"}))
        sys.exit(0)

    elif args.digest_cmd == "merge-planner-resolutions":
        merge_planner_resolutions(args.amb_file, args.plan_file)
        print(json.dumps({"status": "ok"}))
        sys.exit(0)

    elif args.digest_cmd == "parse-response":
        from .digest import parse_digest_response
        import dataclasses
        raw = sys.stdin.read()
        try:
            digest = parse_digest_response(raw)
            print(json.dumps(dataclasses.asdict(digest)))
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    elif args.digest_cmd == "validate-raw":
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print("Invalid JSON", file=sys.stderr)
            sys.exit(1)
        errors = validate_digest(data)
        if errors:
            for e in errors:
                print(f"WARNING: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    elif args.digest_cmd == "stabilize-ids":
        from .digest import stabilize_ids as _stabilize, _dict_to_digest_result
        import dataclasses
        raw = sys.stdin.read()
        data = json.loads(raw)
        digest = _dict_to_digest_result(data)
        stabilized = _stabilize(digest)
        print(json.dumps(dataclasses.asdict(stabilized)))
        sys.exit(0)

    elif args.digest_cmd == "write-output":
        from .digest import write_digest_output, _dict_to_digest_result
        raw = sys.stdin.read()
        data = json.loads(raw)
        digest = _dict_to_digest_result(data)
        scan = scan_spec_directory(args.spec)
        write_digest_output(digest, scan)
        print(json.dumps({"status": "ok"}))
        sys.exit(0)


def cmd_watchdog(args):
    """Dispatch watchdog subcommands."""
    from .watchdog import watchdog_check, heartbeat_data
    from .state import load_state

    if args.watchdog_cmd == "check":
        state = load_state(args.state)
        state_dict = state.to_dict()
        result = watchdog_check(args.change, state_dict, args.state)
        print(json.dumps({
            "action": result.action,
            "reason": result.reason,
            "escalation_level": result.escalation_level,
        }))
        sys.exit(0)

    elif args.watchdog_cmd == "status":
        state = load_state(args.state)
        state_dict = state.to_dict()
        statuses = []
        for c in state_dict.get("changes", []):
            wd = c.get("watchdog")
            if wd:
                statuses.append({
                    "change": c["name"],
                    "status": c.get("status", ""),
                    "escalation_level": wd.get("escalation_level", 0),
                    "consecutive_same_hash": wd.get("consecutive_same_hash", 0),
                    "last_activity_epoch": wd.get("last_activity_epoch", 0),
                })
        print(json.dumps(statuses, indent=2))
        sys.exit(0)


def cmd_audit(args):
    """Dispatch audit subcommands."""
    from .auditor import build_audit_prompt, run_audit
    from .state import load_state

    if args.audit_cmd == "run":
        state = load_state(args.state)
        state_dict = state.to_dict()
        result = run_audit(
            state_dict,
            cycle=args.cycle,
            input_mode=args.input_mode,
            input_path=args.input_path,
            review_model=args.model,
        )
        gap_data = [{"description": g.description, "severity": g.severity} for g in result.gaps]
        print(json.dumps({
            "audit_result": result.audit_result,
            "gap_count": len(result.gaps),
            "gaps": gap_data,
            "summary": result.summary,
            "duration_ms": result.duration_ms,
        }))
        sys.exit(0)

    elif args.audit_cmd == "prompt":
        state = load_state(args.state)
        state_dict = state.to_dict()
        prompt_data = build_audit_prompt(
            state_dict,
            cycle=args.cycle,
            input_mode=args.input_mode,
            input_path=args.input_path,
        )
        print(json.dumps(prompt_data, indent=2))
        sys.exit(0)

    elif args.audit_cmd == "parse":
        from .auditor import parse_audit_result
        from pathlib import Path
        raw = Path(args.raw_file).read_text(encoding="utf-8")
        result = parse_audit_result(raw)
        gap_data = [
            {"description": g.description, "severity": g.severity,
             "spec_reference": g.spec_reference, "suggested_scope": g.suggested_scope}
            for g in result.gaps
        ]
        print(json.dumps({
            "audit_result": result.audit_result,
            "gaps": gap_data,
            "summary": result.summary,
        }))
        sys.exit(0)


def cmd_build(args):
    """Dispatch build subcommands."""
    if args.build_cmd == "check":
        from .builder import check_base_build
        result = check_base_build(args.project)
        print(json.dumps({
            "status": result.status,
            "package_manager": result.package_manager,
        }))
        sys.exit(0 if result.status != "fail" else 1)

    elif args.build_cmd == "fix":
        from .builder import fix_base_build
        result = fix_base_build(args.project)
        print(json.dumps({"status": result.status}))
        sys.exit(0 if result.status == "pass" else 1)

    elif args.build_cmd == "detect-server":
        from .config import detect_dev_server
        cmd = detect_dev_server(args.project)
        print(json.dumps({"command": cmd or ""}))
        sys.exit(0)

    elif args.build_cmd == "detect-pm":
        from .config import detect_package_manager
        pm = detect_package_manager(args.project)
        print(json.dumps({"package_manager": pm}))
        sys.exit(0)


def main():
    import logging

    # Determine log file: prefer project-local, fall back to stderr
    _log_file = None
    for _arg_i, _arg in enumerate(sys.argv):
        if _arg == "--state" and _arg_i + 1 < len(sys.argv):
            _state_dir = os.path.dirname(sys.argv[_arg_i + 1])
            _log_file = os.path.join(_state_dir, "set", "orchestration", "python.log")
            os.makedirs(os.path.dirname(_log_file), exist_ok=True)
            break

    _handlers: list[logging.Handler] = []
    if _log_file:
        _handlers.append(logging.FileHandler(_log_file, encoding="utf-8"))
    _handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=_handlers,
    )

    parser = argparse.ArgumentParser(
        prog="set-orch-core",
        description="Python core for set-core orchestration engine",
    )
    # Top-level model-profile flag — applies the named preset by setting
    # SET_ORCH_MODEL_<ROLE> env vars before dispatch. Per-role flags on
    # subcommands override on top of the preset.
    parser.add_argument(
        "--model-profile",
        choices=["default", "all-opus-4-6", "all-opus-4-7", "cost-optimized"],
        default=None,
        help=(
            "Apply a model preset to all roles. Per-role flags override. "
            "Presets: default | all-opus-4-6 | all-opus-4-7 | cost-optimized."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- process ---
    proc_parser = subparsers.add_parser("process", help="Process lifecycle management")
    proc_sub = proc_parser.add_subparsers(dest="process_cmd", required=True)

    p_check = proc_sub.add_parser("check-pid", help="Check PID with identity verification")
    p_check.add_argument("--pid", type=int, required=True)
    p_check.add_argument("--expect-cmd", required=True, help="Expected cmdline pattern")

    p_kill = proc_sub.add_parser("safe-kill", help="Terminate with identity verification")
    p_kill.add_argument("--pid", type=int, required=True)
    p_kill.add_argument("--expect-cmd", required=True, help="Expected cmdline pattern")
    p_kill.add_argument("--timeout", type=int, default=10, help="Seconds to wait after SIGTERM")

    p_orphans = proc_sub.add_parser("find-orphans", help="Find orphaned processes")
    p_orphans.add_argument("--expect-cmd", required=True, help="Expected cmdline pattern")
    p_orphans.add_argument("--known-pids", default="", help="Comma-separated known PIDs")

    # --- state ---
    state_parser = subparsers.add_parser("state", help="Typed JSON state management")
    state_sub = state_parser.add_subparsers(dest="state_cmd", required=True)

    s_init = state_sub.add_parser("init", help="Initialize state from plan file")
    s_init.add_argument("--plan-file", required=True, help="Path to plan.json")
    s_init.add_argument("--output", required=True, help="Output state file path")
    s_init.add_argument(
        "--spec",
        default=None,
        help="Path to the spec the sentinel was started with. Becomes "
             "spec_lineage_id; falls back to plan.input_path when omitted.",
    )
    s_init.add_argument(
        "--project",
        default=None,
        help="Project root directory. Used to canonicalise --spec into a "
             "project-relative POSIX path. Defaults to the plan file's dir.",
    )
    s_init.add_argument(
        "--session-id",
        default=None,
        help="Pre-existing sentinel session id (e.g., for replan reuse). "
             "Omit to mint a fresh uuid.",
    )

    s_query = state_sub.add_parser("query", help="Query changes by status")
    s_query.add_argument("--file", required=True, help="State file path")
    s_query.add_argument("--status", default=None, help="Filter by status")

    s_get = state_sub.add_parser("get", help="Get a field from a specific change")
    s_get.add_argument("--file", required=True, help="State file path")
    s_get.add_argument("--change", required=True, help="Change name")
    s_get.add_argument("--field", required=True, help="Field name to retrieve")

    s_uf = state_sub.add_parser("update-field", help="Update a top-level state field")
    s_uf.add_argument("--file", required=True, help="State file path")
    s_uf.add_argument("--field", required=True, help="Field name")
    s_uf.add_argument("--value", required=True, help="JSON value")

    s_uc = state_sub.add_parser("update-change", help="Update a change field")
    s_uc.add_argument("--file", required=True, help="State file path")
    s_uc.add_argument("--name", required=True, help="Change name")
    s_uc.add_argument("--field", required=True, help="Field name")
    s_uc.add_argument("--value", required=True, help="JSON value")

    s_gs = state_sub.add_parser("get-status", help="Get a change's status")
    s_gs.add_argument("--file", required=True, help="State file path")
    s_gs.add_argument("--name", required=True, help="Change name")

    s_cbs = state_sub.add_parser("count-by-status", help="Count changes by status")
    s_cbs.add_argument("--file", required=True, help="State file path")
    s_cbs.add_argument("--status", required=True, help="Status to count")

    s_chbs = state_sub.add_parser("changes-by-status", help="List change names by status")
    s_chbs.add_argument("--file", required=True, help="State file path")
    s_chbs.add_argument("--status", required=True, help="Status to filter")

    s_ds = state_sub.add_parser("deps-satisfied", help="Check if change deps are satisfied")
    s_ds.add_argument("--file", required=True, help="State file path")
    s_ds.add_argument("--name", required=True, help="Change name")

    s_cf = state_sub.add_parser("cascade-failed", help="Cascade failed dependencies")
    s_cf.add_argument("--file", required=True, help="State file path")

    s_ts = state_sub.add_parser("topo-sort", help="Topological sort of plan changes")
    s_ts.add_argument("--plan-file", required=True, help="Plan file path")

    s_ap = state_sub.add_parser("advance-phase", help="Advance to next phase")
    s_ap.add_argument("--file", required=True, help="State file path")

    s_rc = state_sub.add_parser("reconstruct", help="Reconstruct state from events")
    s_rc.add_argument("--file", required=True, help="State file path")
    s_rc.add_argument("--events", default=None, help="Events JSONL file path")

    # --- template ---
    tmpl_parser = subparsers.add_parser("template", help="Safe structured text generation")
    tmpl_sub = tmpl_parser.add_subparsers(dest="template_cmd", required=True)

    t_proposal = tmpl_sub.add_parser("proposal", help="Render proposal.md")
    t_proposal.add_argument("--change", default="", help="Change name")
    t_proposal.add_argument("--scope", default="", help="Change scope")
    t_proposal.add_argument("--roadmap", default="", help="Roadmap item")
    t_proposal.add_argument("--input-file", default=None, help="JSON input (- for stdin)")

    t_review = tmpl_sub.add_parser("review", help="Render review prompt")
    t_review.add_argument("--input-file", default=None, help="JSON input (- for stdin)")

    t_fix = tmpl_sub.add_parser("fix", help="Render fix prompt")
    t_fix.add_argument("--input-file", default=None, help="JSON input (- for stdin)")

    t_planning = tmpl_sub.add_parser("planning", help="Render planning prompt")
    t_planning.add_argument("--mode", default="spec", choices=["spec", "brief"])
    t_planning.add_argument("--input-file", default=None, help="JSON input (- for stdin)")

    t_audit = tmpl_sub.add_parser("audit", help="Render post-phase audit prompt")
    t_audit.add_argument("--input-file", default=None, help="JSON input (- for stdin)")

    # --- config ---
    cfg_parser = subparsers.add_parser("config", help="Configuration and directive utilities")
    cfg_sub = cfg_parser.add_subparsers(dest="config_cmd", required=True)

    c_parse = cfg_sub.add_parser("parse-directives", help="Parse directives from document")
    c_parse.add_argument("--file", required=True, help="Document path (brief or spec)")

    c_resolve = cfg_sub.add_parser("resolve-directives", help="Resolve directives with full precedence")
    c_resolve.add_argument("--file", required=True, help="Input document path")
    c_resolve.add_argument("--config", default=None, help="Config file path (orchestration.yaml)")
    c_resolve.add_argument("--override", action="append", help="CLI override key=value (repeatable)")

    c_load = cfg_sub.add_parser("load-config", help="Load config file (YAML)")
    c_load.add_argument("--file", required=True, help="Config file path")

    c_pdur = cfg_sub.add_parser("parse-duration", help="Parse duration string to seconds")
    c_pdur.add_argument("value", help="Duration string (e.g., '1h30m', '30')")

    c_fdur = cfg_sub.add_parser("format-duration", help="Format seconds to duration string")
    c_fdur.add_argument("value", help="Seconds")

    c_hash = cfg_sub.add_parser("brief-hash", help="SHA-256 hash of a file")
    c_hash.add_argument("--file", required=True, help="File to hash")

    c_next = cfg_sub.add_parser("parse-next-items", help="Extract ### Next items from brief")
    c_next.add_argument("--file", required=True, help="Brief file path")

    c_find = cfg_sub.add_parser("find-input", help="Resolve orchestration input source")
    c_find.add_argument("--spec", default=None, help="Spec override path")
    c_find.add_argument("--brief", default=None, help="Brief override path")

    # --- plan ---
    plan_parser = subparsers.add_parser("plan", help="Planner operations")
    plan_sub = plan_parser.add_subparsers(dest="plan_cmd", required=True)

    pl_validate = plan_sub.add_parser("validate", help="Validate plan JSON")
    pl_validate.add_argument("--plan-file", required=True, help="Plan file path")
    pl_validate.add_argument("--digest-dir", default=None, help="Digest directory for coverage check")

    pl_testinfra = plan_sub.add_parser("detect-test-infra", help="Detect test infrastructure")
    pl_testinfra.add_argument("--project-dir", default=None, help="Project directory (default: cwd)")

    pl_triage = plan_sub.add_parser("check-triage", help="Check triage gate status")
    pl_triage.add_argument("--digest-dir", required=True, help="Digest directory")
    pl_triage.add_argument("--auto-defer", action="store_true", help="Auto-defer all ambiguities")

    pl_overlap = plan_sub.add_parser("check-scope-overlap", help="Check scope overlap")
    pl_overlap.add_argument("--plan-file", required=True, help="Plan file path")
    pl_overlap.add_argument("--state-file", default=None, help="State file for active change check")
    pl_overlap.add_argument("--pk-file", default=None, help="project-knowledge.yaml path")

    pl_context = plan_sub.add_parser("build-context", help="Build decomposition context and render prompt")
    pl_context.add_argument("--input-file", default=None, help="JSON input (- for stdin)")

    pl_enrich = plan_sub.add_parser("enrich-metadata", help="Enrich plan with metadata")
    pl_enrich.add_argument("--plan-file", required=True, help="Plan file path (read+write)")
    pl_enrich.add_argument("--hash", required=True, help="Input content hash")
    pl_enrich.add_argument("--input-mode", required=True, help="Input mode (brief/spec/digest)")
    pl_enrich.add_argument("--input-path", required=True, help="Input file path")
    pl_enrich.add_argument("--replan-cycle", type=int, default=None, help="Replan cycle number")
    pl_enrich.add_argument("--state-file", default=None, help="State file for replan stripping")
    pl_enrich.add_argument("--plan-version", type=int, default=None, help="Override plan version")

    pl_summarize = plan_sub.add_parser("summarize-spec", help="Summarize a large spec")
    pl_summarize.add_argument("--spec-file", required=True, help="Spec file path")
    pl_summarize.add_argument("--phase-hint", default=None, help="Phase to focus on")
    pl_summarize.add_argument("--model", default=None, help="Model for summarization")

    pl_replan = plan_sub.add_parser("replan-context", help="Collect replan context")
    pl_replan.add_argument("--state-file", required=True, help="State file path")

    pl_run = plan_sub.add_parser("run", help="Run full planning pipeline")
    pl_run.add_argument("--input-mode", required=True, help="Input mode (spec/brief/digest)")
    pl_run.add_argument("--input-path", required=True, help="Input file/dir path")
    pl_run.add_argument("--output", default=None, help="Output plan file (default: resolver)")
    pl_run.add_argument("--state-file", default="", help="State file (for replan)")
    pl_run.add_argument("--model", default=None, help="Model for decomposition (default: resolve_model('decompose_brief'))")
    pl_run.add_argument("--method", default="api", help="Planning method (api/agent)")
    pl_run.add_argument("--team", action="store_true", help="Team mode")
    pl_run.add_argument("--phase-hint", default="", help="Phase to focus on")
    pl_run.add_argument("--replan-cycle", type=int, default=None, help="Replan cycle number")

    # --- report ---
    rpt_parser = subparsers.add_parser("report", help="HTML report generation")
    rpt_sub = rpt_parser.add_subparsers(dest="report_cmd", required=True)

    r_gen = rpt_sub.add_parser("generate", help="Generate HTML report from orchestration data")
    r_gen.add_argument("--state", default=None, help="State JSON file path")
    r_gen.add_argument("--plan", default=None, help="Plan JSON file path")
    r_gen.add_argument("--digest-dir", default=None, help="Digest directory path")
    r_gen.add_argument("--output", default="set/orchestration/report.html", help="Output HTML path")

    # --- events ---
    evt_parser = subparsers.add_parser("events", help="Query orchestration events log")
    evt_parser.add_argument("--log", default=None, help="Events JSONL file path")
    evt_parser.add_argument("--type", default=None, help="Filter by event type")
    evt_parser.add_argument("--change", default=None, help="Filter by change name")
    evt_parser.add_argument("--since", default=None, help="Filter by timestamp (ISO 8601)")
    evt_parser.add_argument("--last", type=int, default=None, help="Only last N events")
    evt_parser.add_argument("--json", action="store_true", help="Output as JSON array")

    # --- dispatch ---
    disp_parser = subparsers.add_parser("dispatch", help="Dispatcher operations")
    disp_sub = disp_parser.add_subparsers(dest="dispatch_cmd", required=True)

    d_sync = disp_sub.add_parser("sync-worktree", help="Sync worktree with main branch")
    d_sync.add_argument("--wt-path", required=True, help="Worktree path")
    d_sync.add_argument("--change", required=True, help="Change name")

    d_boot = disp_sub.add_parser("bootstrap", help="Bootstrap worktree environment")
    d_boot.add_argument("--project-path", required=True, help="Project root path")
    d_boot.add_argument("--wt-path", required=True, help="Worktree path")

    d_prune = disp_sub.add_parser("prune-context", help="Prune orchestrator context from worktree")
    d_prune.add_argument("--wt-path", required=True, help="Worktree path")

    d_model = disp_sub.add_parser("resolve-model", help="Resolve implementation model")
    d_model.add_argument("--state", required=True, help="State file path")
    d_model.add_argument("--change", required=True, help="Change name")
    d_model.add_argument("--default-model", default=None, help="Default agent model (default: resolve_model('agent'))")
    d_model.add_argument("--model-routing", default="off", help="Routing mode")

    d_disp = disp_sub.add_parser("dispatch-change", help="Dispatch a single change")
    d_disp.add_argument("--state", required=True, help="State file path")
    d_disp.add_argument("--change", required=True, help="Change name")
    d_disp.add_argument("--default-model", default=None, help="Default agent model (default: resolve_model('agent'))")
    d_disp.add_argument("--model-routing", default="off", help="Routing mode")
    d_disp.add_argument("--team", action="store_true", help="Enable team mode")
    d_disp.add_argument("--no-prune", action="store_true", help="Skip context pruning")
    d_disp.add_argument("--input-mode", default="", help="Input mode (spec/brief/digest)")
    d_disp.add_argument("--input-path", default="", help="Input file path")
    d_disp.add_argument("--digest-dir", default="", help="Digest directory")

    d_ready = disp_sub.add_parser("dispatch-ready", help="Dispatch all ready changes")
    d_ready.add_argument("--state", required=True, help="State file path")
    d_ready.add_argument("--max-parallel", type=int, required=True, help="Max parallel changes")
    d_ready.add_argument("--default-model", default=None, help="Default agent model (default: resolve_model('agent'))")
    d_ready.add_argument("--model-routing", default="off", help="Routing mode")
    d_ready.add_argument("--team", action="store_true", help="Enable team mode")
    d_ready.add_argument("--no-prune", action="store_true", help="Skip context pruning")
    d_ready.add_argument("--input-mode", default="", help="Input mode")
    d_ready.add_argument("--input-path", default="", help="Input file path")
    d_ready.add_argument("--digest-dir", default="", help="Digest directory")

    d_pause = disp_sub.add_parser("pause", help="Pause a running change")
    d_pause.add_argument("--state", required=True, help="State file path")
    d_pause.add_argument("--change", required=True, help="Change name")

    d_resume = disp_sub.add_parser("resume", help="Resume a paused/stopped change")
    d_resume.add_argument("--state", required=True, help="State file path")
    d_resume.add_argument("--change", required=True, help="Change name")
    d_resume.add_argument("--default-model", default=None, help="Default agent model (default: resolve_model('agent'))")
    d_resume.add_argument("--model-routing", default="off", help="Routing mode")
    d_resume.add_argument("--team", action="store_true", help="Enable team mode")

    d_rstopped = disp_sub.add_parser("resume-stopped", help="Resume all stopped changes")
    d_rstopped.add_argument("--state", required=True, help="State file path")

    d_rstalled = disp_sub.add_parser("resume-stalled", help="Resume stalled changes after cooldown")
    d_rstalled.add_argument("--state", required=True, help="State file path")

    d_recover = disp_sub.add_parser("recover-orphans", help="Recover orphaned changes")
    d_recover.add_argument("--state", required=True, help="State file path")

    d_redisp = disp_sub.add_parser("redispatch", help="Redispatch a stuck change")
    d_redisp.add_argument("--state", required=True, help="State file path")
    d_redisp.add_argument("--change", required=True, help="Change name")
    d_redisp.add_argument("--failure-pattern", default="stuck", help="Failure pattern")
    d_redisp.add_argument("--max-redispatch", type=int, default=2, help="Max redispatch attempts")

    d_retry = disp_sub.add_parser("retry-builds", help="Retry failed builds")
    d_retry.add_argument("--state", required=True, help="State file path")
    d_retry.add_argument("--max-retries", type=int, default=2, help="Max retry attempts")

    # --- verify ---
    ver_parser = subparsers.add_parser("verify", help="Verifier operations")
    ver_sub = ver_parser.add_subparsers(dest="verify_cmd", required=True)

    v_tests = ver_sub.add_parser("run-tests", help="Run tests in worktree")
    v_tests.add_argument("--wt-path", required=True, help="Worktree path")
    v_tests.add_argument("--command", required=True, help="Test command")
    v_tests.add_argument("--timeout", type=int, default=120, help="Timeout in seconds")
    v_tests.add_argument("--max-chars", type=int, default=2000, help="Max output chars")

    v_review = ver_sub.add_parser("review", help="LLM code review")
    v_review.add_argument("--change", required=True, help="Change name")
    v_review.add_argument("--wt-path", required=True, help="Worktree path")
    v_review.add_argument("--scope", required=True, help="Change scope")
    v_review.add_argument("--model", default=None, help="Review model (default: resolve_model('review'))")
    v_review.add_argument("--state", default="", help="State file path")

    v_rules = ver_sub.add_parser("evaluate-rules", help="Evaluate verification rules")
    v_rules.add_argument("--change", required=True, help="Change name")
    v_rules.add_argument("--wt-path", required=True, help="Worktree path")
    v_rules.add_argument("--pk-file", default="", help="project-knowledge.yaml path")
    v_rules.add_argument("--state", default="", help="State file for events")

    v_mscope = ver_sub.add_parser("check-merge-scope", help="Post-merge scope check")
    v_mscope.add_argument("--change", required=True, help="Change name")

    v_iscope = ver_sub.add_parser("check-impl-scope", help="Pre-merge implementation scope check")
    v_iscope.add_argument("--change", required=True, help="Change name")
    v_iscope.add_argument("--wt-path", required=True, help="Worktree path")

    v_health = ver_sub.add_parser("health-check", help="HTTP health check")
    v_health.add_argument("--url", required=True, help="URL to check")
    v_health.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")

    v_hurl = ver_sub.add_parser("extract-health-url", help="Extract health URL from smoke command")
    v_hurl.add_argument("--smoke-cmd", required=True, help="Smoke command string")

    v_reqsec = ver_sub.add_parser("build-req-section", help="Build requirement review section")
    v_reqsec.add_argument("--change", required=True, help="Change name")
    v_reqsec.add_argument("--state", required=True, help="State file path")

    v_poll = ver_sub.add_parser("poll", help="Poll a change's loop-state")
    v_poll.add_argument("--change", required=True, help="Change name")
    v_poll.add_argument("--state", required=True, help="State file path")
    v_poll.add_argument("--test-command", default="", help="Test command")
    v_poll.add_argument("--merge-policy", default="eager", help="Merge policy")
    v_poll.add_argument("--test-timeout", type=int, default=120, help="Test timeout")
    v_poll.add_argument("--max-verify-retries", type=int, default=2, help="Max verify retries")
    v_poll.add_argument("--review-before-merge", action="store_true", help="Enable code review")
    v_poll.add_argument("--review-model", default=None, help="Review model (default: resolve_model('review'))")
    v_poll.add_argument("--smoke-command", default="", help="Smoke test command")
    v_poll.add_argument("--smoke-timeout", type=int, default=180, help="Smoke timeout")
    v_poll.add_argument("--e2e-command", default="", help="E2E test command")
    v_poll.add_argument("--e2e-timeout", type=int, default=120, help="E2E timeout")

    v_done = ver_sub.add_parser("handle-done", help="Handle change done (verify gate)")
    v_done.add_argument("--change", required=True, help="Change name")
    v_done.add_argument("--state", required=True, help="State file path")
    v_done.add_argument("--test-command", default="", help="Test command")
    v_done.add_argument("--merge-policy", default="eager", help="Merge policy")
    v_done.add_argument("--test-timeout", type=int, default=120, help="Test timeout")
    v_done.add_argument("--max-verify-retries", type=int, default=2, help="Max verify retries")
    v_done.add_argument("--review-before-merge", action="store_true", help="Enable code review")
    v_done.add_argument("--review-model", default=None, help="Review model (default: resolve_model('review'))")
    v_done.add_argument("--smoke-command", default="", help="Smoke test command")
    v_done.add_argument("--smoke-timeout", type=int, default=180, help="Smoke timeout")
    v_done.add_argument("--e2e-command", default="", help="E2E test command")
    v_done.add_argument("--e2e-timeout", type=int, default=120, help="E2E timeout")

    v_sfix = ver_sub.add_parser("smoke-fix", help="Scoped smoke fix agent")
    v_sfix.add_argument("--change", required=True, help="Change name")
    v_sfix.add_argument("--smoke-cmd", required=True, help="Smoke command")
    v_sfix.add_argument("--smoke-timeout", type=int, required=True, help="Smoke timeout")
    v_sfix.add_argument("--smoke-output", default="", help="Initial smoke output")
    v_sfix.add_argument("--state", required=True, help="State file path")
    v_sfix.add_argument("--max-retries", type=int, default=3, help="Max fix retries")
    v_sfix.add_argument("--max-turns", type=int, default=15, help="Max Claude turns per fix")

    v_pe2e = ver_sub.add_parser("phase-e2e", help="Phase-end E2E tests")
    v_pe2e.add_argument("--command", required=True, help="E2E command")
    v_pe2e.add_argument("--state", required=True, help="State file path")
    v_pe2e.add_argument("--timeout", type=int, default=180, help="E2E timeout")

    # --- serve ---
    serve_parser = subparsers.add_parser("serve", help="Start the web dashboard server")
    serve_parser.add_argument("--port", type=int, default=None, help="Port (default: 7400, env: WT_WEB_PORT)")
    serve_parser.add_argument("--host", default=None, help="Host (default: 0.0.0.0, use 127.0.0.1 to restrict to localhost)")

    # --- merge ---
    merge_parser = subparsers.add_parser("merge", help="Merger operations")
    merge_sub = merge_parser.add_subparsers(dest="merge_cmd", required=True)

    m_merge = merge_sub.add_parser("merge-change", help="Merge a completed change")
    m_merge.add_argument("--change", required=True, help="Change name")
    m_merge.add_argument("--state", required=True, help="State file path")

    m_exec = merge_sub.add_parser("execute-queue", help="Drain merge queue")
    m_exec.add_argument("--state", required=True, help="State file path")

    m_retry = merge_sub.add_parser("retry-queue", help="Retry merge queue + merge-blocked")
    m_retry.add_argument("--state", required=True, help="State file path")

    m_archive = merge_sub.add_parser("archive", help="Archive a change to dated directory")
    m_archive.add_argument("--change", required=True, help="Change name")

    m_cwt = merge_sub.add_parser("cleanup-worktree", help="Clean up a single worktree")
    m_cwt.add_argument("--change", required=True, help="Change name")
    m_cwt.add_argument("--wt-path", required=True, help="Worktree path")

    m_call = merge_sub.add_parser("cleanup-all", help="Clean up all merged/done worktrees")
    m_call.add_argument("--state", required=True, help="State file path")

    # --- milestone ---
    ms_parser = subparsers.add_parser("milestone", help="Milestone operations")
    ms_sub = ms_parser.add_subparsers(dest="milestone_cmd", required=True)

    ms_ckpt = ms_sub.add_parser("checkpoint", help="Run milestone checkpoint for a phase")
    ms_ckpt.add_argument("--phase", type=int, required=True, help="Phase number")
    ms_ckpt.add_argument("--state", required=True, help="State file path")
    ms_ckpt.add_argument("--base-port", type=int, default=3100, help="Base port for dev servers")
    ms_ckpt.add_argument("--max-worktrees", type=int, default=3, help="Max milestone worktrees")
    ms_ckpt.add_argument("--dev-server", default="", help="Dev server command override")

    ms_cs = ms_sub.add_parser("cleanup-servers", help="Kill all milestone dev servers")
    ms_cs.add_argument("--state", required=True, help="State file path")

    ms_cw = ms_sub.add_parser("cleanup-worktrees", help="Remove all milestone worktrees")

    # --- digest ---
    dig_parser = subparsers.add_parser("digest", help="Spec digest operations")
    dig_sub = dig_parser.add_subparsers(dest="digest_cmd", required=True)

    dig_run = dig_sub.add_parser("run", help="Run full digest pipeline")
    dig_run.add_argument("--spec", required=True, help="Spec directory or file path")
    dig_run.add_argument("--dry-run", action="store_true", help="Print without writing")
    dig_run.add_argument("--model", default=None, help="Model for digest (default: resolve_model('digest'))")
    dig_run.add_argument("--dir", default=None, help="Digest directory (default: resolver)")
    dig_run.add_argument(
        "--no-digest-cache",
        action="store_true",
        help="skip both cache lookup and cache write for this invocation",
    )
    dig_run.add_argument(
        "--digest-cache-clear",
        action="store_true",
        help="purge the digest cache before running",
    )

    dig_val = dig_sub.add_parser("validate", help="Validate existing digest")
    dig_val.add_argument("--dir", default=None, help="Digest directory (default: resolver)")

    dig_cov = dig_sub.add_parser("coverage", help="Show coverage report")
    dig_cov.add_argument("--dir", default=None, help="Digest directory (default: resolver)")

    dig_fresh = dig_sub.add_parser("freshness", help="Check digest freshness")
    dig_fresh.add_argument("--spec", required=True, help="Spec directory or file path")
    dig_fresh.add_argument("--dir", default=None, help="Digest directory (default: resolver)")

    dig_scan = dig_sub.add_parser("scan", help="Scan spec directory")
    dig_scan.add_argument("--spec", required=True, help="Spec directory or file path")

    dig_bp = dig_sub.add_parser("build-prompt", help="Build digest prompt from spec")
    dig_bp.add_argument("--spec", required=True, help="Spec directory or file path")

    dig_pcov = dig_sub.add_parser("populate-coverage", help="Map requirements to plan changes")
    dig_pcov.add_argument("--plan-file", required=True, help="Plan file path")
    dig_pcov.add_argument("--dir", default=None, help="Digest directory (default: resolver)")

    dig_ucov = dig_sub.add_parser("update-coverage", help="Update coverage status for a change")
    dig_ucov.add_argument("--change", required=True, help="Change name")
    dig_ucov.add_argument("--status", required=True, help="New status")
    dig_ucov.add_argument("--dir", default=None, help="Digest directory (default: resolver)")

    dig_fcov = dig_sub.add_parser("final-coverage", help="Final coverage check summary")
    dig_fcov.add_argument("--dir", default=None, help="Digest directory (default: resolver)")

    dig_gtriage = dig_sub.add_parser("generate-triage", help="Generate triage.md from ambiguities")
    dig_gtriage.add_argument("--amb-file", required=True, help="Ambiguities JSON file")
    dig_gtriage.add_argument("--output", required=True, help="Output triage.md path")
    dig_gtriage.add_argument("--existing-triage", default="", help="Existing triage.md to preserve decisions")

    dig_ptriage = dig_sub.add_parser("parse-triage", help="Parse triage.md decisions")
    dig_ptriage.add_argument("--triage-file", required=True, help="Triage.md file path")

    dig_mtriage = dig_sub.add_parser("merge-triage", help="Merge triage decisions into ambiguities")
    dig_mtriage.add_argument("--amb-file", required=True, help="Ambiguities JSON file")
    dig_mtriage.add_argument("--decisions", required=True, help="Triage decisions JSON string")
    dig_mtriage.add_argument("--resolved-by", default="triage", help="Resolution source")

    dig_mplan = dig_sub.add_parser("merge-planner-resolutions", help="Merge planner resolutions into ambiguities")
    dig_mplan.add_argument("--amb-file", required=True, help="Ambiguities JSON file")
    dig_mplan.add_argument("--plan-file", required=True, help="Plan file path")

    dig_sub.add_parser("parse-response", help="Parse raw digest LLM response (stdin)")
    dig_sub.add_parser("validate-raw", help="Validate raw digest JSON (stdin)")
    dig_sub.add_parser("stabilize-ids", help="Stabilize requirement IDs (stdin)")

    dig_wo = dig_sub.add_parser("write-output", help="Write digest output files (stdin JSON)")
    dig_wo.add_argument("--spec", required=True, help="Spec directory or file path")

    # --- watchdog ---
    wd_parser = subparsers.add_parser("watchdog", help="Watchdog operations")
    wd_sub = wd_parser.add_subparsers(dest="watchdog_cmd", required=True)

    wd_check = wd_sub.add_parser("check", help="Run watchdog check for one change")
    wd_check.add_argument("--change", required=True, help="Change name")
    wd_check.add_argument("--state", required=True, help="State file path")

    wd_status = wd_sub.add_parser("status", help="Show watchdog state for all changes")
    wd_status.add_argument("--state", required=True, help="State file path")

    # --- audit ---
    aud_parser = subparsers.add_parser("audit", help="Post-phase audit operations")
    aud_sub = aud_parser.add_subparsers(dest="audit_cmd", required=True)

    aud_run = aud_sub.add_parser("run", help="Run post-phase audit")
    aud_run.add_argument("--cycle", type=int, default=1, help="Cycle number")
    aud_run.add_argument("--state", required=True, help="State file path")
    aud_run.add_argument("--input-mode", default="spec", help="Input mode (spec/digest)")
    aud_run.add_argument("--input-path", default="", help="Input file path")
    aud_run.add_argument("--model", default=None, help="Review model (default: resolve_model('review'))")

    aud_prompt = aud_sub.add_parser("prompt", help="Print audit prompt without executing")
    aud_prompt.add_argument("--cycle", type=int, default=1, help="Cycle number")
    aud_prompt.add_argument("--state", required=True, help="State file path")
    aud_prompt.add_argument("--input-mode", default="spec", help="Input mode")
    aud_prompt.add_argument("--input-path", default="", help="Input file path")

    aud_parse = aud_sub.add_parser("parse", help="Parse raw audit result file")
    aud_parse.add_argument("--raw-file", required=True, help="Path to raw audit output")

    # --- build ---
    bld_parser = subparsers.add_parser("build", help="Build health operations")
    bld_sub = bld_parser.add_subparsers(dest="build_cmd", required=True)

    bld_check = bld_sub.add_parser("check", help="Run build health check")
    bld_check.add_argument("--project", default=".", help="Project directory")

    bld_fix = bld_sub.add_parser("fix", help="Attempt LLM-assisted build fix")
    bld_fix.add_argument("--project", default=".", help="Project directory")

    bld_ds = bld_sub.add_parser("detect-server", help="Detect dev server command")
    bld_ds.add_argument("--project", default=".", help="Project directory")

    bld_pm = bld_sub.add_parser("detect-pm", help="Detect package manager")
    bld_pm.add_argument("--project", default=".", help="Project directory")

    # --- loop ---
    loop_parser = subparsers.add_parser("loop", help="Ralph loop engine utilities")
    loop_sub = loop_parser.add_subparsers(dest="loop_cmd", required=True)

    l_classify = loop_sub.add_parser("classify-error", help="Classify API error from log")
    l_classify.add_argument("--log-file", required=True, help="Log file to scan")

    l_budget = loop_sub.add_parser("check-budget", help="Check token budget status")
    l_budget.add_argument("--used", type=int, required=True, help="Tokens used")
    l_budget.add_argument("--budget", type=int, required=True, help="Token budget")

    l_done = loop_sub.add_parser("check-done", help="Check if loop is done")
    l_done.add_argument("--wt-path", required=True, help="Worktree path")
    l_done.add_argument("--done-criteria", default="tasks", help="Done criteria")

    l_action = loop_sub.add_parser("detect-action", help="Detect next OpenSpec change action")
    l_action.add_argument("--wt-path", required=True, help="Worktree path")
    l_action.add_argument("--change", default="", help="Targeted change name")

    l_prompt = loop_sub.add_parser("build-prompt", help="Build Claude prompt arguments")
    l_prompt.add_argument("--wt-path", required=True, help="Worktree path")
    l_prompt.add_argument("--task", required=True, help="Task description")
    l_prompt.add_argument("--done-criteria", default="tasks", help="Done criteria")
    l_prompt.add_argument("--change", default="", help="Change name")
    l_prompt.add_argument("--previous-commits", default="", help="Previous commits summary")
    l_prompt.add_argument("--manual-tasks", default="", help="Manual task text")
    l_prompt.add_argument("--team", action="store_true", help="Enable team mode")

    l_tasks = loop_sub.add_parser("task-status", help="Check tasks.md completion status")
    l_tasks.add_argument("--wt-path", required=True, help="Worktree path")

    # --- engine ---
    eng_parser = subparsers.add_parser("engine", help="Orchestration engine")
    eng_sub = eng_parser.add_subparsers(dest="engine_cmd", required=True)

    e_mon = eng_sub.add_parser("monitor", help="Run main orchestration monitoring loop")
    e_mon.add_argument("--directives", required=True, help="Directives JSON file or string")
    e_mon.add_argument("--state", required=True, help="State file path")
    e_mon.add_argument("--poll-interval", type=int, default=15, help="Poll interval in seconds")
    e_mon.add_argument("--default-model", default="", help="Default model override")
    e_mon.add_argument("--team-mode", action="store_true", help="Enable team mode")
    e_mon.add_argument("--context-pruning", action="store_true", default=True, help="Enable context pruning")
    e_mon.add_argument("--model-routing", default="off", help="Model routing mode")
    e_mon.add_argument("--checkpoint-auto-approve", action="store_true", help="Auto-approve checkpoints")
    e_mon.add_argument("--checkpoint-timeout", type=int, default=0, help="Auto-resume checkpoint after N seconds (0=disabled)")

    # --- issues ---
    iss_parser = subparsers.add_parser("issues", help="Issue registry / fix-iss lifecycle operations")
    iss_sub = iss_parser.add_subparsers(dest="issues_cmd", required=True)

    iss_cleanup = iss_sub.add_parser(
        "cleanup-orphans",
        help="Scan + remove orphan fix-iss children (parent merged, but child still pending)",
    )
    iss_cleanup.add_argument("--project", required=True, help="Project root path")
    iss_cleanup.add_argument("--dry-run", action="store_true", help="List orphans without modifying")
    iss_cleanup.add_argument("--yes", action="store_true", help="Skip interactive confirmation")

    args = parser.parse_args()

    # Apply --model-profile preset (sets SET_ORCH_MODEL_<ROLE> env vars
    # so the resolver sees them). Per-role flags inside subcommands
    # override on top via cli_override.
    if getattr(args, "model_profile", None):
        from .model_config import PRESETS, _env_var_name
        preset = PRESETS.get(args.model_profile)
        if preset:
            def _flatten(d, prefix=""):
                for k, v in d.items():
                    full = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                    if isinstance(v, dict):
                        yield from _flatten(v, full)
                    else:
                        yield full, v
            for role, model in _flatten(preset):
                env_key = _env_var_name(role)
                # Don't override if the user already set the env var explicitly
                if env_key not in os.environ:
                    os.environ[env_key] = model
            logger.info("Applied --model-profile=%s", args.model_profile)

    if args.command == "process":
        cmd_process(args)
    elif args.command == "state":
        cmd_state(args)
    elif args.command == "template":
        cmd_template(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "events":
        cmd_events(args)
    elif args.command == "dispatch":
        cmd_dispatch(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "merge":
        cmd_merge(args)
    elif args.command == "milestone":
        cmd_milestone(args)
    elif args.command == "loop":
        cmd_loop(args)
    elif args.command == "engine":
        cmd_engine(args)
    elif args.command == "digest":
        cmd_digest(args)
    elif args.command == "watchdog":
        cmd_watchdog(args)
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "issues":
        cmd_issues(args)


def cmd_issues(args):
    """Dispatch issue-registry CLI subcommands."""
    if args.issues_cmd == "cleanup-orphans":
        _cmd_issues_cleanup_orphans(args)


def _cmd_issues_cleanup_orphans(args):
    """Scan for orphan fix-iss children and optionally purge them."""
    import os
    from pathlib import Path
    from set_orch.issues.manager import (
        scan_fix_iss_orphans,
        _purge_fix_iss_child,
    )
    from set_orch.issues.models import Issue, IssueState

    project_path = os.path.abspath(args.project)
    if not os.path.isdir(project_path):
        print(f"Error: project path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)

    orphans = scan_fix_iss_orphans(project_path)

    if not orphans:
        print(f"No orphan fix-iss children found in {project_path}")
        sys.exit(0)

    # Display table
    print(f"Found {len(orphans)} orphan fix-iss child(ren) in {project_path}:")
    print()
    print(f"{'CHILD NAME':<40} {'PARENT':<30} {'PARENT STATUS':<12} "
          f"{'ISSUE':<12} {'STATE':<6} {'DIR':<6} REASON")
    print("-" * 120)
    for o in orphans:
        print(
            f"{o['child_name']:<40} {o['parent_name']:<30} "
            f"{o['parent_status']:<12} {o['issue_state'] or '-':<12} "
            f"{'yes' if o['state_entry_present'] else 'no':<6} "
            f"{'yes' if o['dir_present'] else 'no':<6} {o['reason']}"
        )
    print()

    if args.dry_run:
        print(f"(dry-run: {len(orphans)} orphan(s) listed; no changes made)")
        sys.exit(0)

    # Confirmation gate
    if not args.yes:
        try:
            resp = input(f"Remove {len(orphans)} orphan(s)? [y/N] ").strip().lower()
        except EOFError:
            resp = ""
        if resp != "y":
            print("Aborted.")
            sys.exit(0)

    # Execute purges
    state_file = os.path.join(project_path, "orchestration-state.json")
    purged = 0
    skipped = 0
    for o in orphans:
        # Build a minimal Issue-like shim for the purge helper
        shim = Issue(
            id=(o.get("issue_id") or "CLI-cleanup"),
            environment="cli",
            environment_path=project_path,
            source="cli:cleanup-orphans",
            state=IssueState.RESOLVED,
            change_name=o["child_name"],
            affected_change=o["parent_name"],
        )
        result = _purge_fix_iss_child(
            shim, state_file, project_path, reason="cli_cleanup",
        )
        if result["state_removed"] or result["dir_removed"]:
            purged += 1
            print(f"  purged: {o['child_name']}")
        else:
            skipped += 1
            print(f"  skipped: {o['child_name']} ({result.get('skipped_reason')})")

    print()
    print(f"Done: {purged} purged, {skipped} skipped, {len(orphans)} total.")


if __name__ == "__main__":
    main()
