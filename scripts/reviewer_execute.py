"""CLI entry point for reviewer handoff preparation; it never launches Claude."""
from reviewer.execution.controller import main


if __name__ == "__main__":
    raise SystemExit(main())
