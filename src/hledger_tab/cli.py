# SPDX-License-Identifier: GPL-3.0-or-later
"""The ``hledger-tab`` command line entry point (DESIGN.md §10.2, §15).

Run as ``hledger-tab`` or, through hledger's add-on mechanism, ``hledger tab``.
"""

import argparse
import json
from collections.abc import Callable, Sequence

from hledger_tab import __version__
from hledger_tab.contracts import CONTRACTS, json_schema

PROG = "hledger-tab"

type Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser. Subcommands register on ``subparsers``."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Document intake, review and evidence archive for hledger.",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    # Each subcommand sets ``handler`` via ``set_defaults``.
    commands = parser.add_subparsers(title="commands", metavar="COMMAND")

    schema = commands.add_parser(
        "schema",
        help="print the JSON Schema of a contract",
        description=(
            "Print the JSON Schema of the contract NAME, "
            "or list the contract names when NAME is omitted."
        ),
    )
    schema.add_argument("name", nargs="?", choices=list(CONTRACTS), metavar="NAME")
    schema.set_defaults(handler=run_schema)
    return parser


def run_schema(args: argparse.Namespace) -> int:
    """``hledger-tab schema [NAME]``."""
    name: str | None = args.name
    if name is None:
        for contract in CONTRACTS:
            print(contract)
    else:
        print(json.dumps(json_schema(name), indent=2, ensure_ascii=False))
    return 0


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
