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
        msg = pool.add(args.email)
        print(msg)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_remove(args):
    pool = AccountPool()
    try:
        msg = pool.remove(args.email)
        print(msg)
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    pool = AccountPool()
    accounts = pool.list_accounts()
    if not accounts:
        print("No accounts registered. Run `claude login` then `set-router add <email>`.")
        return

    for acct in accounts:
        marker = "\u25cf" if acct["active"] else "\u25cb"
        label = "[ACTIVE]" if acct["active"] else ""
        print(f"  {marker} {acct['email']:30s} {label}")


def cmd_switch(args):
    pool = AccountPool()
    try:
        msg = pool.switch(args.email)
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

    print(f"Active: {info['email']}")
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
                print(f"Token:  EXPIRED \u2014 run `claude login` then `set-router add {info['email']}`")
        except (OSError, ValueError):
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="set-router",
        description="Claude Code account manager \u2014 manage multiple CC credentials.\n\n" + TOS_NOTE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=TOS_NOTE,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Save current CC credentials")
    p_add.add_argument("email", help="Account email (from CC /stats)")
    p_add.set_defaults(func=cmd_add)

    p_remove = sub.add_parser("remove", help="Remove a saved account")
    p_remove.add_argument("email", help="Account email to remove")
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="List all accounts")
    p_list.set_defaults(func=cmd_list)

    p_switch = sub.add_parser("switch", help="Switch active CC account (manual)")
    p_switch.add_argument("email", help="Account email to switch to")
    p_switch.set_defaults(func=cmd_switch)

    p_status = sub.add_parser("status", help="Show active account info")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
