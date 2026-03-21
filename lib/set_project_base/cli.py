"""Backwards compatibility shim — delegates to original CLI functionality.

Kept for `python -m set_project_base.cli deploy-templates` compatibility.
"""

# Import the original CLI from the base package if available,
# otherwise provide a minimal stub
try:
    from set_orch.profile_deploy import deploy_templates, resolve_template, get_available_modules
except ImportError:
    pass


def main():
    """CLI entry point — kept for backwards compat."""
    import sys
    print("set-project-base CLI has been merged into set-core.", file=sys.stderr)
    print("Use 'set-project init' instead.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
