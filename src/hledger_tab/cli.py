# SPDX-License-Identifier: GPL-3.0-or-later
"""The ``hledger-tab`` command line entry point (DESIGN.md §10.2, §15).

Run as ``hledger-tab`` or, through hledger's add-on mechanism, ``hledger tab``.
"""

import argparse
from collections.abc import Callable, Sequence

from hledger_tab import __version__

PROG = "hledger-tab"

type Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser. Subcommands register on ``subparsers``."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Document intake, review and evidence archive for hledger.",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    # Subcommands are added here; each sets ``handler`` via ``set_defaults``.
    parser.add_subparsers(title="commands", metavar="COMMAND")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` (default: ``sys.argv[1:]``) and run the chosen command.

    Returns the process exit code. ``--version`` and ``--help`` exit through
    argparse with ``SystemExit(0)``.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Handler | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
