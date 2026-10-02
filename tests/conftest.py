# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-suite wide configuration."""

import os
from pathlib import Path

import pytest

# ``pytester`` runs pytest inside a test; used to prove that the invariant
# suite cannot be skipped (tests/test_invariants_no_skip.py).
pytest_plugins = ["pytester"]

INVARIANTS = Path(__file__).parent / "invariants"
DESELECTED_INVARIANTS = pytest.StashKey[list[str]]()
MESSAGE = "invariant tests must not be deselected (DESIGN.md §15)"


def running_in_ci() -> bool:
    """Whether the ``CI`` environment variable is set (GitHub Actions sets
    ``CI=true``)."""
    return os.environ.get("CI", "").lower() not in ("", "0", "false")


def pytest_deselected(items: list[pytest.Item]) -> None:
    """Refuse to deselect invariant tests in CI (DESIGN.md §15: never skipped).

    Covers ``-k``, ``-m`` and ``--deselect``. In CI this is a usage error.
    Locally it is allowed for convenience, and the terminal summary names the
    deselected invariant tests. Selecting by path (``pytest tests/contracts``)
    or ``--ignore`` does not deselect anything and is always allowed.
    """
    deselected = [item for item in items if item.path.is_relative_to(INVARIANTS)]
    if not deselected:
        return
    if running_in_ci():
        raise pytest.UsageError(
            f"{MESSAGE}: {len(deselected)} item(s), e.g. {deselected[0].nodeid}; "
            "pass paths to run a subset instead"
        )
    stash = deselected[0].config.stash
    stash.setdefault(DESELECTED_INVARIANTS, []).extend(i.nodeid for i in deselected)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    """Name the invariant tests deselected in a local run.

    A report line, not a Python warning: with ``filterwarnings = error`` a
    warning would turn into an error.
    """
    deselected = config.stash.get(DESELECTED_INVARIANTS, None)
    if not deselected:
        return
    terminalreporter.write_sep("=", "WARNING: invariant tests deselected", yellow=True)
    terminalreporter.write_line(
        f"{MESSAGE}; allowed locally, a usage error in CI. "
        f"{len(deselected)} deselected:"
    )
    for nodeid in deselected:
        terminalreporter.write_line(f"  {nodeid}")
