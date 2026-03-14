"""CLI entry point for wt-orch-core.

This module is the canonical implementation. bin/wt-orch-core delegates here.
pyproject.toml [project.scripts] also points here for pip-installed environments.
"""

import argparse
import json
import sys


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
        init_state(args.plan_file, args.output)
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


def cmd_serve(args):
    """Start the web dashboard server."""
    import os
    import signal
    import uvicorn

    from .server import create_app

    port = args.port or int(os.environ.get("WT_WEB_PORT", "7400"))
    host = args.host or "0.0.0.0"

    app = create_app()
    print(f"wt-web dashboard running at http://{host}:{port}")

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


def main():
    parser = argparse.ArgumentParser(
        prog="wt-orch-core",
        description="Python core for wt-tools orchestration engine",
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

    # --- report ---
    rpt_parser = subparsers.add_parser("report", help="HTML report generation")
    rpt_sub = rpt_parser.add_subparsers(dest="report_cmd", required=True)

    r_gen = rpt_sub.add_parser("generate", help="Generate HTML report from orchestration data")
    r_gen.add_argument("--state", default=None, help="State JSON file path")
    r_gen.add_argument("--plan", default=None, help="Plan JSON file path")
    r_gen.add_argument("--digest-dir", default=None, help="Digest directory path")
    r_gen.add_argument("--output", default="wt/orchestration/report.html", help="Output HTML path")

    # --- events ---
    evt_parser = subparsers.add_parser("events", help="Query orchestration events log")
    evt_parser.add_argument("--log", default=None, help="Events JSONL file path")
    evt_parser.add_argument("--type", default=None, help="Filter by event type")
    evt_parser.add_argument("--change", default=None, help="Filter by change name")
    evt_parser.add_argument("--since", default=None, help="Filter by timestamp (ISO 8601)")
    evt_parser.add_argument("--last", type=int, default=None, help="Only last N events")
    evt_parser.add_argument("--json", action="store_true", help="Output as JSON array")

    # --- serve ---
    serve_parser = subparsers.add_parser("serve", help="Start the web dashboard server")
    serve_parser.add_argument("--port", type=int, default=None, help="Port (default: 7400, env: WT_WEB_PORT)")
    serve_parser.add_argument("--host", default=None, help="Host (default: 0.0.0.0, use 127.0.0.1 to restrict to localhost)")

    args = parser.parse_args()

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
    elif args.command == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
