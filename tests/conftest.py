# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-suite wide configuration."""

from pathlib import Path

import pytest

# ``pytester`` runs pytest inside a test; used to prove that the invariant
# suite cannot be skipped (tests/test_invariants_no_skip.py).
pytest_plugins = ["pytester"]

INVARIANTS = Path(__file__).parent / "invariants"


def pytest_deselected(items: list[pytest.Item]) -> None:
    """Refuse to deselect invariant tests (DESIGN.md §15: never skipped).

    Covers ``-k``, ``-m`` and ``--deselect``. To run a subset of the suite,
    pass paths instead (e.g. ``pytest tests/contracts -k money``). Leaving
    the directory out with ``--ignore`` stays possible as an explicit choice.
    """
    invariant_items = [
        item.nodeid for item in items if item.path.is_relative_to(INVARIANTS)
    ]
    if invariant_items:
        raise pytest.UsageError(
            "invariant tests must not be deselected (DESIGN.md §15): "
            f"{len(invariant_items)} item(s), e.g. {invariant_items[0]}; "
            "pass paths to run a subset instead"
        )
