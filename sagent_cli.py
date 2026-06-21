#!/usr/bin/env python3
"""CLI entry point for the sagent command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo-root modules resolve even when editable-install metadata is stale.
_PKG_ROOT = Path(__file__).resolve().parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="sagent",
        description="AI agent harness with HydraDB long-term memory",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("repl", help="Interactive REPL (default)")
    subparsers.add_parser("demo", help="Cross-session memory demo")

    args = parser.parse_args(argv)

    if args.command in (None, "repl"):
        from repl import main as repl_main

        repl_main()
        return

    if args.command == "demo":
        from demo import demo

        demo()
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
