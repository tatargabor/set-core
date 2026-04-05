"""
set-router CLI — Claude Code account manager

Manual account management for multiple Claude Code OAuth credentials.

NOTE: This tool is for manual account management only.
Automatic rotation to circumvent rate limits violates Anthropic's Terms of Service.
"""

import argparse
import sys

from . import AccountPool


TOS_NOTE = (
    "NOTE: This tool is for manual account management only. "
    "Automatic rotation to circumvent rate limits violates "
    "Anthropic's Terms of Service."
)


def cmd_add(args):
    pool = AccountPool()
    try:
        msg = pool.add(args.name, email=args.email)
        print(msg)
        if not args.email:
            print("  Tip: use --email <addr> to tag this account (shown in `set-router list`)")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_remove(args):
    pool = AccountPool()
    try:
        msg = pool.remove(args.name)
        print(msg)
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _fetch_live_usage(pool):
    """Fetch live usage for all accounts. Returns {name: usage_dict}."""
    try:
        import sys
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent / "gui"))
        from gui.workers.usage import UsageWorker
        worker = UsageWorker()
        result = {}
        for acct in pool.accounts:
            oauth = acct.get("credentials", {}).get("claudeAiOauth", {})
            token = oauth.get("accessToken")
            if token:
                data = worker.fetch_claude_api_usage(oauth_token=token)
                if data:
                    result[acct["name"]] = data
        return result
    except Exception:
        return {}


def cmd_list(args):
    pool = AccountPool()
    accounts = pool.list_accounts()
    if not accounts:
        print("No accounts registered. Run `claude login` then `set-router add <name>`.")
        return

    usage = _fetch_live_usage(pool) if getattr(args, "live", False) else {}

    for acct in accounts:
        marker = "\u25cf" if acct["active"] else "\u25cb"
        label = "[ACTIVE]" if acct["active"] else ""
        email = f"({acct['email']})" if acct.get("email") else ""
        u = usage.get(acct["name"])
        if u:
            s_pct = u.get("session_pct", 0)
            w_pct = u.get("weekly_pct", 0)
            print(f"  {marker} {acct['name']:10s} session: {s_pct:4.0f}%  weekly: {w_pct:4.0f}%  {label} {email}")
        else:
            sub = acct.get("subscription_type") or "unknown"
            print(f"  {marker} {acct['name']:10s} plan: {sub:10s} {label} {email}")


def cmd_switch(args):
    pool = AccountPool()
    try:
        msg = pool.switch(args.name)
        print(msg)
        print(f"  Manual switch \u2014 automatic rotation is not supported.")
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    pool = AccountPool()
    info = pool.status()
    if not info:
        print("No accounts registered.")
        return

    print(f"Active: {info['name']}")
    sub = info.get("subscription_type") or "unknown"
    tier = info.get("rate_limit_tier") or "unknown"
    print(f"Plan:   {sub} ({tier})")

    expires = info.get("expires_at")
    if expires:
        from datetime import datetime, timezone
        try:
            exp_dt = datetime.fromtimestamp(expires / 1000, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            remaining = exp_dt - now
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                print(f"Token:  expires in {hours}h {mins}m")
            else:
                print(f"Token:  EXPIRED — run `claude login` then `set-router add {info['name']}`")
        except (OSError, ValueError):
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="set-router",
        description="Claude Code account manager — manage multiple CC credentials.\n\n" + TOS_NOTE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=TOS_NOTE,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Save current CC credentials as a named account")
    p_add.add_argument("name", help="Account name (e.g., 'Personal', 'Work')")
    p_add.add_argument("--email", help="Email for this account (from CC /stats, for identification)")
    p_add.set_defaults(func=cmd_add)

    p_remove = sub.add_parser("remove", help="Remove a saved account")
    p_remove.add_argument("name", help="Account name to remove")
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="List all accounts with status")
    p_list.add_argument("--live", action="store_true", help="Fetch live usage data (slower, ~2s per account)")
    p_list.set_defaults(func=cmd_list)

    p_switch = sub.add_parser("switch", help="Switch active CC account (manual)")
    p_switch.add_argument("name", help="Account name to switch to")
    p_switch.set_defaults(func=cmd_switch)

    p_status = sub.add_parser("status", help="Show active account info")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
