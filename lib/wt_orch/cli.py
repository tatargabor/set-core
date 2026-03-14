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
    from .state import init_state, load_state, query_changes

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
    elif args.command == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
