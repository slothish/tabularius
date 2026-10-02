# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-suite wide configuration."""

# ``pytester`` runs pytest inside a test; used to prove that the invariant
# suite's no-skip rule works (tests/test_invariants_no_skip.py).
pytest_plugins = ["pytester"]
